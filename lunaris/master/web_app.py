import asyncio
from fastapi import FastAPI, WebSocket, Depends
from fastapi.websockets import WebSocketState, WebSocketDisconnect
from lunaris.utils import bytes2proto, proto2bytes
from lunaris.proto.task_pb2 import NodeRegistration, NodeStatus, Task as TaskProto
from lunaris.master.manager import WorkerManager, TaskManager
from lunaris.core.model import Task
from contextlib import asynccontextmanager
import json


class AppState:
    worker_manager: WorkerManager = WorkerManager()
    task_manager: TaskManager = TaskManager()

    async def close(self):
        await self.worker_manager.close()


def get_app_state() -> AppState:
    return app.state.state


@asynccontextmanager
async def lifecycle(app: FastAPI):
    from lunaris.master.api import app as api

    app.state.state = AppState()
    asyncio.create_task(check_heartbeat(app.state.state))
    asyncio.create_task(destribute_tasks(app.state.state))
    app.include_router(api)
    yield
    await app.state.state.close()


app = FastAPI(lifespan=lifecycle)


@app.websocket("/worker")
async def websocket_endpoint(ws: WebSocket, state: AppState = Depends(get_app_state)):
    await ws.accept()
    reg_data = await ws.receive_bytes()
    try:
        registration = bytes2proto(reg_data)
        if type(registration) != NodeRegistration:
            await ws.close()
        await state.worker_manager.register(ws, registration)

        while True:
            data = await ws.receive_bytes()
            await state.worker_manager.dispatch(ws, data)
    except WebSocketDisconnect:
        print("Worker disconnected")
    except Exception as e:
        print(f"Error with worker connection: {e}")
    finally:
        if ws.client_state != WebSocketState.DISCONNECTED:
            print(str(ws.state))
            await ws.close()


async def check_heartbeat(state: AppState):
    try:
        while True:
            await asyncio.sleep(20)  # 每5秒检查一次
            await state.worker_manager.remove_inactive_workers()
    except asyncio.CancelledError:
        pass


# 任务分发
async def destribute_tasks(state: AppState):
    while True:
        task: Task = await state.task_manager.get()
        idle_worker = []
        for worker in state.worker_manager.workers:
            if worker.status == NodeStatus.NodeState.IDLE:
                idle_worker.append(worker)

        low_worker: list = sorted(idle_worker, key=lambda x: x.current_task)
        await low_worker[0].websocket.send(
            proto2bytes(
                TaskProto(
                    task_id=task.task_id,
                    code=task.code,
                    args=json.dumps(task.args),
                    lua_version=task.lua_version,
                    priority=task.priority,
                )
            )
        )
