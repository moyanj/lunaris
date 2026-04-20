from lunaris.proto import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateTask(_message.Message):
    __slots__ = ("wasm_module", "args", "entry", "priority", "wasi_env", "execution_limits", "request_id", "idempotency_key", "host_capabilities")
    WASM_MODULE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    WASI_ENV_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_LIMITS_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    HOST_CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    wasm_module: bytes
    args: str
    entry: str
    priority: int
    wasi_env: _common_pb2.WasiEnv
    execution_limits: _common_pb2.ExecutionLimits
    request_id: str
    idempotency_key: str
    host_capabilities: _common_pb2.HostCapabilities
    def __init__(self, wasm_module: _Optional[bytes] = ..., args: _Optional[str] = ..., entry: _Optional[str] = ..., priority: _Optional[int] = ..., wasi_env: _Optional[_Union[_common_pb2.WasiEnv, _Mapping]] = ..., execution_limits: _Optional[_Union[_common_pb2.ExecutionLimits, _Mapping]] = ..., request_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., host_capabilities: _Optional[_Union[_common_pb2.HostCapabilities, _Mapping]] = ...) -> None: ...

class TaskCreated(_message.Message):
    __slots__ = ("task_id", "request_id")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: int
    request_id: str
    def __init__(self, task_id: _Optional[int] = ..., request_id: _Optional[str] = ...) -> None: ...

class TaskCreateFailed(_message.Message):
    __slots__ = ("error", "request_id")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    error: str
    request_id: str
    def __init__(self, error: _Optional[str] = ..., request_id: _Optional[str] = ...) -> None: ...

class UnsubscribeTask(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, task_id: _Optional[_Iterable[int]] = ...) -> None: ...
