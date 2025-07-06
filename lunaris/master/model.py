import secrets
from datetime import datetime
from lunaris.proto.task_pb2 import Task as TaskProto
from pydantic import BaseModel, Field
from lunaris.master import id_gen


class Task(BaseModel):
    code: str
    task_id: str = Field(default_factory=id_gen.get_id)
    args: list = Field(default_factory=list)
    lua_version: str = "LUA_54"
    priority: int = 0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "task_id": self.task_id,
            "args": self.args,
            "lua_version": self.lua_version,
            "priority": self.priority,
        }

    def __lt__(self, other):
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        if me < them:
            return True
        else:
            return False

    def __gt__(self, other):
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        if me > them:
            return True
        else:
            return False
