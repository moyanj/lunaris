from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Union
from datetime import datetime
from lunaris.master import id_gen
from lunaris.proto import common_pb2
from lunaris.runtime import ExecutionLimits


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class Task(BaseModel):
    wasm_module: bytes
    entry: str = "main"
    task_id: str = Field(default_factory=id_gen.get_id)
    args: list = Field(default_factory=list)
    priority: int = 0
    wasi_env: dict[str, Union[dict[str, str], list[str]]] = Field(default_factory=dict)
    execution_limits: dict[str, int] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    attempt_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        return {
            "wasm_module_size": len(self.wasm_module),
            "entry": self.entry,
            "task_id": self.task_id,
            "args": self.args,
            "priority": self.priority,
            "execution_limits": self.execution_limits,
            "status": self.status,
            "assigned_worker": self.assigned_worker,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "lease_expires_at": (
                self.lease_expires_at.isoformat() if self.lease_expires_at else None
            ),
            "attempt_count": self.attempt_count,
            "retry_count": max(0, self.attempt_count - 1),
            "max_retries": self.max_retries,
        }

    def __lt__(self, other):
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        return me < them

    def __gt__(self, other):
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        return me > them

    def assign_to_worker(self, worker_id: str, lease_expires_at: datetime):
        """将任务分配给worker"""
        self.attempt_count += 1
        self.status = TaskStatus.ASSIGNED
        self.assigned_worker = worker_id
        self.assigned_at = datetime.now()
        self.lease_expires_at = lease_expires_at

    def mark_running(self):
        """标记任务开始运行"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        self.lease_expires_at = None

    def mark_completed(self):
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.lease_expires_at = None

    def mark_failed(self):
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.lease_expires_at = None

    def reset_for_retry(self):
        """重新放回待调度状态。"""
        self.status = TaskStatus.PENDING
        self.assigned_worker = None  # 重置worker分配
        self.assigned_at = None
        self.lease_expires_at = None
        self.started_at = None  # 重置开始时间

    @property
    def can_retry(self) -> bool:
        """max_retries 表示首次执行之外允许的重试次数。"""
        return self.attempt_count <= self.max_retries
