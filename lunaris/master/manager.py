from __future__ import annotations

import asyncio
import json
import secrets
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from loguru import logger

from lunaris.master.model import (
    AttemptStatus,
    Task,
    TaskAttempt,
    TaskResultPayload,
    TaskStatus,
    WorkerRecord,
    WorkerStatus,
)
from lunaris.master.metrics import MasterMetrics
from lunaris.master.store_base import StateStore
from lunaris.proto.common_pb2 import TaskResult
from lunaris.proto.worker_pb2 import ControlCommand, NodeRegistration, NodeRegistrationReply, NodeStatus
from lunaris.runtime.capabilities import normalize_host_capabilities
from lunaris.utils import proto2bytes


@dataclass
class Worker:
    websocket: WebSocket
    registration: NodeRegistration
    node_id: str = field(default_factory=lambda: secrets.token_hex(16))
    last_heartbeat: datetime = field(default_factory=datetime.now)
    status: Optional[NodeStatus] = None
    current_tasks: List[int] = field(default_factory=list)
    drain: bool = False

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "status": {
                "current_task": self.status.current_task if self.status else None,
                "state": self.status.status if self.status else None,
                "drain": self.drain,
            },
            "current_tasks": self.current_tasks,
            "registration": {
                "name": self.registration.name,
                "arch": self.registration.arch,
                "max_concurrency": self.registration.max_concurrency,
                "memory_size": self.registration.memory_size,
                "provided_capabilities": list(
                    self.registration.provided_capabilities.items
                ),
            },
        }

    def add_task(self, task_id: int) -> None:
        if task_id not in self.current_tasks:
            self.current_tasks.append(task_id)

    def remove_task(self, task_id: int) -> None:
        if task_id in self.current_tasks:
            self.current_tasks.remove(task_id)

    @property
    def current_load(self) -> int:
        return len(self.current_tasks)

    @property
    def available_slots(self) -> int:
        return max(0, self.registration.max_concurrency - self.current_load)

    def supports(self, required_capabilities: list[str]) -> bool:
        return set(required_capabilities).issubset(
            set(self.registration.provided_capabilities.items)
        )


