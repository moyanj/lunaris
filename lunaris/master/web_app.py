import asyncio
from fastapi import FastAPI, WebSocket
from lunaris.utils import bytes2proto
from lunaris.proto.task_pb2 import NodeRegistration, NodeStatus
from lunaris.master.manager import WorkerManager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifecycle(app: FastAPI):
    app.state.worker_manager = WorkerManager()
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
        
        # 启动心跳检查任务
        heartbeat_task = asyncio.create_task(check_heartbeat(app, ws))
        
        while True:
            data = await ws.receive_bytes()
            await app.state.worker_manager.dispatch(ws, data)
            
    except Exception as e:
        print(e)
        await ws.close()
        
async def check_heartbeat(app, ws):
    try:
        while True:
            await asyncio.sleep(5)  # 每5秒检查一次
            app.state.worker_manager.remove_inactive_workers()
    except asyncio.CancelledError:
        pass