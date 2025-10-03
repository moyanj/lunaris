from pydantic import BaseModel, Field
from lunaris.master import id_gen


class Task(BaseModel):
    wasm_module: bytes
    entry: str = "main"
    task_id: str = Field(default_factory=id_gen.get_id)
    args: list = Field(default_factory=list)
    priority: int = 0

    def to_dict(self) -> dict:
        return {
            "wasm_module_size": len(self.wasm_module),
            "entry": self.entry,
            "task_id": self.task_id,
            "args": self.args,
            "priority": self.priority,
        }

    def __lt__(self, other):
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        return me < them

    def __gt__(self, other):
        me = (-self.priority, self.task_id)
        them = (-other.priority, other.task_id)
        return me > them
