from fastapi import WebSocket
from lunaris.proto.task_pb2 import NodeRegistration


class Worker:
    def __init__(self, websocket: WebSocket, registration: NodeRegistration):
        self.websocket = websocket
        self.registration: NodeRegistration = registration


class TaskManager:
    def __init__(self):
        self.workers: list[Worker] = []

    def register(self, worker: WebSocket, registration: NodeRegistration):
        self.workers.append(Worker(worker, registration))
