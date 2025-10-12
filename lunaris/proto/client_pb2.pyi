from lunaris.proto import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateTask(_message.Message):
    __slots__ = ("wasm_module", "args", "entry", "priority", "wasi_env")
    WASM_MODULE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    WASI_ENV_FIELD_NUMBER: _ClassVar[int]
    wasm_module: bytes
    args: str
    entry: str
    priority: int
    wasi_env: _common_pb2.WasiEnv
    def __init__(self, wasm_module: _Optional[bytes] = ..., args: _Optional[str] = ..., entry: _Optional[str] = ..., priority: _Optional[int] = ..., wasi_env: _Optional[_Union[_common_pb2.WasiEnv, _Mapping]] = ...) -> None: ...

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
