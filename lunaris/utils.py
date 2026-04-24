from lunaris.proto.client_pb2 import (
    CreateTask,
    TaskCreateFailed,
    TaskCreated,
    UnsubscribeTask,
)
from lunaris.proto.worker_pb2 import (
    Task,
    TaskAccepted,
    ControlCommand,
    NodeStatus,
    NodeRegistration,
    NodeRegistrationReply,
    UnregisterNode,
)
from lunaris.proto.common_pb2 import Envelope, TaskResult
from google.protobuf.message import Message
from typing import Any, Optional, Type
from fastapi.responses import JSONResponse
import time
import threading
import zstandard


def Rest(msg: str = "OK", status_code: int = 200, data=None):
    """Rest

    Keyword Arguments:
        msg -- 消息 (default: {"OK"})
        status_code -- 状态码 (default: {200})
        data -- 数据 (default: {None})

    Returns:
        处理后的返回字符串
    """
    ret_dict = {"msg": msg, "code": status_code, "data": data}
    req = JSONResponse(ret_dict)
    req.status_code = status_code
    req.headers["Content-Type"] = "application/json; charset=utf-8"

    return req


# 类型映射表：将Envelope.MessageType映射到对应的proto类
MESSAGE_TYPE_MAP: dict[Envelope.MessageType, Type[Message]] = {
    Envelope.MessageType.TASK: Task,
    Envelope.MessageType.TASK_RESULT: TaskResult,
    Envelope.MessageType.CONTROL_COMMAND: ControlCommand,
    Envelope.MessageType.NODE_STATUS: NodeStatus,
    Envelope.MessageType.NODE_REGISTRATION: NodeRegistration,
    Envelope.MessageType.NODE_REGISTRATION_REPLY: NodeRegistrationReply,
    Envelope.MessageType.UNREGISTER_NODE: UnregisterNode,
    Envelope.MessageType.TASK_ACCEPTED: TaskAccepted,
    Envelope.MessageType.CREATE_TASK: CreateTask,
    Envelope.MessageType.UNSUBSCRIBE_TASK: UnsubscribeTask,
    Envelope.MessageType.TASK_CREATED: TaskCreated,
    Envelope.MessageType.TASK_CREATE_FAILED: TaskCreateFailed,
}

# 类型反向映射表：将proto类映射到Envelope.MessageType
CLASS_TO_MESSAGE_TYPE: dict[Type[Message], Envelope.MessageType] = {
    v: k for k, v in MESSAGE_TYPE_MAP.items()
}


def bytes2proto(
    data: bytes,
) -> Any:
    """将字节数据转换为对应的proto对象"""
    envelope = Envelope.FromString(data)

    message_class = MESSAGE_TYPE_MAP.get(envelope.type)

    if not message_class:
        raise ValueError(f"Unknown message type: {envelope.type}")
    if envelope.compressed:
        payload = zstandard.decompress(envelope.payload)
    else:
        payload = envelope.payload
    return message_class.FromString(payload)


def proto2bytes(obj: Any, type: Optional[Envelope.MessageType] = None, compress: bool = True) -> bytes:
    """将proto对象转换为字节数据

    Args:
        obj: protobuf 消息对象
        type: 消息类型，自动推导时可为 None
        compress: 是否启用 zstd 压缩，默认 True。
                  MCU Worker 等资源受限场景可传 False 禁用压缩。

    Returns:
        序列化后的字节数据
    """
    # 检查是否是protobuf对象
    if type is None:
        message_type = CLASS_TO_MESSAGE_TYPE.get(obj.__class__)
        if not message_type:
            raise TypeError(f"Unknown message type: {obj.__class__}")
    else:
        message_type = type

    envelope = Envelope()
    envelope.type = message_type
    if compress:
        envelope.payload = zstandard.compress(obj.SerializeToString())
        envelope.compressed = True
    else:
        envelope.payload = obj.SerializeToString()
        envelope.compressed = False
    return envelope.SerializeToString()


