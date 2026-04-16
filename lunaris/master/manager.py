from typing import Optional, Dict, List
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from lunaris.proto.worker_pb2 import (
    NodeRegistration,
    NodeRegistrationReply,
    NodeStatus,
)
from collections import deque
from lunaris.proto.common_pb2 import TaskResult
from dataclasses import dataclass, field
import secrets
from lunaris.utils import proto2bytes
from datetime import datetime, timedelta
from lunaris.master.model import Task, TaskStatus
import asyncio
from loguru import logger


@dataclass
class Worker:
    websocket: WebSocket
    registration: NodeRegistration
    node_id: str = field(default_factory=lambda: secrets.token_hex(16))
    last_heartbeat: datetime = datetime.now()
    status: Optional[NodeStatus] = None
    current_tasks: List[str] = field(default_factory=list)  # 当前正在执行的任务ID列表

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "status": {
                "current_task": self.status.current_task if self.status else None,
                "state": self.status.status if self.status else None,
            },
            "current_tasks": self.current_tasks,
            "registration": {
                "name": self.registration.name,
                "arch": self.registration.arch,
                "max_concurrency": self.registration.max_concurrency,
                "memory_size": self.registration.memory_size,
            },
        }

    def add_task(self, task_id: str):
        """添加任务到worker的当前任务列表"""
        if task_id not in self.current_tasks:
            self.current_tasks.append(task_id)

    def remove_task(self, task_id: str):
        """从worker的当前任务列表中移除任务"""
        if task_id in self.current_tasks:
            self.current_tasks.remove(task_id)

    @property
    def current_load(self) -> int:
        """返回worker的当前负载（正在执行的任务数）"""
        return len(self.current_tasks)

    @property
    def available_slots(self) -> int:
        """返回worker的可用任务槽位"""
        if self.registration:
            return max(0, self.registration.max_concurrency - self.current_load)
        return 0


class WorkerManager:
    def __init__(self):
        self.workers: List[Worker] = []
        self.result = {}
        self.condition = asyncio.Condition()

    async def register(self, ws: WebSocket, registration: NodeRegistration):
        worker = Worker(ws, registration)
        logger.info(f"Registering worker: {registration.name}")
        self.workers.append(worker)
        await ws.send_bytes(proto2bytes(NodeRegistrationReply(node_id=worker.node_id)))

    def get_worker(self, node_id: str) -> Optional[Worker]:
        for worker in self.workers:
            if worker.node_id == node_id:
                return worker
        return None

    def get_worker_by_ws(self, ws: WebSocket) -> Optional[Worker]:
        for worker in self.workers:
            if worker.websocket == ws:
                return worker
        return None

    def remove_worker(self, worker: Worker) -> None:
        if worker in self.workers:
            self.workers.remove(worker)

    async def get_available_worker(self) -> Worker:
        """获取可用的worker，考虑当前负载"""
        async with self.condition:
            while True:
                available_workers = []
                for worker in self.workers:
                    if (
                        worker.status
                        and worker.status.status == NodeStatus.NodeState.IDLE
                        and worker.websocket.client_state == WebSocketState.CONNECTED
                        and worker.available_slots > 0
                    ):
                        available_workers.append(worker)

                if available_workers:
                    # 按可用槽位降序排序，选择最空闲的worker
                    return max(available_workers, key=lambda w: w.available_slots)

                # 没有可用worker，等待通知
                await self.condition.wait()

    async def close(self):
        for worker in self.workers:
            if worker.websocket.client_state != WebSocketState.DISCONNECTED:
                await worker.websocket.close()

    async def handle_heartbeat(self, worker_ws: WebSocket, status: NodeStatus):
        for w in self.workers:
            if w.websocket == worker_ws:
                w.last_heartbeat = datetime.now()
                w.status = status
                break
        async with self.condition:
            self.condition.notify_all()

    async def remove_inactive_workers(self):
        cutoff_time = datetime.now() - timedelta(seconds=20)
        workers_to_remove = []

        for w in self.workers:
            if w.websocket.client_state == WebSocketState.DISCONNECTED:
                workers_to_remove.append(w)
                continue

            if w.last_heartbeat < cutoff_time:
                workers_to_remove.append(w)

        for w in workers_to_remove:
            logger.info(f"Removing inactive worker: {w.node_id}")
            try:
                if w.websocket.client_state != WebSocketState.DISCONNECTED:
                    await w.websocket.close()
            except:
                pass
            self.workers.remove(w)


