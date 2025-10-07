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
import json
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
    asyncio.create_task(destribute_tasks(app.state.state))
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
            await ws.close()  # 自定义关闭码，表示超时
            return

        registration = bytes2proto(reg_data)
        if type(registration) != NodeRegistration:
            await ws.close()
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
                # 错误的数据包
                continue
            if type(data) == worker_pb2.NodeStatus:
                await state.worker_manager.handle_heartbeat(ws, data)
            elif type(data) == common_pb2.TaskResult:
                await state.task_manager.put_result(data)
            elif type(data) == worker_pb2.UnregisterNode:
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

        # logger.error(traceback.format_exc())
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


# 任务分发
async def destribute_tasks(state: AppState):
    logger.info("Task distribution started")
    while True:
        task: Task = await state.task_manager.get()
        worker = await state.worker_manager.get()
        logger.info(f"Distribute task {task.task_id} to {worker.registration.name}")
        await worker.websocket.send_bytes(
            proto2bytes(
                TaskProto(
                    task_id=task.task_id,
                    wasm_module=task.wasm_module,
                    args=json.dumps(task.args),
                    entry=task.entry,  # type: ignore
                    priority=task.priority,
                ),
                Envelope.MessageType.TASK,
            )
        )
