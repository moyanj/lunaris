from lunaris.proto.task_pb2 import (
    Envelope,
    Task,
    TaskResult,
    ControlCommand,
    NodeStatus,
    NodeRegistration,
    NodeRegistrationReply,
)
from google.protobuf.message import Message
from typing import Any, Optional, Type
from fastapi.responses import JSONResponse


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
