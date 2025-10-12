from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.websockets import WebSocketState
from lunaris.master.web_app import get_app_state, AppState
from lunaris.master.manager import Task
from lunaris.proto.client_pb2 import CreateTask, TaskCreated
from lunaris.utils import Rest, bytes2proto, proto2bytes
from lunaris.master.model import TaskStatus
import orjson

app = APIRouter()


@app.get("/worker")
async def get_workers(state: AppState = Depends(get_app_state)):
    workers = state.worker_manager.workers
    return Rest(data={"count": len(workers), "workers": [w.to_dict() for w in workers]})


@app.websocket("/task")
async def tasks(token: str, ws: WebSocket, state: AppState = Depends(get_app_state)):
    from lunaris.proto.client_pb2 import UnsubscribeTask
    from loguru import logger

    if token != state.client_token:
        raise HTTPException(status_code=403, detail="Invalid token")
    await ws.accept()
    logger.info("WebSocket connection established for task submission")

    try:
        while ws.client_state == WebSocketState.CONNECTED:
            try:
                data = bytes2proto(await ws.receive_bytes())
                if type(data) is CreateTask:

                    task = Task(
                        wasm_module=data.wasm_module,
                        args=orjson.loads(data.args),
                        entry=data.entry,
                        priority=data.priority,
                        wasi_env={
                            "env": dict(data.wasi_env.env),
                            "args": list(data.wasi_env.args),
                        },
                    )

                    logger.info(f"Created task with ID: {task.task_id}")
                    state.task_manager.add_task(task, ws)
                    await ws.send_bytes(proto2bytes(TaskCreated(task_id=task.task_id)))

                elif type(data) is UnsubscribeTask:
                    for task in state.task_manager.all():
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
    for result in state.task_manager.result:
        if result.task_id == task_id:
            return Rest(
                data={
                    "task_id": result.task_id,
                    "result": result.result,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "time": result.time,
                }
            )

    return Rest(msg="Task not found or doesn't run", status_code=404)


@app.get("/tasks")
async def get_all_tasks(state: AppState = Depends(get_app_state)):
    """获取所有任务的状态信息"""
    tasks = state.task_manager.all()
    return Rest(data={"count": len(tasks), "tasks": [task.to_dict() for task in tasks]})


@app.get("/tasks/status/{status}")
async def get_tasks_by_status(status: str, state: AppState = Depends(get_app_state)):
    """根据状态获取任务"""
    try:
        task_status = TaskStatus(status)
        tasks = state.task_manager.get_tasks_by_status(task_status)
        return Rest(
            data={"count": len(tasks), "tasks": [task.to_dict() for task in tasks]}
        )
    except ValueError:
        return Rest(msg=f"Invalid status: {status}", status_code=400)


@app.get("/tasks/worker/{worker_id}")
async def get_tasks_by_worker(worker_id: str, state: AppState = Depends(get_app_state)):
    """获取分配给指定worker的任务"""
    tasks = state.task_manager.get_tasks_by_worker(worker_id)
    return Rest(data={"count": len(tasks), "tasks": [task.to_dict() for task in tasks]})


@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str, state: AppState = Depends(get_app_state)):
    """获取特定任务的详细状态"""
    task = state.task_manager.get_task(task_id)
    if task:
        return Rest(data=task.to_dict())
    return Rest(msg="Task not found", status_code=404)


@app.get("/stats")
async def get_system_stats(state: AppState = Depends(get_app_state)):
    """获取系统统计信息"""
    tasks = state.task_manager.all()
    status_counts = {}
    for status in TaskStatus:
        status_counts[status.value] = len([t for t in tasks if t.status == status])

    return Rest(
        data={
            "workers": {
                "total": len(state.worker_manager.workers),
                "active": len(
                    [
                        w
                        for w in state.worker_manager.workers
                        if w.websocket.client_state == WebSocketState.CONNECTED
                    ]
                ),
            },
            "tasks": status_counts,
            "queue_size": state.task_manager.task_queue.qsize(),
            "running_tasks": len(state.task_manager.running_tasks),
        }
    )
