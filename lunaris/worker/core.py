# core.py
from multiprocessing import Pool
from typing import Optional, Callable
import psutil
from lunaris.proto.task_pb2 import Task
from lunaris.runtime import LuaSandbox, LuaVersion
from lunaris.runtime.engine import LuaResult


class Runner:
    def __init__(
        self, max_workers: Optional[int] = None, callback: Optional[Callable] = None
    ):
        self.max_workers = max_workers or psutil.cpu_count()
        self.executor = Pool(self.max_workers)
        self.num_running = 0
        self.result = []
        self.callback = callback

    def task_completed(self, result_tuple):
        """Handle task completion and invoke the callback"""
        result, task_id = result_tuple
        self.num_running -= 1
        if self.callback:
            self.callback(task_id, result)

    def submit(self, task: Task):
        self.executor.apply_async(
            self.worker,
            (task.code, task.args, task.lua_version, task.task_id),
            callback=self.task_completed,
        )
        self.num_running += 1

    def worker(self, code: str, args: str, lua_version: Task.LuaVersion, task_id: str):

        version = getattr(LuaVersion, Task.LuaVersion.Name(lua_version))
        if version is None:
            raise ValueError(f"Invalid lua version: {lua_version}")
        lua = LuaSandbox(version)
        return lua.run(code, *args), task_id

    def close(self):
        self.executor.close()
