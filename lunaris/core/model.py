from dataclasses import dataclass, field
import secrets
from datetime import datetime
from lunaris.proto.task_pb2 import Task as TaskProto


@dataclass
class Task:
    code: str
    task_id: str = secrets.token_hex(16)
    timestamp: int = int(datetime.now().timestamp())
    args: list = field(default_factory=list)
    lua_version: TaskProto.LuaVersion = TaskProto.LuaVersion.Lua54
    priority: int = 0