class WorkerManager:
    def __init__(
        self,
        store: StateStore,
        notify_scheduler: Callable[[str], Awaitable[None]],
        metrics: MasterMetrics,
    ):
        self.store = store
        self.notify_scheduler = notify_scheduler
        self.metrics = metrics
        self.workers: List[Worker] = []

    async def sync_worker_state(self, worker: Worker) -> None:
        record = self.store.workers.get(worker.node_id)
        if not record:
            return
        # worker 容量变化需要立刻落盘并唤醒调度，不再依赖 heartbeat 周期刷新。
        record.capacity_used = worker.current_load
        record.current_tasks = list(worker.current_tasks)
        record.last_heartbeat = worker.last_heartbeat
        record.connected = worker.websocket.client_state == WebSocketState.CONNECTED
        record.drain = worker.drain
        record.status = (
            WorkerStatus.DRAINING if worker.drain else WorkerStatus.ACTIVE
        )
        await self.store.persist()
        await self.notify_scheduler("worker.capacity_changed")

    async def register(self, ws: WebSocket, registration: NodeRegistration) -> None:
        provided_capabilities = normalize_host_capabilities(
            registration.provided_capabilities.items
        )
        del registration.provided_capabilities.items[:]
        registration.provided_capabilities.items.extend(provided_capabilities)
        worker = Worker(ws, registration)
        logger.info("Registering worker: {}", registration.name)
        self.workers.append(worker)
        self.metrics.worker_registrations_total.inc()
        self.metrics.connected_workers.set(len(self.workers))
        self.store.workers[worker.node_id] = WorkerRecord(
            worker_id=worker.node_id,
            name=registration.name,
            arch=registration.arch,
            max_concurrency=int(registration.max_concurrency),
            memory_size=int(registration.memory_size),
            status=WorkerStatus.ACTIVE,
            drain=False,
            capacity_used=0,
            current_tasks=[],
            provided_capabilities=provided_capabilities,
            connected=True,
            last_heartbeat=worker.last_heartbeat,
        )
        await self.store.persist()
        await self.store.append_event(
            "worker.registered",
            worker_id=worker.node_id,
            payload={"name": registration.name},
        )
        await ws.send_bytes(proto2bytes(NodeRegistrationReply(node_id=worker.node_id)))
        await self.notify_scheduler("worker.registered")

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

    def get_available_worker_nowait(
        self, required_capabilities: Optional[list[str]] = None
    ) -> Optional[Worker]:
        required_capabilities = required_capabilities or []
        available_workers = [
            worker
            for worker in self.workers
            if worker.websocket.client_state == WebSocketState.CONNECTED
            and not worker.drain
            and worker.available_slots > 0
            and worker.supports(required_capabilities)
        ]
        if not available_workers:
            return None
        return max(available_workers, key=lambda item: item.available_slots)

    async def set_drain(self, worker_id: str, enabled: bool) -> bool:
        worker = self.get_worker(worker_id)
        if not worker:
            record = self.store.workers.get(worker_id)
            if not record:
                return False
            record.drain = enabled
            record.status = WorkerStatus.DRAINING if enabled else WorkerStatus.ACTIVE
            await self.store.persist()
            await self.store.append_event(
                "worker.drain_changed",
                worker_id=worker_id,
                payload={"enabled": enabled},
            )
            await self.notify_scheduler("worker.drain_changed")
            return True

        worker.drain = enabled
        await self.sync_worker_state(worker)
        await self.store.append_event(
            "worker.drain_changed",
            worker_id=worker_id,
            payload={"enabled": enabled},
        )
        await self.send_control_command(
            worker_id,
            ControlCommand.CommandType.SET_DRAIN,
            {"enabled": enabled},
        )
        return True

    async def remove_worker(
        self,
        worker: Worker,
        *,
        status: WorkerStatus = WorkerStatus.OFFLINE,
    ) -> None:
        if worker in self.workers:
            self.workers.remove(worker)
        self.metrics.worker_disconnects_total.labels(status=status.value).inc()
        self.metrics.connected_workers.set(len(self.workers))
        record = self.store.workers.get(worker.node_id)
        if record:
            record.connected = False
            record.capacity_used = 0
            record.current_tasks = []
            record.status = status
            record.last_heartbeat = datetime.now()
            await self.store.persist()
            await self.store.append_event(
                "worker.removed",
                worker_id=worker.node_id,
                payload={"status": status.value},
            )
        await self.notify_scheduler("worker.removed")

    async def send_control_command(
        self,
        worker_id: str,
        command_type: ControlCommand.CommandType,
        payload: dict,
    ) -> bool:
        worker = self.get_worker(worker_id)
        if not worker or worker.websocket.client_state != WebSocketState.CONNECTED:
            return False
        await worker.websocket.send_bytes(
            proto2bytes(
                ControlCommand(
                    type=command_type,
                    data=json.dumps(payload),
                )
            )
        )
        return True

    async def close(self) -> None:
        for worker in self.workers[:]:
            if worker.websocket.client_state != WebSocketState.DISCONNECTED:
                await worker.websocket.close()

    async def handle_heartbeat(self, worker_ws: WebSocket, status: NodeStatus) -> None:
        worker = self.get_worker_by_ws(worker_ws)
        if not worker:
            return
        worker.last_heartbeat = datetime.now()
        worker.status = status
        await self.sync_worker_state(worker)

    async def remove_inactive_workers(self) -> List[Worker]:
        cutoff_time = datetime.now() - timedelta(seconds=20)
        removed_workers: List[Worker] = []
        for worker in self.workers[:]:
            if worker.websocket.client_state == WebSocketState.DISCONNECTED:
                await self.remove_worker(worker, status=WorkerStatus.LOST)
                removed_workers.append(worker)
                continue
            if worker.last_heartbeat < cutoff_time:
                logger.info("Removing inactive worker: {}", worker.node_id)
                try:
                    await worker.websocket.close()
                except Exception:
                    pass
                await self.remove_worker(worker, status=WorkerStatus.LOST)
                removed_workers.append(worker)
        return removed_workers


