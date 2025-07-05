from calendar import c
from fastapi import APIRouter, Request, Depends
from lunaris.master.web_app import get_app_state, AppState
from lunaris.master.manager import Task
from lunaris.utils import Rest
from pydantic import BaseModel, Field
from lunaris.proto.task_pb2 import Task as TaskProto
import json

app = APIRouter()


class TaskModel(BaseModel):
    code: str
    args: str = "[]"
    lua_version: str = "LUA_54"
    priority: int = Field(default=0)


@app.get("/worker")
async def get_workers(state: AppState = Depends(get_app_state)):
    workers = state.worker_manager.workers
    return Rest(data={"count": len(workers), "workers": [w.to_dict() for w in workers]})


@app.get("/task")
async def get_tasks(state: AppState = Depends(get_app_state)):
    tasks = state.task_manager.all()
    return Rest(data={"count": len(tasks), "tasks": [t.to_dict() for t in tasks]})


@app.post("/task")
async def add_task(task: TaskModel, state: AppState = Depends(get_app_state)):
    task_r = Task(
        code=task.code,
        args=json.loads(task.args),
        lua_version=getattr(TaskProto.LuaVersion, task.lua_version),
        priority=task.priority,
    )
    state.task_manager.add_task(task_r)
    return Rest(data=task_r.to_dict())
