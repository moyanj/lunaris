from dataclasses import dataclass, field
import secrets
from datetime import datetime
from lunaris.proto.task_pb2 import Task as TaskProto


@dataclass
class Task:
    code: str
    task_id: str = field(default_factory=lambda: secrets.token_hex(16))
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    args: list = field(default_factory=list)
    lua_version: TaskProto.LuaVersion = TaskProto.LuaVersion.LUA_54
    priority: int = 0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "args": self.args,
            "lua_version": self.lua_version,
            "priority": self.priority,
        }