class TaskManager:
    def __init__(self):
        self.task_queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue()
        self._tasks_dict: Dict[str, Task] = {}  # 任务ID到Task对象的映射
        self.running_tasks: Dict[str, Task] = {}  # 正在运行的任务
        self.failed_count: Dict[str, int] = {}
        self.task_websockets: Dict[str, WebSocket] = {}
        self.result = deque(maxlen=1024)

    def add_task(self, task: Task, ws: WebSocket) -> None:
        self.task_queue.put_nowait(task)
        self._tasks_dict[task.task_id] = task
        self.task_websockets[task.task_id] = ws

    async def get(self) -> Task:
        """获取任务并标记为已分配"""
        task = await self.task_queue.get()
        # 注意：这里不标记为RUNNING，因为还没有实际分配给worker
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """根据任务ID获取任务"""
        return self._tasks_dict.get(task_id)

    def all(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks_dict.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """根据状态获取任务"""
        return [task for task in self._tasks_dict.values() if task.status == status]

    def get_tasks_by_worker(self, worker_id: str) -> List[Task]:
        """获取分配给指定worker的任务"""
        return [
            task
            for task in self._tasks_dict.values()
            if task.assigned_worker == worker_id
        ]

    async def assign_task_to_worker(self, task: Task, worker: Worker):
        """将任务分配给worker"""
        task.assign_to_worker(worker.node_id)
        worker.add_task(task.task_id)
        self.running_tasks[task.task_id] = task

    async def put_result(
        self, result: TaskResult, worker_manager: WorkerManager, source_worker: Worker
    ) -> None:
        """处理任务执行结果"""
        logger.debug(f"Task Result: {result}")

        task = self.running_tasks.get(result.task_id)
        if not task:
            logger.warning(f"Received result for unknown task: {result.task_id}")
            return

        if task.assigned_worker != source_worker.node_id:
            logger.warning(
                "Rejected task result for task {} from unexpected worker {}",
                result.task_id,
                source_worker.node_id,
            )
            return

        # 更新worker状态
        worker = worker_manager.get_worker(task.assigned_worker)  # type: ignore
        if worker:
            worker.remove_task(result.task_id)

        # 从运行任务中移除
        self.running_tasks.pop(result.task_id)

        if result.succeeded:
            task.mark_completed()
            ws = self.task_websockets.get(result.task_id)
            if ws:
                await ws.send_bytes(proto2bytes(result))
            self.result.append(result)
            logger.info(f"Task {result.task_id} completed successfully")

            # 清理失败计数
            if result.task_id in self.failed_count:
                del self.failed_count[result.task_id]

        else:
            # 任务失败处理
            failure_count = self.failed_count.get(result.task_id, 0) + 1
            self.failed_count[result.task_id] = failure_count

            logger.error(f"Task {result.task_id} failed (attempt {failure_count})")

            if failure_count >= task.max_retries:
                # 达到最大重试次数
                task.mark_failed()
                logger.error(f"Task {result.task_id} reached maximum retries")
                ws = self.task_websockets.get(result.task_id)
                if ws:
                    await ws.send_bytes(proto2bytes(result))
                self.result.append(result)
                # 清理失败计数
                del self.failed_count[result.task_id]
            else:
                # 重试任务
                task.mark_retrying()
                logger.info(
                    f"Retrying task {result.task_id} (attempt {failure_count + 1})"
                )
                ws = self.task_websockets.get(result.task_id)
                if ws:
                    self.add_task(task, ws)
