"""
Master 数据模型模块

定义 Master 节点的数据模型，包括任务状态、尝试状态、Worker 状态等枚举，
以及任务、Worker 记录等数据类。

主要组件：
    - TaskStatus: 任务生命周期状态枚举
    - AttemptStatus: 任务尝试状态枚举
    - WorkerStatus: Worker 节点状态枚举
    - TaskResultPayload: 任务执行结果载荷
    - TaskAttempt: 任务尝试记录
    - WorkerRecord: Worker 节点记录
    - TaskEvent: 任务事件记录
    - Task: 任务完整信息

状态流转：
    TaskStatus: CREATED → QUEUED → LEASED → RUNNING → SUCCEEDED/FAILED
    AttemptStatus: DISPATCHED → ACCEPTED → RUNNING → FINISHED/LOST/CANCELLED
    WorkerStatus: ACTIVE → DRAINING → OFFLINE/LOST
"""
import base64
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field

from lunaris.master import id_gen
from lunaris.proto.common_pb2 import TaskResult


def _now() -> datetime:
    """获取当前时间

    Returns:
        当前 datetime 对象
    """
    return datetime.now()


def _encode_bytes(value: bytes) -> str:
    """将字节编码为 Base64 字符串

    Args:
        value: 要编码的字节数据

    Returns:
        Base64 编码的字符串
    """
    return base64.b64encode(value).decode("ascii")


def _decode_bytes(value: str) -> bytes:
    """将 Base64 字符串解码为字节

    Args:
        value: Base64 编码的字符串

    Returns:
        解码后的字节数据，空字符串返回 b""
    """
    if not value:
        return b""
    return base64.b64decode(value.encode("ascii"))


class TaskStatus(str, Enum):
    """任务状态枚举

    定义任务的完整生命周期状态。

    状态流转：
        CREATED → QUEUED → LEASED → RUNNING → SUCCEEDED/FAILED
        特殊状态：RETRY_WAIT（重试等待）、CANCEL_REQUESTED（取消请求）、CANCELLED（已取消）

    Attributes:
        CREATED: 已创建，初始状态
        QUEUED: 排队中，等待分配 Worker
        LEASED: 已分配给 Worker，等待执行
        RUNNING: 运行中，Worker 正在执行
        RETRY_WAIT: 重试等待，执行失败后等待重试
        CANCEL_REQUESTED: 取消请求，等待 Worker 确认
        CANCELLED: 已取消
        SUCCEEDED: 执行成功
        FAILED: 执行失败（达到最大重试次数）
    """
    CREATED = "created"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AttemptStatus(str, Enum):
    """任务尝试状态枚举

    定义单次任务尝试的状态。

    状态流转：
        DISPATCHED → ACCEPTED → RUNNING → FINISHED/LOST/CANCELLED

    Attributes:
        DISPATCHED: 已派发，发送给 Worker
        ACCEPTED: 已接受，Worker 确认接收
        RUNNING: 运行中，Worker 正在执行
        FINISHED: 已完成，执行成功或失败
        LOST: 丢失，Worker 断开连接
        CANCELLED: 已取消，任务被取消
    """
    DISPATCHED = "dispatched"
    ACCEPTED = "accepted"
    RUNNING = "running"
    FINISHED = "finished"
    LOST = "lost"
    CANCELLED = "cancelled"


class WorkerStatus(str, Enum):
    """Worker 节点状态枚举

    定义 Worker 节点的运行状态。

    Attributes:
        ACTIVE: 活跃，正常接收任务
        DRAINING: 排空，不接收新任务，等待现有任务完成
        OFFLINE: 离线，主动断开连接
        LOST: 丢失，心跳超时断开
    """
    ACTIVE = "active"
    DRAINING = "draining"
    OFFLINE = "offline"
    LOST = "lost"