class TaskManager:
    def __init__(
        self,
        store: StateStore,
        notify_scheduler: Callable[[str], Awaitable[None]],
        metrics: MasterMetrics,
        lease_timeout_seconds: int = 30,
        retry_delay_seconds: int = 5,
    ):
        self.store = store
        self.notify_scheduler = notify_scheduler
        self.metrics = metrics
        self.task_queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue()
        self._queued_task_ids: set[int] = set()
        self._tasks_dict: Dict[int, Task] = self.store.tasks
        self.attempts: Dict[str, TaskAttempt] = self.store.attempts
        self.running_tasks: Dict[int, Task] = {}
        self.result = deque(maxlen=1024)
        self.lease_timeout = timedelta(seconds=lease_timeout_seconds)
        self.retry_delay_seconds = retry_delay_seconds
        self.subscribers: dict[int, set[WebSocket]] = defaultdict(set)
        self._recovery_dirty = self._recover_state()
        self._refresh_metrics()

    def _refresh_metrics(self) -> None:
        status_counts = {status.value: 0 for status in TaskStatus}
        for task in self._tasks_dict.values():
            status_counts[task.status.value] += 1
        for status, count in status_counts.items():
            self.metrics.tasks_by_status.labels(status=status).set(count)
        self.metrics.task_queue_size.set(self.task_queue.qsize())
        self.metrics.running_tasks.set(len(self.running_tasks))

    async def _record_event(
        self,
        event_type: str,
        *,
        task: Optional[Task] = None,
        worker_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        await self.store.append_event(
            event_type,
            task_id=task.task_id if task else None,
            worker_id=worker_id,
            payload=payload or {},
        )

    async def _persist(self) -> None:
        await self.store.persist()

    def _enqueue_task(self, task: Task) -> None:
        if task.task_id in self._queued_task_ids:
            return
        self.task_queue.put_nowait(task)
        self._queued_task_ids.add(task.task_id)

    def _recover_state(self) -> bool:
        now = datetime.now()
        dirty = False
        for task in self._tasks_dict.values():
            if task.is_terminal and task.result:
                self.result.append(task.result.to_proto(task.task_id))
                continue

            if task.status == TaskStatus.QUEUED:
                self._enqueue_task(task)
                continue

            if task.status == TaskStatus.RETRY_WAIT:
                if not task.next_retry_at or task.next_retry_at <= now:
                    # master 重启后，把已经到点的重试任务重新放回队列。
                    task.mark_queued()
                    self._enqueue_task(task)
                    dirty = True
                continue

            if task.status in {
                TaskStatus.CREATED,
                TaskStatus.LEASED,
                TaskStatus.RUNNING,
                TaskStatus.CANCEL_REQUESTED,
            }:
                # 单 master 重启后无法确认旧 worker 上的执行态，统一转为 lost/retry 或终态失败。
                latest_attempt = self._get_latest_attempt(task)
                if latest_attempt and latest_attempt.status not in {
                    AttemptStatus.FINISHED,
                    AttemptStatus.CANCELLED,
                    AttemptStatus.LOST,
                }:
                    latest_attempt.mark_lost("master restarted")
                if task.status == TaskStatus.CANCEL_REQUESTED:
                    task.mark_cancelled()
                elif task.can_retry:
                    task.schedule_retry(0, "master restarted")
                else:
                    task.mark_failed(error="master restarted")
                dirty = True

        return dirty

    async def flush_recovery(self) -> None:
        if not self._recovery_dirty:
            return
        await self._persist()
        self._recovery_dirty = False
        self._refresh_metrics()

    async def add_task(self, task: Task, ws: Optional[WebSocket] = None) -> None:
        task.mark_queued()
        self._tasks_dict[task.task_id] = task
        self.metrics.tasks_submitted_total.inc()
        if ws:
            self.subscribe(task.task_id, ws)
        self._enqueue_task(task)
        self._refresh_metrics()
        await self._persist()
        await self._record_event("task.created", task=task)
        await self._record_event("task.queued", task=task)
        await self.notify_scheduler("task.queued")

    def get_task_by_idempotency_key(self, scoped_key: str) -> Optional[Task]:
        task_id = self.store.idempotency_index.get(scoped_key)
        if not task_id:
            return None
        return self._tasks_dict.get(task_id)

    async def register_idempotency_key(self, scoped_key: Optional[str], task: Task) -> None:
        if not scoped_key:
            return
        self.store.idempotency_index[scoped_key] = task.task_id
        await self._persist()

    def pop_next_queued_task_nowait(self) -> Optional[Task]:
        while True:
            try:
                task = self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
            self._queued_task_ids.discard(task.task_id)
            current = self._tasks_dict.get(task.task_id)
            if current and current.status == TaskStatus.QUEUED:
                return current

    async def get(self) -> Task:
        while True:
            task = await self.task_queue.get()
            self._queued_task_ids.discard(task.task_id)
            current = self._tasks_dict.get(task.task_id)
            if current and current.status == TaskStatus.QUEUED:
                return current

    def get_task(self, task_id: int) -> Optional[Task]:
        return self._tasks_dict.get(task_id)

    def all(self) -> List[Task]:
        return list(self._tasks_dict.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        return [task for task in self._tasks_dict.values() if task.status == status]

    def get_tasks_by_worker(self, worker_id: str) -> List[Task]:
        return [task for task in self._tasks_dict.values() if task.assigned_worker == worker_id]

    def subscribe(self, task_id: int, ws: WebSocket) -> None:
        self.subscribers[task_id].add(ws)

    def unsubscribe(self, task_id: int, ws: Optional[WebSocket] = None) -> None:
        if task_id not in self.subscribers:
            return
        if ws is None:
            self.subscribers.pop(task_id, None)
            return
        self.subscribers[task_id].discard(ws)
        if not self.subscribers[task_id]:
            self.subscribers.pop(task_id, None)

    def unsubscribe_ws(self, ws: WebSocket) -> None:
        for task_id in list(self.subscribers):
            self.unsubscribe(task_id, ws)

    def get_task_events(self, task_id: int, after_seq: int = 0) -> list[dict]:
        return [event.to_dict() for event in self.store.get_task_events(task_id, after_seq)]

    def get_task_result(self, task_id: int) -> Optional[dict]:
        task = self.get_task(task_id)
        if not task or not task.result:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            **task.result.to_dict(),
        }

    async def cancel_task(self, task_id: int) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task or task.is_terminal:
            return task
        if task.status in {TaskStatus.QUEUED, TaskStatus.RETRY_WAIT, TaskStatus.CREATED}:
            # 未运行任务直接终止，避免再进入调度。
            task.mark_cancelled()
            await self._record_event("task.cancelled", task=task, payload={"reason": "cancelled before dispatch"})
        else:
            # 运行中任务先进入取消请求态，等待 worker 回包或丢失后收敛为终态。
            task.mark_cancel_requested()
            await self._record_event("task.cancel_requested", task=task)
        await self._persist()
        self._refresh_metrics()
        await self.notify_scheduler("task.cancelled")
        return task

    def _get_latest_attempt(self, task: Task) -> Optional[TaskAttempt]:
        if task.latest_attempt_id:
            return self.attempts.get(task.latest_attempt_id)
        for attempt in self.attempts.values():
            if attempt.task_id == task.task_id and attempt.attempt_no == task.attempt_count:
                return attempt
        return None

    async def _schedule_retry_or_fail(self, task: Task, reason: str) -> bool:
        if task.can_retry:
            # 重试不会立即回队列，而是先进入 RETRY_WAIT，避免瞬时抖动反复派发。
            task.schedule_retry(self.retry_delay_seconds, reason)
            self.metrics.task_retries_total.inc()
            await self._record_event("task.retry_scheduled", task=task, payload={"reason": reason})
            await self.notify_scheduler("task.retry_scheduled")
            return True
        task.mark_failed(error=reason)
        self.metrics.task_results_total.labels(status=TaskStatus.FAILED.value).inc()
        await self._record_event("task.failed", task=task, payload={"reason": reason})
        return False

    async def assign_task_to_worker(self, task: Task, worker: Worker) -> None:
        task.assign_to_worker(worker.node_id, datetime.now() + self.lease_timeout)
        attempt = TaskAttempt(
            task_id=task.task_id,
            attempt_no=task.attempt_count,
            worker_id=worker.node_id,
            lease_expires_at=task.lease_expires_at,
        )
        task.latest_attempt_id = attempt.attempt_id
        self.attempts[attempt.attempt_id] = attempt
        worker.add_task(task.task_id)
        self.running_tasks[task.task_id] = task
        self._refresh_metrics()
        await self._persist()
        await self._record_event(
            "task.leased",
            task=task,
            worker_id=worker.node_id,
            payload={"attempt": task.attempt_count},
        )

    async def requeue_worker_tasks(self, worker: Worker, reason: str = "") -> List[int]:
        requeued_task_ids: List[int] = []
        for task_id in worker.current_tasks[:]:
            task = self.get_task(task_id)
            if not task:
                worker.remove_task(task_id)
                self.running_tasks.pop(task_id, None)
                continue

            self.running_tasks.pop(task_id, None)
            attempt = self._get_latest_attempt(task)
            if attempt and attempt.status not in {
                AttemptStatus.FINISHED,
                AttemptStatus.CANCELLED,
                AttemptStatus.LOST,
            }:
                attempt.mark_lost(reason or "worker lost")

            worker.remove_task(task_id)
            if task.status == TaskStatus.CANCEL_REQUESTED:
                task.mark_cancelled()
                await self._record_event("task.cancelled", task=task, worker_id=worker.node_id, payload={"reason": reason or "worker lost during cancellation"})
                continue

            if task.status not in {
                TaskStatus.LEASED,
                TaskStatus.RUNNING,
                TaskStatus.CANCEL_REQUESTED,
            }:
                continue

            if await self._schedule_retry_or_fail(task, reason or "worker recovery"):
                requeued_task_ids.append(task_id)

        await self._persist()
        self._refresh_metrics()
        if requeued_task_ids:
            logger.warning(
                "Requeued {} task(s) from worker {} due to {}: {}",
                len(requeued_task_ids),
                worker.node_id,
                reason or "unknown reason",
                ", ".join(str(task_id) for task_id in requeued_task_ids),
            )
            await self.notify_scheduler("worker.tasks_requeued")
        return requeued_task_ids

    async def mark_task_running(self, task_id: int, worker: Worker, attempt: int) -> Optional[Task]:
        task = self.running_tasks.get(task_id)
        if not task:
            logger.warning("Received task acceptance for unknown task: {}", task_id)
            return None
        if task.assigned_worker != worker.node_id:
            logger.warning(
                "Rejected task acceptance for task {} from unexpected worker {}",
                task_id,
                worker.node_id,
            )
            return None
        if task.attempt_count != attempt:
            logger.warning(
                "Rejected task acceptance for task {} with stale attempt {} (current {})",
                task_id,
                attempt,
                task.attempt_count,
            )
            return None
        task.mark_running()
        active_attempt = self._get_latest_attempt(task)
        if active_attempt:
            active_attempt.status = AttemptStatus.ACCEPTED
            active_attempt.accepted_at = datetime.now()
            active_attempt.mark_running()
        await self._persist()
        self._refresh_metrics()
        await self._record_event(
            "task.running",
            task=task,
            worker_id=worker.node_id,
            payload={"attempt": attempt},
        )
        await self.notify_scheduler("task.running")
        return task

    async def requeue_expired_leases(self, worker_manager: WorkerManager) -> List[int]:
        expired_task_ids: List[int] = []
        now = datetime.now()
        for task in list(self.running_tasks.values()):
            if task.status != TaskStatus.LEASED or not task.lease_expires_at:
                continue
            if task.lease_expires_at > now:
                continue
            worker = worker_manager.get_worker(task.assigned_worker) if task.assigned_worker else None
            if worker:
                worker.remove_task(task.task_id)
            attempt = self._get_latest_attempt(task)
            if attempt and attempt.status not in {
                AttemptStatus.FINISHED,
                AttemptStatus.LOST,
                AttemptStatus.CANCELLED,
            }:
                attempt.mark_lost("task acceptance lease expired")
            self.running_tasks.pop(task.task_id, None)
            if await self._schedule_retry_or_fail(task, "task acceptance lease expired"):
                expired_task_ids.append(task.task_id)
        if expired_task_ids:
            await self._persist()
            self._refresh_metrics()
            logger.warning(
                "Requeued {} task(s) after lease expiry: {}",
                len(expired_task_ids),
                ", ".join(str(task_id) for task_id in expired_task_ids),
            )
            await self.notify_scheduler("task.lease_expired")
        return expired_task_ids

    async def put_result(
        self,
        result: TaskResult,
        worker_manager: WorkerManager,
        source_worker: Worker,
    ) -> None:
        logger.debug("Task Result: {}", result)
        task = self.running_tasks.get(result.task_id)
        if not task:
            logger.warning("Received result for unknown task: {}", result.task_id)
            return
        if task.assigned_worker != source_worker.node_id:
            logger.warning(
                "Rejected task result for task {} from unexpected worker {}",
                result.task_id,
                source_worker.node_id,
            )
            return
        if task.attempt_count != result.attempt:
            logger.warning(
                "Rejected task result for task {} with stale attempt {} (current {})",
                result.task_id,
                result.attempt,
                task.attempt_count,
            )
            return

        payload = TaskResultPayload.from_proto(result)
        source_worker.remove_task(result.task_id)
        await worker_manager.sync_worker_state(source_worker)
        self.running_tasks.pop(result.task_id, None)

        attempt = self._get_latest_attempt(task)
        if attempt:
            attempt.mark_finished()

        if task.status == TaskStatus.CANCEL_REQUESTED:
            # 取消请求态下，晚到结果只用于补全终态信息，不再把任务恢复为成功。
            if attempt:
                attempt.mark_cancelled("task cancelled while running")
            task.mark_cancelled(payload)
            await self._record_event(
                "task.cancelled",
                task=task,
                worker_id=source_worker.node_id,
                payload={"attempt": result.attempt},
            )
        elif result.succeeded:
            task.mark_succeeded(payload)
            self.metrics.task_results_total.labels(status=TaskStatus.SUCCEEDED.value).inc()
            self.metrics.task_execution_ms.observe(payload.time)
            await self._record_event(
                "task.succeeded",
                task=task,
                worker_id=source_worker.node_id,
                payload={"attempt": result.attempt},
            )
        else:
            if await self._schedule_retry_or_fail(task, "task execution failed"):
                await self._record_event(
                    "task.failed_attempt",
                    task=task,
                    worker_id=source_worker.node_id,
                    payload={"attempt": result.attempt},
                )
            else:
                task.result = payload
                task.last_error = payload.stderr.decode("utf-8", errors="replace")
                self.metrics.task_results_total.labels(status=TaskStatus.FAILED.value).inc()
                self.metrics.task_execution_ms.observe(payload.time)

        await self._persist()
        self._refresh_metrics()
        await self.notify_scheduler("task.finished")

        if task.is_terminal and task.result:
            terminal_result = task.result.to_proto(task.task_id)
            self.result.append(terminal_result)
            await self._notify_subscribers(task.task_id, terminal_result)

    async def _notify_subscribers(self, task_id: int, result: TaskResult) -> None:
        subscribers = list(self.subscribers.get(task_id, set()))
        if not subscribers:
            return
        dead_subscribers: list[WebSocket] = []
        for ws in subscribers:
            if ws.client_state != WebSocketState.CONNECTED:
                dead_subscribers.append(ws)
                continue
            try:
                await ws.send_bytes(proto2bytes(result))
            except Exception:
                dead_subscribers.append(ws)
        for ws in dead_subscribers:
            self.unsubscribe(task_id, ws)

    async def process_retry_queue(self) -> List[int]:
        ready: List[int] = []
        now = datetime.now()
        for task in self._tasks_dict.values():
            if task.status != TaskStatus.RETRY_WAIT:
                continue
            if task.next_retry_at and task.next_retry_at > now:
                continue
            # 重试定时器到点后重新入队；调度协程会被队列唤醒继续派发。
            task.mark_queued()
            self._enqueue_task(task)
            await self._record_event("task.requeued", task=task)
            ready.append(task.task_id)
        if ready:
            await self._persist()
            self._refresh_metrics()
            await self.notify_scheduler("task.retry_ready")
        return ready
