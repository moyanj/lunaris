from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os
import orjson

from lunaris.master.model import Task, TaskAttempt, TaskEvent, WorkerRecord
from lunaris.master.store_base import StateStore


class FileStateStore(StateStore):
    """文件后端：单 master 下用快照 + 事件日志保存控制面状态。"""

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.root / "state.json"
        self.events_path = self.root / "events.jsonl"
        self.tasks: dict[int, Task] = {}
        self.attempts: dict[str, TaskAttempt] = {}
        self.workers: dict[str, WorkerRecord] = {}
        self.task_events: dict[int, list[TaskEvent]] = defaultdict(list)
        self.events: list[TaskEvent] = []
        self.idempotency_index: dict[str, int] = {}
        self._next_seq = 1
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def load(self) -> None:
        # 单 master 模式下，以快照作为当前状态源，事件日志只用于恢复历史事件与订阅游标。
        if self.snapshot_path.exists():
            async with aiofiles.open(self.snapshot_path, "rb") as f:
                payload = orjson.loads(await f.read())
            self.tasks.clear()
            self.tasks.update(
                {
                    int(task_id): Task.from_snapshot(task_data)
                    for task_id, task_data in payload.get("tasks", {}).items()
                }
            )
            self.attempts.clear()
            self.attempts.update(
                {
                    attempt_id: TaskAttempt.from_snapshot(attempt_data)
                    for attempt_id, attempt_data in payload.get("attempts", {}).items()
                }
            )
            self.workers.clear()
            self.workers.update(
                {
                    worker_id: WorkerRecord.from_snapshot(worker_data)
                    for worker_id, worker_data in payload.get("workers", {}).items()
                }
            )
            self.idempotency_index = {
                key: int(task_id)
                for key, task_id in payload.get("idempotency_index", {}).items()
            }

        if self.events_path.exists():
            self.task_events.clear()
            self.events.clear()
            async with aiofiles.open(self.events_path, "r", encoding="utf-8") as f:
                content = await f.read()
            for line in content.splitlines():
                if not line:
                    continue
                event = TaskEvent.from_snapshot(orjson.loads(line))
                self.events.append(event)
                if event.task_id is not None:
                    self.task_events[event.task_id].append(event)
                self._next_seq = max(self._next_seq, event.seq + 1)

    async def persist(self) -> None:
        async with self.lock:
            # 使用原子替换写快照，避免进程中断后留下半写入文件。
            payload = {
                "tasks": {
                    str(task_id): task.to_snapshot() for task_id, task in self.tasks.items()
                },
                "attempts": {
                    attempt_id: attempt.to_snapshot()
                    for attempt_id, attempt in self.attempts.items()
                },
                "workers": {
                    worker_id: worker.to_snapshot()
                    for worker_id, worker in self.workers.items()
                },
                "idempotency_index": {
                    key: task_id for key, task_id in self.idempotency_index.items()
                },
            }
            tmp_path = self.snapshot_path.with_suffix(".tmp")
            async with aiofiles.open(tmp_path, "wb") as f:
                await f.write(orjson.dumps(payload))
            await aiofiles.os.replace(str(tmp_path), str(self.snapshot_path))

    async def append_event(
        self,
        event_type: str,
        *,
        task_id: Optional[int] = None,
        worker_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> TaskEvent:
        async with self.lock:
            # 事件日志采用追加写，供轮询/订阅接口读取状态变化轨迹。
            event = TaskEvent(
                seq=self._next_seq,
                event_type=event_type,
                task_id=task_id,
                worker_id=worker_id,
                payload=payload or {},
            )
            self._next_seq += 1
            self.events.append(event)
            if task_id is not None:
                self.task_events[task_id].append(event)
            async with aiofiles.open(self.events_path, "ab") as f:
                await f.write(orjson.dumps(event.to_snapshot()))
                await f.write(b"\n")
            return event

    def get_task_events(self, task_id: int, after_seq: int = 0) -> list[TaskEvent]:
        events = self.task_events.get(task_id, [])
        return [event for event in events if event.seq > after_seq]
