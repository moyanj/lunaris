from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Envelope(_message.Message):
    __slots__ = ("type", "payload")
    class MessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TASK: _ClassVar[Envelope.MessageType]
        TASK_RESULT: _ClassVar[Envelope.MessageType]
        CONTROL_COMMAND: _ClassVar[Envelope.MessageType]
        NODE_STATUS: _ClassVar[Envelope.MessageType]
        NODE_REGISTRATION: _ClassVar[Envelope.MessageType]
        NODE_REGISTRATION_REPLY: _ClassVar[Envelope.MessageType]
    TASK: Envelope.MessageType
    TASK_RESULT: Envelope.MessageType
    CONTROL_COMMAND: Envelope.MessageType
    NODE_STATUS: Envelope.MessageType
    NODE_REGISTRATION: Envelope.MessageType
    NODE_REGISTRATION_REPLY: Envelope.MessageType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    type: Envelope.MessageType
    payload: bytes
    def __init__(self, type: _Optional[_Union[Envelope.MessageType, str]] = ..., payload: _Optional[bytes] = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("task_id", "code", "args", "lua_version", "priority")
    class LuaVersion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        Lua54: _ClassVar[Task.LuaVersion]
        Lua51: _ClassVar[Task.LuaVersion]
        Lua52: _ClassVar[Task.LuaVersion]
        Lua53: _ClassVar[Task.LuaVersion]
        LuaJIT20: _ClassVar[Task.LuaVersion]
        LuaJIT21: _ClassVar[Task.LuaVersion]
    Lua54: Task.LuaVersion
    Lua51: Task.LuaVersion
    Lua52: Task.LuaVersion
    Lua53: Task.LuaVersion
    LuaJIT20: Task.LuaVersion
    LuaJIT21: Task.LuaVersion
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    LUA_VERSION_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    code: str
    args: str
    lua_version: Task.LuaVersion
    priority: int
    def __init__(self, task_id: _Optional[str] = ..., code: _Optional[str] = ..., args: _Optional[str] = ..., lua_version: _Optional[_Union[Task.LuaVersion, str]] = ..., priority: _Optional[int] = ...) -> None: ...

class TaskResult(_message.Message):
    __slots__ = ("task_id", "status", "result", "stdout", "stderr", "time")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SUCCESS: _ClassVar[TaskResult.Status]
        FAILED: _ClassVar[TaskResult.Status]
    SUCCESS: TaskResult.Status
    FAILED: TaskResult.Status
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    STDOUT_FIELD_NUMBER: _ClassVar[int]
    STDERR_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    status: TaskResult.Status
    result: str
    stdout: str
    stderr: str
    time: float
    def __init__(self, task_id: _Optional[str] = ..., status: _Optional[_Union[TaskResult.Status, str]] = ..., result: _Optional[str] = ..., stdout: _Optional[str] = ..., stderr: _Optional[str] = ..., time: _Optional[float] = ...) -> None: ...

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
    __slots__ = ("node_id", "status", "current_task", "available_mem", "processing_tasks")
    class NodeState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        IDLE: _ClassVar[NodeStatus.NodeState]
        BUSY: _ClassVar[NodeStatus.NodeState]
    IDLE: NodeStatus.NodeState
    BUSY: NodeStatus.NodeState
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_TASK_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_MEM_FIELD_NUMBER: _ClassVar[int]
    PROCESSING_TASKS_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    status: NodeStatus.NodeState
    current_task: int
    available_mem: int
    processing_tasks: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, node_id: _Optional[str] = ..., status: _Optional[_Union[NodeStatus.NodeState, str]] = ..., current_task: _Optional[int] = ..., available_mem: _Optional[int] = ..., processing_tasks: _Optional[_Iterable[str]] = ...) -> None: ...

class NodeRegistration(_message.Message):
    __slots__ = ("hostname", "os", "arch", "max_concurrency", "total_cpus", "total_mem")
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    ARCH_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENCY_FIELD_NUMBER: _ClassVar[int]
    TOTAL_CPUS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_MEM_FIELD_NUMBER: _ClassVar[int]
    hostname: str
    os: str
    arch: str
    max_concurrency: int
    total_cpus: int
    total_mem: int
    def __init__(self, hostname: _Optional[str] = ..., os: _Optional[str] = ..., arch: _Optional[str] = ..., max_concurrency: _Optional[int] = ..., total_cpus: _Optional[int] = ..., total_mem: _Optional[int] = ...) -> None: ...

class NodeRegistrationReply(_message.Message):
    __slots__ = ("node_id",)
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    def __init__(self, node_id: _Optional[str] = ...) -> None: ...
