import secrets
from datetime import datetime
from lunaris.proto.task_pb2 import Task as TaskProto
from pydantic import BaseModel, Field


class Task(BaseModel):
    code: str
    task_id: str = Field(default_factory=lambda: secrets.token_hex(16))
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    args: list = Field(default_factory=list)
    lua_version: str = "LUA_54"
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
