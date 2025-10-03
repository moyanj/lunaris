from lunaris.proto.client_pb2 import CreateTask, UnsubscribeTask
from lunaris.proto.worker_pb2 import (
    Task,
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
    Envelope.MessageType.CREATE_TASK: CreateTask,
    Envelope.MessageType.UNSUBSCRIBE_TASK: UnsubscribeTask,
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

    return message_class.FromString(envelope.payload)


def proto2bytes(obj: Any, type: Optional[Envelope.MessageType] = None) -> bytes:
    """将proto对象转换为字节数据"""
    # 检查是否是protobuf对象
    if type is None:
        message_type = CLASS_TO_MESSAGE_TYPE.get(obj.__class__)
        if not message_type:
            raise TypeError(f"Unknown message type: {obj.__class__}")
    else:
        message_type = type

    envelope = Envelope()
    envelope.type = message_type
    envelope.payload = obj.SerializeToString()
    return envelope.SerializeToString()


class IDGenerator:
    ID_BITS = 10
    SEQUENCE_BITS = 12
    MAX_ID = -1 ^ (-1 << ID_BITS)
    ID_SHIFT = SEQUENCE_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + ID_BITS
    SEQUENCE_MASK = -1 ^ (-1 << SEQUENCE_BITS)
    EPOCH = 1718766000000

    def __init__(self, id):
        if not (0 <= id <= self.MAX_ID):
            raise ValueError(f"Worker ID must be between 0 and {self.MAX_ID}")
        self.id = id
        self.last_timestamp = -1
        self.sequence = 0
        self.lock = threading.Lock()

    def get_id(self):
        with self.lock:
            timestamp = self._current_millis()
            if timestamp < self.last_timestamp:
                raise Exception("Clock moved backwards!")
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
                if self.sequence == 0:
                    timestamp = self._wait_for_next_millis(self.last_timestamp)
            else:
                self.sequence = 0
            self.last_timestamp = timestamp
            new_id = (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.id << self.ID_SHIFT)
                | self.sequence
            )
            return str(new_id)

    def _current_millis(self):
        return int(time.time() * 1000)

    def _wait_for_next_millis(self, last_timestamp):
        timestamp = self._current_millis()
        while timestamp <= last_timestamp:
            timestamp = self._current_millis()
        return timestamp
