from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class CreateTask(_message.Message):
    __slots__ = ("wasm_module", "args", "entry", "priority")
    WASM_MODULE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    wasm_module: bytes
    args: str
    entry: str
    priority: int
    def __init__(self, wasm_module: _Optional[bytes] = ..., args: _Optional[str] = ..., entry: _Optional[str] = ..., priority: _Optional[int] = ...) -> None: ...

class TaskCreated(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...

class UnsubscribeTask(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, task_id: _Optional[_Iterable[str]] = ...) -> None: ...
