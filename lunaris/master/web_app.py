import asyncio
import os
import secrets
from typing import Optional
from fastapi import FastAPI, WebSocket, Depends
from fastapi.websockets import WebSocketState, WebSocketDisconnect
from lunaris.proto import common_pb2
from lunaris.utils import bytes2proto, proto2bytes
from lunaris.proto.worker_pb2 import (
    ControlCommand,
    NodeRegistration,
    Task as TaskProto,
)
from lunaris.proto.common_pb2 import Envelope
import lunaris.proto.worker_pb2 as worker_pb2
from lunaris.master.manager import WorkerManager, TaskManager
from lunaris.master.model import Task
from contextlib import asynccontextmanager
import orjson
from loguru import logger


class AppState:
    worker_manager: WorkerManager = WorkerManager()
    task_manager: TaskManager = TaskManager()
    client_token: str = os.environ.get("CLIENT_TOKEN", secrets.token_hex(16))
    worker_token: str = os.environ.get("WORKER_TOKEN", secrets.token_hex(16))

    async def close(self):
        await self.worker_manager.close()


def get_app_state() -> AppState:
    return app.state.state


@asynccontextmanager
async def lifecycle(app: FastAPI):
    from lunaris.master.api import app as api

    app.state.state = AppState()
    logger.info(f"Worker Token: {app.state.state.worker_token}")
    logger.info(f"Client Token: {app.state.state.client_token}")
    asyncio.create_task(check_heartbeat(app.state.state))
    asyncio.create_task(distribute_tasks(app.state.state))
    app.include_router(api)
    yield
    await app.state.state.close()


app = FastAPI(lifespan=lifecycle)


@app.websocket("/worker")
async def websocket_endpoint(ws: WebSocket, state: AppState = Depends(get_app_state)):
    await ws.accept()
    try:
        reg_data: Optional[bytes] = None
        try:
            reg_data = await asyncio.wait_for(ws.receive_bytes(), timeout=10.0)
        except asyncio.TimeoutError:
            await ws.close()
            return

        registration = bytes2proto(reg_data)
        if type(registration) != NodeRegistration:
            await ws.close()
            return
        if not registration.token == state.worker_token:
            await ws.send_bytes(
                proto2bytes(
                    ControlCommand(
                        type=ControlCommand.CommandType.SHUTDOWN, data="Invalid token"
                    )
                )
            )
            await ws.close()
            return
        await state.worker_manager.register(ws, registration)

        while True and ws.client_state == WebSocketState.CONNECTED:
            data = await ws.receive_bytes()
            try:
                data = bytes2proto(data)
            except ValueError:
                continue
            if type(data) == worker_pb2.NodeStatus:
                await state.worker_manager.handle_heartbeat(ws, data)
            elif type(data) == common_pb2.TaskResult:
                await state.task_manager.put_result(data, state.worker_manager)
            elif type(data) == worker_pb2.UnregisterNode:
                # 清理worker上的所有任务
                worker = state.worker_manager.get_worker(data.node_id)
                if worker:
                    for task_id in worker.current_tasks[:]:
                        task = state.task_manager.get_task(task_id)
                        if task and task.status in ["assigned", "running"]:
                            task.mark_retrying()
                            ws = state.task_manager.task_websockets.get(task_id)  # type: ignore
                            if ws:
                                state.task_manager.add_task(task, ws)
                # 移除worker
                for w in state.worker_manager.workers:
                    if w.node_id == data.node_id:
                        state.worker_manager.workers.remove(w)
                        break
                logger.info(f"Unregistered node {data.node_id}")

            else:
                await ws.send_text("Invalid message")
                break
    except WebSocketDisconnect:
        logger.warning("A worker disconnected")
    except Exception as e:
        import traceback

        logger.error(traceback.format_exc())
        logger.error(f"Error: {e}")
    finally:
        if ws.client_state != WebSocketState.DISCONNECTED:
            try:
                await ws.close()
            except Exception:
                pass


async def check_heartbeat(state: AppState):
    logger.info("Heartbeat detection task started")
    try:
        while True:
            await asyncio.sleep(20)
            await state.worker_manager.remove_inactive_workers()
    except asyncio.CancelledError:
        pass


async def distribute_tasks(state: AppState):
    logger.info("Task distribution started")
    while True:
        task: Task = await state.task_manager.get()
        worker = await state.worker_manager.get_available_worker()
        if worker:
            logger.info(
                f"Distributing task {task.task_id} to {worker.registration.name}"
            )

            # 分配任务给worker
            await state.task_manager.assign_task_to_worker(task, worker)

            # 发送任务到worker
            await worker.websocket.send_bytes(
                proto2bytes(
                    TaskProto(
                        task_id=task.task_id,
                        wasm_module=task.wasm_module,
                        args=orjson.dumps(task.args).decode("utf-8"),
                        entry=task.entry,
                        priority=task.priority,
                    ),
                    Envelope.MessageType.TASK,
                )
            )
        else:
            logger.warning(f"No available worker for task {task.task_id}, re-queueing")
            # 如果没有可用worker，重新加入队列
            ws = state.task_manager.task_websockets.get(task.task_id)
            if ws:
                state.task_manager.add_task(task, ws)
