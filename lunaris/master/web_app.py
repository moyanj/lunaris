import asyncio
from fastapi import FastAPI, WebSocket
from lunaris.utils import bytes2proto, proto2bytes
from lunaris.proto.task_pb2 import NodeRegistration, NodeStatus, Task as TaskProto
from lunaris.master.manager import WorkerManager
from lunaris.core.model import Task
from contextlib import asynccontextmanager
import json


@asynccontextmanager
async def lifecycle(app: FastAPI):
    app.state.worker_manager = WorkerManager()
    asyncio.create_task(check_heartbeat(app))  # 心跳检测
    yield
    await app.state.worker_manager.close()


app = FastAPI(lifespan=lifecycle)


@app.websocket("/worker")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    reg_data = await ws.receive_bytes()
    try:
        registration = bytes2proto(reg_data)
        if type(registration) != NodeRegistration:
            await ws.close()
        await app.state.worker_manager.register(ws, registration)

        while True:
            data = await ws.receive_bytes()
            await app.state.worker_manager.dispatch(ws, data)

    except Exception as e:
        print(e)
        await ws.close()


async def check_heartbeat(app):
    try:
        while True:
            await asyncio.sleep(20)  # 每5秒检查一次
            app.state.worker_manager.remove_inactive_workers()
    except asyncio.CancelledError:
        pass


# 任务分发
async def destribute_tasks(app):
    while True:
        task: Task = await app.state.task_manager.get()
        idle_worker = []
        for worker in app.state.worker_manager.workers:
            if worker.status == NodeStatus.NodeState.IDLE:
                idle_worker.append(worker)

        low_worker = sorted(idle_worker, key=lambda x: x.current_task)
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
