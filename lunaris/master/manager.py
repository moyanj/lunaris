from typing import Optional
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from lunaris.proto.task_pb2 import (
    NodeRegistration,
    NodeRegistrationReply,
    TaskResult,
    NodeStatus,
)
from dataclasses import dataclass
import secrets
from lunaris.utils import bytes2proto, proto2bytes
from datetime import datetime, timedelta
from lunaris.core.model import Task
import asyncio


@dataclass
class Worker:
    websocket: WebSocket
    registration: NodeRegistration
    node_id: str = secrets.token_hex(16)
    last_heartbeat: datetime = datetime.now()
    status: Optional[NodeStatus] = None


class WorkerManager:
    def __init__(self):
        self.workers: list[Worker] = []
        self.result = {}

    async def register(self, ws: WebSocket, registration: NodeRegistration):
        worker = Worker(ws, registration)
        print(f"Registering worker {registration.hostname}")
        self.workers.append(worker)
        await ws.send_bytes(proto2bytes(NodeRegistrationReply(node_id=worker.node_id)))

    async def dispatch(self, worker: WebSocket, data: bytes):
        data = bytes2proto(data)
        if type(data) == TaskResult:
            self.result[data.task_id] = data
        elif type(data) == NodeStatus:
            await self.handle_heartbeat(worker, data)
        else:
            await worker.send_text("Invalid message")
            await worker.close()

    def get_worker(self, node_id: str):
        for worker in self.workers:
            if worker.node_id == node_id:
                return worker

    async def close(self):
        for worker in self.workers:
            if worker.websocket.client_state != WebSocketState.DISCONNECTED:
                await worker.websocket.close()

    async def handle_heartbeat(self, worker: WebSocket, status: NodeStatus):
        for w in self.workers:
            if w.websocket == worker:
                print(f"Heartbeat from {w.node_id}")
                w.last_heartbeat = datetime.now()
                w.status = status
                break

    async def remove_inactive_workers(self):
        cutoff_time = datetime.now() - timedelta(seconds=20)
        for w in self.workers:
            if w.last_heartbeat < cutoff_time:
                print(f"Removing inactive worker {w.node_id}")
                if w.websocket.client_state != WebSocketState.DISCONNECTED:
                    await w.websocket.close()
                self.workers.remove(w)


class TaskManager:
    def __init__(self):
        self.task_queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue()
        self._tasks_list: list[Task] = []

    def add_task(self, task: Task) -> None:
        """
        添加一个任务。
        这是一个同步方法，它将任务放入异步队列中。
        """
        self.task_queue.put_nowait(task)
        # 维护一个同步列表，用于 list_all_tasks，因为它需要所有任务
        # 注意：这个列表的排序需要单独维护或者在获取时重新排序
        self._tasks_list.append(task)
        # 为了保持 _tasks_list 的一致性，每次添加后都排序
        self._sort_tasks_list()

    def _sort_tasks_list(self):
        """
        内部排序方法：按重要度降序排序，重要度相同则按时间戳升序（先添加的在前）。
        用于维护 self._tasks_list 的顺序。
        """
        # 注意这里使用原始的 importance 和 timestamp 进行排序
        self._tasks_list.sort(key=lambda t: (-t.priority, t.timestamp))

    async def get(self) -> Task:
        """
        异步获取当前最重要的任务。
        如果队列为空，此方法将阻塞，直到有任务可用。
        返回 Task 实例。
        """

        task = await self.task_queue.get()

        if task in self._tasks_list:
            self._tasks_list.remove(task)
        return task

    def all(self) -> list[Task]:
        """
        返回当前所有任务，按重要度降序，重要度相同按添加时间排序。
        这是一个同步方法，直接返回内部维护的列表。
        """
        # _tasks_list 已经在 add_task 中维护了排序
        return self._tasks_list[:]  # 返回副本，防止外部修改
