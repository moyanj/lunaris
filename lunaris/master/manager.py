from fastapi import WebSocket
from lunaris.proto.task_pb2 import NodeRegistration, NodeRegistrationReply, TaskResult, NodeStatus
import secrets
from lunaris.utils import bytes2proto, proto2bytes
from datetime import datetime, timedelta


class Worker:
    def __init__(
        self, websocket: WebSocket, registration: NodeRegistration, node_id: str
    ):
        self.websocket = websocket
        self.registration: NodeRegistration = registration
        self.node_id: str = node_id
        self.last_heartbeat = datetime.now()


class WorkerManager:
    def __init__(self):
        self.workers: list[Worker] = []
        self.result = {}

    async def register(self, worker: WebSocket, registration: NodeRegistration):
        node_id = secrets.token_hex(16)
        self.workers.append(Worker(worker, registration, node_id))
        await worker.send_bytes(proto2bytes(NodeRegistrationReply(node_id=node_id)))

    async def dispatch(self, worker: WebSocket, data: bytes):
        data = bytes2proto(data)
        if type(data) == TaskResult:
            self.result[data.task_id] = data
        elif type(data) == NodeStatus:
            await self.handle_heartbeat(worker, data)

    async def close(self):
        for worker in self.workers:
            await worker.websocket.close()

    async def handle_heartbeat(self, worker: WebSocket, status: NodeStatus):
        for w in self.workers:
            if w.websocket == worker:
                w.last_heartbeat = datetime.now()
                break

    def remove_inactive_workers(self):
        cutoff_time = datetime.now() - timedelta(seconds=15)
        self.workers = [w for w in self.workers if w.last_heartbeat > cutoff_time]