class IDGenerator:
    """Snowflake ID 生成器

    基于 Twitter Snowflake 算法的分布式 ID 生成器。
    生成 64 位唯一 ID，包含时间戳、Worker ID 和序列号。

    ID 结构（64 位）：
        - 1 位：符号位（固定为 0）
        - 41 位：时间戳（毫秒，相对于 EPOCH）
        - 10 位：Worker ID（支持 0-1023）
        - 12 位：序列号（每毫秒支持 4096 个 ID）

    特性：
        - 全局唯一：时间戳 + Worker ID + 序列号保证唯一性
        - 趋势递增：ID 大致按时间递增
        - 高性能：单机每毫秒可生成 4096 个 ID
        - 线程安全：使用锁保护生成过程

    常量说明：
        ID_BITS: Worker ID 位数（10 位，支持 1024 个 Worker）
        SEQUENCE_BITS: 序列号位数（12 位，每毫秒 4096 个）
        MAX_ID: 最大 Worker ID（1023）
        ID_SHIFT: Worker ID 左移位数
        TIMESTAMP_SHIFT: 时间戳左移位数
        SEQUENCE_MASK: 序列号掩码
        EPOCH: 起始时间戳（2024-06-19 00:00:00 UTC）

    Examples:
        >>> generator = IDGenerator(worker_id=1)
        >>> task_id = generator.get_id()
        >>> print(task_id)  # "1234567890123456789"
    """
    # Worker ID 位数：10 位，支持 1024 个 Worker（0-1023）
    ID_BITS = 10
    # 序列号位数：12 位，每毫秒支持 4096 个 ID
    SEQUENCE_BITS = 12
    # 最大 Worker ID：2^10 - 1 = 1023
    MAX_ID = -1 ^ (-1 << ID_BITS)
    # Worker ID 左移位数：12 位（序列号占用的位数）
    ID_SHIFT = SEQUENCE_BITS
    # 时间戳左移位数：22 位（序列号 + Worker ID 占用的位数）
    TIMESTAMP_SHIFT = SEQUENCE_BITS + ID_BITS
    # 序列号掩码：低 12 位全 1
    SEQUENCE_MASK = -1 ^ (-1 << SEQUENCE_BITS)
    # 起始时间戳：2024-06-19 00:00:00 UTC（Firefly 发布日期）
    EPOCH = 1718766000000

    def __init__(self, id: int):
        """初始化 ID 生成器

        Args:
            id: Worker ID，范围 0-1023

        Raises:
            ValueError: Worker ID 超出范围

        Examples:
            >>> generator = IDGenerator(1)  # Worker ID 为 1
        """
        if not (0 <= id <= self.MAX_ID):
            raise ValueError(f"Worker ID must be between 0 and {self.MAX_ID}")
        self.id = id
        self.last_timestamp = -1
        self.sequence = 0
        self.lock = threading.Lock()

    def get_id(self) -> str:
        """生成唯一 ID

        生成 64 位 Snowflake ID 并返回字符串格式。

        Returns:
            字符串格式的唯一 ID

        Raises:
            Exception: 时钟回拨（当前时间小于上次生成时间）

        Note:
            - 同一毫秒内序列号递增
            - 序列号溢出时等待下一毫秒
            - 不同毫秒序列号重置为 0

        Examples:
            >>> generator = IDGenerator(1)
            >>> id1 = generator.get_id()
            >>> id2 = generator.get_id()
            >>> assert id1 != id2  # 保证唯一性
        """
        with self.lock:
            timestamp = self._current_millis()
            # 检测时钟回拨
            if timestamp < self.last_timestamp:
                raise Exception("Clock moved backwards!")
            # 同一毫秒内序列号递增
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
                if self.sequence == 0:
                    # 序列号溢出，等待下一毫秒
                    timestamp = self._wait_for_next_millis(self.last_timestamp)
            else:
                # 不同毫秒，序列号重置
                self.sequence = 0
            self.last_timestamp = timestamp
            # 组合 ID：时间戳 | Worker ID | 序列号
            new_id = (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.id << self.ID_SHIFT)
                | self.sequence
            )
            return str(new_id)

    def _current_millis(self) -> int:
        """获取当前时间戳（毫秒）

        Returns:
            当前 Unix 时间戳（毫秒）
        """
        return int(time.time() * 1000)

    def _wait_for_next_millis(self, last_timestamp: int) -> int:
        """等待下一毫秒

        当序列号溢出时，阻塞直到时间戳变化。

        Args:
            last_timestamp: 上次生成的时间戳

        Returns:
            新的时间戳（大于 last_timestamp）
        """
        timestamp = self._current_millis()
        while timestamp <= last_timestamp:
            timestamp = self._current_millis()
        return timestamp
