from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from lunaris.master.model import Task, TaskAttempt, TaskEvent, WorkerRecord


class StateStore(ABC):
    """状态存储抽象，允许后续替换为其他单 master 后端实现。"""

    tasks: dict[str, Task]
    attempts: dict[str, TaskAttempt]
    workers: dict[str, WorkerRecord]
    idempotency_index: dict[str, str]

    @abstractmethod
    async def load(self) -> None:
        """从后端加载当前快照。"""

    @abstractmethod
    async def persist(self) -> None:
        """把当前内存状态落盘到后端。"""

    @abstractmethod
    async def append_event(
        self,
        event_type: str,
        *,
        task_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> TaskEvent:
        """追加事件日志，用于订阅和恢复。"""

    @abstractmethod
    def get_task_events(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        """返回指定任务的增量事件。"""
