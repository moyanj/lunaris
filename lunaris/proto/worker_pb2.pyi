from lunaris.proto import common_pb2 as _common_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Task(_message.Message):
    __slots__ = ("task_id", "wasm_module", "args", "entry", "priority", "wasi_env", "execution_limits", "attempt")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    WASM_MODULE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    WASI_ENV_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_LIMITS_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    wasm_module: bytes
    args: str
    entry: str
    priority: int
    wasi_env: _common_pb2.WasiEnv
    execution_limits: _common_pb2.ExecutionLimits
    attempt: int
    def __init__(self, task_id: _Optional[str] = ..., wasm_module: _Optional[bytes] = ..., args: _Optional[str] = ..., entry: _Optional[str] = ..., priority: _Optional[int] = ..., wasi_env: _Optional[_Union[_common_pb2.WasiEnv, _Mapping]] = ..., execution_limits: _Optional[_Union[_common_pb2.ExecutionLimits, _Mapping]] = ..., attempt: _Optional[int] = ...) -> None: ...

class TaskAccepted(_message.Message):
    __slots__ = ("task_id", "node_id", "attempt")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    node_id: str
    attempt: int
    def __init__(self, task_id: _Optional[str] = ..., node_id: _Optional[str] = ..., attempt: _Optional[int] = ...) -> None: ...

class ControlCommand(_message.Message):
    __slots__ = ("type", "data")
    class CommandType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HEARTBEAT: _ClassVar[ControlCommand.CommandType]
        SHUTDOWN: _ClassVar[ControlCommand.CommandType]
    HEARTBEAT: ControlCommand.CommandType
    SHUTDOWN: ControlCommand.CommandType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    type: ControlCommand.CommandType
    data: str
    def __init__(self, type: _Optional[_Union[ControlCommand.CommandType, str]] = ..., data: _Optional[str] = ...) -> None: ...

class NodeStatus(_message.Message):
    __slots__ = ("node_id", "status", "current_task")
    class NodeState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        IDLE: _ClassVar[NodeStatus.NodeState]
        BUSY: _ClassVar[NodeStatus.NodeState]
    IDLE: NodeStatus.NodeState
    BUSY: NodeStatus.NodeState
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_TASK_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    status: NodeStatus.NodeState
    current_task: int
    def __init__(self, node_id: _Optional[str] = ..., status: _Optional[_Union[NodeStatus.NodeState, str]] = ..., current_task: _Optional[int] = ...) -> None: ...

class NodeRegistration(_message.Message):
    __slots__ = ("name", "arch", "max_concurrency", "memory_size", "token")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ARCH_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENCY_FIELD_NUMBER: _ClassVar[int]
    MEMORY_SIZE_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    name: str
    arch: str
    max_concurrency: int
    memory_size: int
    token: str
    def __init__(self, name: _Optional[str] = ..., arch: _Optional[str] = ..., max_concurrency: _Optional[int] = ..., memory_size: _Optional[int] = ..., token: _Optional[str] = ...) -> None: ...

class NodeRegistrationReply(_message.Message):
    __slots__ = ("node_id",)
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    def __init__(self, node_id: _Optional[str] = ...) -> None: ...

class UnregisterNode(_message.Message):
    __slots__ = ("node_id",)
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    def __init__(self, node_id: _Optional[str] = ...) -> None: ...
