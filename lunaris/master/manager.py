from typing import Optional
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from lunaris.proto.worker_pb2 import (
    NodeRegistration,
    NodeRegistrationReply,
    NodeStatus,
)
from lunaris.proto.common_pb2 import TaskResult
from dataclasses import dataclass, field
import secrets
from lunaris.utils import proto2bytes
from datetime import datetime, timedelta
from lunaris.master.model import Task
import asyncio
from loguru import logger


@dataclass
class Worker:
    __solt__ = ["node_id", "last_heartbeat", "status", "registration"]
    websocket: WebSocket
    registration: NodeRegistration
    node_id: str = field(default_factory=lambda: secrets.token_hex(16))
    last_heartbeat: datetime = datetime.now()
    status: Optional[NodeStatus] = None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "status": {
                "current_task": self.status.current_task if self.status else None
            },
            "registration": {
                "name": self.registration.name,
                "os": self.registration.os,
                "arch": self.registration.arch,
                "max_concurrency": self.registration.max_concurrency,
                "num_cpu": self.registration.num_cpu,
                "memory_size": self.registration.memory_size,
            },
        }


class WorkerManager:
    def __init__(self):
        self.workers: list[Worker] = []
        self.result = {}
        self.condition = asyncio.Condition()

    async def register(self, ws: WebSocket, registration: NodeRegistration):
        worker = Worker(ws, registration)
        logger.info(f"Registering worker: {registration.name}")
        self.workers.append(worker)
        await ws.send_bytes(proto2bytes(NodeRegistrationReply(node_id=worker.node_id)))

    def get_worker(self, node_id: str):
        for worker in self.workers:
            if worker.node_id == node_id:
                return worker

    async def get(self):
        async with self.condition:
            idle_workers = []
            for i in self.workers:
                if i.status and i.status.status == NodeStatus.NodeState.IDLE:
                    idle_workers.append(i)
            low_worker: list[Worker] = sorted(
                idle_workers, key=lambda x: x.status.current_task  # type: ignore
            )
            while len(low_worker) == 0:
                await self.condition.wait()
                # 可能需要重新计算 idle_workers 和 low_worker
                idle_workers = []
                for i in self.workers:
                    if i.status and i.status.status == NodeStatus.NodeState.IDLE:
                        idle_workers.append(i)
                low_worker = sorted(
                    idle_workers, key=lambda x: x.status.current_task  # type: ignore
                )

            return low_worker[0]

    async def close(self):
        for worker in self.workers:
            if worker.websocket.client_state != WebSocketState.DISCONNECTED:
                await worker.websocket.close()

    async def handle_heartbeat(self, worker: WebSocket, status: NodeStatus):
        for w in self.workers:
            if w.websocket == worker:
                w.last_heartbeat = datetime.now()
                w.status = status
                break
        async with self.condition:
            self.condition.notify_all()

    async def remove_inactive_workers(self):
        cutoff_time = datetime.now() - timedelta(seconds=20)
        for w in self.workers:
            if w.last_heartbeat < cutoff_time:
                logger.info(f"Removing inactive worker: {w.node_id}")
                if w.websocket.client_state != WebSocketState.DISCONNECTED:
                    await w.websocket.close()
                self.workers.remove(w)


class TaskManager:
    def __init__(self):
        self.task_queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue()
        self._tasks_list: list[Task] = []
        self.running_tasks = {}
        self._result = {}
        self.failed_count = {}

    def add_task(self, task: Task) -> None:
        self.task_queue.put_nowait(task)
        self._tasks_list.append(task)
        # 为了保持 _tasks_list 的一致性，每次添加后都排序
        self._sort_tasks_list()

    def _sort_tasks_list(self):
        """
        内部排序方法：按重要度降序排序，重要度相同则按时间戳升序（先添加的在前）。
        用于维护 self._tasks_list 的顺序。
        """
        # 注意这里使用原始的 importance 和 timestamp 进行排序
        self._tasks_list.sort(key=lambda t: (-t.priority, t.task_id))

    async def get(self) -> Task:
        """
        异步获取当前最重要的任务。
        如果队列为空，此方法将阻塞，直到有任务可用。
        返回 Task 实例。
        """

        task = await self.task_queue.get()

        if task in self._tasks_list:
            self._tasks_list.remove(task)
            self.running_tasks[task.task_id] = task
        return task

    def all(self) -> list[Task]:
        """
        返回当前所有任务，按重要度降序，重要度相同按添加时间排序。
        这是一个同步方法，直接返回内部维护的列表。
        """
        # _tasks_list 已经在 add_task 中维护了排序
        return self._tasks_list[:]  # 返回副本，防止外部修改

    def put_result(self, result: TaskResult) -> None:
        """
        处理任务执行结果，包括成功、失败重试和永久失败。
        """
        logger.debug(f"Task Result: {result}")
        # 在正在运行的任务集合中查找对应的任务对象
        task_to_process = self.running_tasks.get(result.task_id)

        if not task_to_process:
            logger.warning(
                f"Received a task result that is not in running: {result.task_id}"
            )
            return

        # 任务已结束（无论成功或失败），将其从运行集合中移除
        self.running_tasks.pop(result.task_id)
        if result.succeeded:
            # 任务成功，存储最终结果
            self._result[result.task_id] = result
            logger.info(f"Task {result.task_id} done.")
            # 如果任务之前有失败记录，清理掉
            if result.task_id in self.failed_count:
                del self.failed_count[result.task_id]
        else:
            # 任务失败，增加失败计数
            failure_count = self.failed_count.get(result.task_id, 0) + 1
            self.failed_count[result.task_id] = failure_count

            logger.error(f"Task {result.task_id} failed (attempt {failure_count})")

            if failure_count >= 3:
                # 达到最大重试次数，标记为永久失败并存储结果
                logger.error(
                    f"Task {result.task_id} has reached the maximum number of retries."
                )
                self._result[result.task_id] = result
                # 清理失败计数
                del self.failed_count[result.task_id]
            else:
                # 未达到最大重试次数，将任务重新加入队列
                logger.info(f"Retring task {result.task_id} ")
                self.add_task(task_to_process)
