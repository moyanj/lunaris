from fastapi import FastAPI, WebSocket
from lunaris.utils import bytes2proto
from lunaris.proto.task_pb2 import NodeRegistration

app = FastAPI()


@app.websocket("/worker")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    reg_data = await ws.receive_bytes()
    try:
        registration = bytes2proto(reg_data)
        if type(registration) != NodeRegistration:
            await ws.close()
    except Exception as e:
        print(e)