class TaskResultPayload(BaseModel):
    """任务执行结果载荷

    包含任务执行的输出、耗时和状态。

    Attributes:
        result: 函数返回值（JSON 字符串）
        stdout: 标准输出内容（字节）
        stderr: 标准错误输出内容（字节）
        time: 执行耗时（毫秒）
        succeeded: 是否执行成功
        attempt: 任务尝试次数

    Examples:
        >>> payload = TaskResultPayload(result='"hello"', succeeded=True, time=1.5)
        >>> proto = payload.to_proto(task_id=123)
    """
    result: str = ""
    stdout: bytes = b""
    stderr: bytes = b""
    time: float = 0
    succeeded: bool = False
    attempt: int = 0

    @classmethod
    def from_proto(cls, proto: TaskResult) -> "TaskResultPayload":
        """从 Protobuf 消息创建

        Args:
            proto: TaskResult Protobuf 消息

        Returns:
            TaskResultPayload 实例
        """
        return cls(
            result=proto.result,
            stdout=proto.stdout,
            stderr=proto.stderr,
            time=proto.time,
            succeeded=proto.succeeded,
            attempt=proto.attempt,
        )

    def to_proto(self, task_id: int) -> TaskResult:
        """转换为 Protobuf 消息

        Args:
            task_id: 任务 ID

        Returns:
            TaskResult Protobuf 消息
        """
        return TaskResult(
            task_id=task_id,
            result=self.result,
            stdout=self.stdout,
            stderr=self.stderr,
            time=self.time,
            succeeded=self.succeeded,
            attempt=self.attempt,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式

        Returns:
            包含所有字段的字典，输出同时提供 UTF-8 和 Base64 编码
        """
        return {
            "result": self.result,
            "stdout": self.stdout.decode("utf-8", errors="replace"),
            "stderr": self.stderr.decode("utf-8", errors="replace"),
            "stdout_b64": _encode_bytes(self.stdout),
            "stderr_b64": _encode_bytes(self.stderr),
            "time": self.time,
            "succeeded": self.succeeded,
            "attempt": self.attempt,
        }

    def to_snapshot(self) -> dict[str, Any]:
        """转换为快照格式（用于持久化）

        Returns:
            包含所有字段的字典，输出使用 Base64 编码
        """
        return {
            "result": self.result,
            "stdout": _encode_bytes(self.stdout),
            "stderr": _encode_bytes(self.stderr),
            "time": self.time,
            "succeeded": self.succeeded,
            "attempt": self.attempt,
        }

    @classmethod
    def from_snapshot(cls, data: Optional[dict[str, Any]]) -> Optional["TaskResultPayload"]:
        if not data:
            return None
        return cls(
            result=data.get("result", ""),
            stdout=_decode_bytes(data.get("stdout", "")),
            stderr=_decode_bytes(data.get("stderr", "")),
            time=float(data.get("time", 0)),
            succeeded=bool(data.get("succeeded", False)),
            attempt=int(data.get("attempt", 0)),
        )


class TaskAttempt(BaseModel):
    attempt_id: str = Field(default_factory=id_gen.get_id)
    task_id: int
    attempt_no: int
    worker_id: str
    status: AttemptStatus = AttemptStatus.DISPATCHED
    dispatched_at: datetime = Field(default_factory=_now)
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    error: Optional[str] = None

    def mark_running(self) -> None:
        now = _now()
        self.status = AttemptStatus.RUNNING
        if self.accepted_at is None:
            self.accepted_at = now
        self.started_at = now
        self.lease_expires_at = None

    def mark_lost(self, reason: str) -> None:
        self.status = AttemptStatus.LOST
        self.finished_at = _now()
        self.error = reason
        self.lease_expires_at = None

    def mark_finished(self) -> None:
        self.status = AttemptStatus.FINISHED
        self.finished_at = _now()
        self.lease_expires_at = None

    def mark_cancelled(self, reason: str) -> None:
        self.status = AttemptStatus.CANCELLED
        self.finished_at = _now()
        self.error = reason
        self.lease_expires_at = None

    def to_snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "TaskAttempt":
        return cls.model_validate(data)


class WorkerRecord(BaseModel):
    worker_id: str
    name: str
    arch: str
    max_concurrency: int
    memory_size: int
    status: WorkerStatus = WorkerStatus.ACTIVE
    drain: bool = False
    capacity_used: int = 0
    current_tasks: list[int] = Field(default_factory=list)
    provided_capabilities: list[str] = Field(default_factory=list)
    last_heartbeat: datetime = Field(default_factory=_now)
    connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "arch": self.arch,
            "max_concurrency": self.max_concurrency,
            "memory_size": self.memory_size,
            "status": self.status.value,
            "drain": self.drain,
            "capacity_used": self.capacity_used,
            "current_tasks": self.current_tasks,
            "provided_capabilities": self.provided_capabilities,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "connected": self.connected,
        }

    def to_snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "WorkerRecord":
        return cls.model_validate(data)


class TaskEvent(BaseModel):
    seq: int
    event_type: str
    created_at: datetime = Field(default_factory=_now)
    task_id: Optional[int] = None
    worker_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat(),
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "payload": self.payload,
        }

    def to_snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "TaskEvent":
        return cls.model_validate(data)


class Task(BaseModel):
    wasm_module: bytes
    entry: str = "main"
    task_id: int = Field(default_factory=lambda: int(id_gen.get_id()))
    idempotency_key: Optional[str] = None
    args: list = Field(default_factory=list)
    priority: int = 0
    wasi_env: dict[str, Union[dict[str, str], list[str]]] = Field(default_factory=dict)
    execution_limits: dict[str, int] = Field(default_factory=dict)
    host_capabilities: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.CREATED
    assigned_worker: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None
    attempt_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    cancel_requested_at: Optional[datetime] = None
    last_error: Optional[str] = None
    result: Optional[TaskResultPayload] = None
    latest_attempt_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "wasm_module_size": len(self.wasm_module),
            "entry": self.entry,
            "task_id": self.task_id,
            "idempotency_key": self.idempotency_key,
            "args": self.args,
            "priority": self.priority,
            "execution_limits": self.execution_limits,
            "host_capabilities": self.host_capabilities,
            "status": self.status.value,
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
            "next_retry_at": (
                self.next_retry_at.isoformat() if self.next_retry_at else None
            ),
            "cancel_requested_at": (
                self.cancel_requested_at.isoformat()
                if self.cancel_requested_at
                else None
            ),
            "attempt_count": self.attempt_count,
            "retry_count": max(0, self.attempt_count - 1),
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "result": self.result.to_dict() if self.result else None,
        }

    def to_snapshot(self) -> dict[str, Any]:
        # wasm 二进制不能走 pydantic 的 JSON bytes 序列化，否则会被误按 UTF-8 解码。
        data = self.model_dump(mode="json", exclude={"result", "wasm_module"})
        data["wasm_module"] = _encode_bytes(self.wasm_module)
        data["result"] = self.result.to_snapshot() if self.result else None
        return data

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "Task":
        snapshot = dict(data)
        snapshot["wasm_module"] = _decode_bytes(snapshot.get("wasm_module", ""))
        snapshot["result"] = TaskResultPayload.from_snapshot(snapshot.get("result"))
        return cls.model_validate(snapshot)

    def __lt__(self, other: "Task") -> bool:
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        return me < them

    def __gt__(self, other: "Task") -> bool:
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        return me > them

    def mark_queued(self) -> None:
        self.status = TaskStatus.QUEUED
        self.assigned_worker = None
        self.assigned_at = None
        self.lease_expires_at = None
        self.next_retry_at = None
        self.latest_attempt_id = None

    def assign_to_worker(self, worker_id: str, lease_expires_at: datetime) -> None:
        self.attempt_count += 1
        self.status = TaskStatus.LEASED
        self.assigned_worker = worker_id
        self.assigned_at = _now()
        self.lease_expires_at = lease_expires_at
        self.next_retry_at = None
        self.last_error = None

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = _now()
        self.lease_expires_at = None

    def mark_cancel_requested(self) -> None:
        if self.status in {
            TaskStatus.CANCELLED,
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
        }:
            return
        self.status = TaskStatus.CANCEL_REQUESTED
        self.cancel_requested_at = _now()

    def mark_succeeded(self, result: TaskResultPayload) -> None:
        self.status = TaskStatus.SUCCEEDED
        self.completed_at = _now()
        self.lease_expires_at = None
        self.last_error = None
        self.result = result

    def mark_failed(
        self,
        result: Optional[TaskResultPayload] = None,
        error: Optional[str] = None,
    ) -> None:
        self.status = TaskStatus.FAILED
        self.completed_at = _now()
        self.lease_expires_at = None
        self.last_error = error or (result.stderr.decode("utf-8", errors="replace") if result else None)
        self.result = result

    def mark_cancelled(self, result: Optional[TaskResultPayload] = None) -> None:
        self.status = TaskStatus.CANCELLED
        self.completed_at = _now()
        self.lease_expires_at = None
        self.result = result or TaskResultPayload(
            result="",
            stdout=b"",
            stderr=b"task cancelled",
            time=0,
            succeeded=False,
            attempt=self.attempt_count,
        )

    def schedule_retry(self, delay_seconds: int, reason: str) -> None:
        self.status = TaskStatus.RETRY_WAIT
        self.assigned_worker = None
        self.assigned_at = None
        self.lease_expires_at = None
        self.started_at = None
        self.next_retry_at = _now() + timedelta(seconds=delay_seconds)
        self.last_error = reason
        self.latest_attempt_id = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.CANCELLED,
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
        }

    @property
    def can_retry(self) -> bool:
        return self.attempt_count <= self.max_retries
