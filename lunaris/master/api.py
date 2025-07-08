from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.websockets import WebSocketState
from lunaris.master.web_app import get_app_state, AppState
from lunaris.master.manager import Task
from lunaris.proto.client_pb2 import CreateTask
from lunaris.utils import Rest, bytes2proto
from pydantic import BaseModel, Field
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


@app.websocket("/task")
async def tasks(ws: WebSocket, state: AppState = Depends(get_app_state)):
    from lunaris.proto.client_pb2 import UnsubscribeTask
    from loguru import logger

    await ws.accept()
    logger.info("WebSocket connection established for task submission")

    try:
        while ws.client_state == WebSocketState.CONNECTED:
            try:
                data = bytes2proto(await ws.receive_bytes())

                if type(data) is CreateTask:
                    logger.info(f"Received CreateTask request")

                    task = Task(
                        code=data.code,
                        args=json.loads(data.args),
                        lua_version=data.lua_version,
                        priority=data.priority,
                    )

                    logger.info(f"Created task with ID: {task.task_id}")
                    state.task_manager.add_task(task, ws)

                elif type(data) is UnsubscribeTask:
                    for task in state.task_manager._tasks_list:
                        if task.task_id in data.task_id:
                            state.task_manager.task_websockets.pop(task.task_id)
                    await ws.close()

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")

    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        logger.info("WebSocket connection closed")


@app.get("/task/{task_id}")
async def get_task_result(task_id: str, state: AppState = Depends(get_app_state)):
    result = state.task_manager._result.get(task_id)
    if result is None:
        return Rest(msg="Task not found or doesn't run", status_code=404)
    return Rest(
        data={
            "task_id": result.task_id,
            "result": result.result,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "time": result.time,
        }
    )
