from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Envelope(_message.Message):
    __slots__ = ("type", "payload", "compressed")
    class MessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TASK: _ClassVar[Envelope.MessageType]
        TASK_RESULT: _ClassVar[Envelope.MessageType]
        CONTROL_COMMAND: _ClassVar[Envelope.MessageType]
        NODE_STATUS: _ClassVar[Envelope.MessageType]
        NODE_REGISTRATION: _ClassVar[Envelope.MessageType]
        NODE_REGISTRATION_REPLY: _ClassVar[Envelope.MessageType]
        UNREGISTER_NODE: _ClassVar[Envelope.MessageType]
        CREATE_TASK: _ClassVar[Envelope.MessageType]
        UNSUBSCRIBE_TASK: _ClassVar[Envelope.MessageType]
        TASK_CREATED: _ClassVar[Envelope.MessageType]
    TASK: Envelope.MessageType
    TASK_RESULT: Envelope.MessageType
    CONTROL_COMMAND: Envelope.MessageType
    NODE_STATUS: Envelope.MessageType
    NODE_REGISTRATION: Envelope.MessageType
    NODE_REGISTRATION_REPLY: Envelope.MessageType
    UNREGISTER_NODE: Envelope.MessageType
    CREATE_TASK: Envelope.MessageType
    UNSUBSCRIBE_TASK: Envelope.MessageType
    TASK_CREATED: Envelope.MessageType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    COMPRESSED_FIELD_NUMBER: _ClassVar[int]
    type: Envelope.MessageType
    payload: bytes
    compressed: bool
    def __init__(self, type: _Optional[_Union[Envelope.MessageType, str]] = ..., payload: _Optional[bytes] = ..., compressed: _Optional[bool] = ...) -> None: ...

class TaskResult(_message.Message):
    __slots__ = ("task_id", "result", "stdout", "stderr", "time", "succeeded")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    STDOUT_FIELD_NUMBER: _ClassVar[int]
    STDERR_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    SUCCEEDED_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    result: str
    stdout: bytes
    stderr: bytes
    time: float
    succeeded: bool
    def __init__(self, task_id: _Optional[str] = ..., result: _Optional[str] = ..., stdout: _Optional[bytes] = ..., stderr: _Optional[bytes] = ..., time: _Optional[float] = ..., succeeded: _Optional[bool] = ...) -> None: ...
