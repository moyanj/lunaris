from re import S
from pydantic import BaseModel, Field
import secrets
from datetime import datetime
from lunaris.proto.task_pb2 import Task as TaskProto


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: secrets.token_hex(16))
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    code: str
    args: list = Field(default_factory=list)
    lua_version: TaskProto.LuaVersion = Field(default=TaskProto.LuaVersion.Lua54)
    priority: int = Field(default=0)
