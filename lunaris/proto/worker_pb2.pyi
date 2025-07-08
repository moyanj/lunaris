from proto import common_pb2 as _common_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Task(_message.Message):
    __slots__ = ("task_id", "code", "args", "lua_version", "priority")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    LUA_VERSION_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    code: str
    args: str
    lua_version: _common_pb2.LuaVersion
    priority: int
    def __init__(self, task_id: _Optional[str] = ..., code: _Optional[str] = ..., args: _Optional[str] = ..., lua_version: _Optional[_Union[_common_pb2.LuaVersion, str]] = ..., priority: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("name", "os", "arch", "max_concurrency", "num_cpu", "memory_size")
    NAME_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    ARCH_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENCY_FIELD_NUMBER: _ClassVar[int]
    NUM_CPU_FIELD_NUMBER: _ClassVar[int]
    MEMORY_SIZE_FIELD_NUMBER: _ClassVar[int]
    name: str
    os: str
    arch: str
    max_concurrency: int
    num_cpu: int
    memory_size: int
    def __init__(self, name: _Optional[str] = ..., os: _Optional[str] = ..., arch: _Optional[str] = ..., max_concurrency: _Optional[int] = ..., num_cpu: _Optional[int] = ..., memory_size: _Optional[int] = ...) -> None: ...

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
