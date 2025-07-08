from proto import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateTask(_message.Message):
    __slots__ = ("code", "args", "lua_version", "priority")
    CODE_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    LUA_VERSION_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    code: str
    args: str
    lua_version: _common_pb2.LuaVersion
    priority: int
    def __init__(self, code: _Optional[str] = ..., args: _Optional[str] = ..., lua_version: _Optional[_Union[_common_pb2.LuaVersion, str]] = ..., priority: _Optional[int] = ...) -> None: ...

class UnsubscribeTask(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, task_id: _Optional[_Iterable[str]] = ...) -> None: ...
