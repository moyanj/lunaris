import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from lunaris.master.web_app import get_app_state, AppState
from lunaris.master.model import Task, TaskStatus
from lunaris.proto.worker_pb2 import ControlCommand
from lunaris.proto.client_pb2 import CreateTask, TaskCreateFailed, TaskCreated
from lunaris.runtime.capabilities import normalize_host_capabilities
from lunaris.utils import Rest, bytes2proto, proto2bytes
from lunaris.runtime import ExecutionLimits
import orjson

app = APIRouter()


def require_client_token(
    state: AppState = Depends(get_app_state),
    token: Optional[str] = Query(default=None),
    x_client_token: Optional[str] = Header(default=None, alias="X-Client-Token"),
) -> None:
    provided_token = x_client_token or token
    if not provided_token or not secrets.compare_digest(
        provided_token, state.client_token
    ):
        raise HTTPException(status_code=403, detail="Invalid token")


@app.get("/worker")
async def get_workers(
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
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
                    try:
                        execution_limits = state.apply_execution_limits(
                            ExecutionLimits.from_proto(data.execution_limits)
                        )
                        if (
                            execution_limits.max_module_bytes > 0
                            and len(data.wasm_module)
                            > execution_limits.max_module_bytes
                        ):
                            raise ValueError(
                                "Wasm module exceeds the configured size limit"
                            )

                        task = Task(
                            wasm_module=data.wasm_module,
                            idempotency_key=data.idempotency_key or None,
                            args=orjson.loads(data.args),
                            entry=data.entry,
                            priority=data.priority,
                            wasi_env={
                                "env": dict(data.wasi_env.env),
                                "args": list(data.wasi_env.args),
                            },
                            execution_limits=execution_limits.to_dict(),
                            host_capabilities=normalize_host_capabilities(
                                data.host_capabilities.items
                            ),
                        )

                        scoped_key = (
                            f"{token}:{data.idempotency_key}"
                            if data.idempotency_key
                            else None
                        )
                        if scoped_key:
                            existing = state.task_manager.get_task_by_idempotency_key(
                                scoped_key
                            )
                            if existing:
                                state.task_manager.subscribe(existing.task_id, ws)
                                await ws.send_bytes(
                                    proto2bytes(
                                        TaskCreated(
                                            task_id=existing.task_id,
                                            request_id=data.request_id,
                                        )
                                    )
                                )
                                continue

                        logger.info(f"Created task with ID: {task.task_id}")
                        await state.task_manager.add_task(task, ws)
                        await state.task_manager.register_idempotency_key(
                            scoped_key, task
                        )
                        await ws.send_bytes(
                            proto2bytes(
                                TaskCreated(
                                    task_id=task.task_id,
                                    request_id=data.request_id,
                                )
                            )
                        )
                    except Exception as exc:
                        logger.error(f"Failed to create task: {str(exc)}")
                        await ws.send_bytes(
                            proto2bytes(
                                TaskCreateFailed(
                                    error=str(exc),
                                    request_id=data.request_id,
                                )
                            )
                        )

                elif type(data) is UnsubscribeTask:
                    for task_id in data.task_id:
                        state.task_manager.unsubscribe(task_id, ws)

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        state.task_manager.unsubscribe_ws(ws)
        logger.info("WebSocket connection closed")


@app.websocket("/task/{task_id}/subscribe")
async def subscribe_task(
    task_id: int,
    token: str,
    ws: WebSocket,
    state: AppState = Depends(get_app_state),
):
    if token != state.client_token:
        raise HTTPException(status_code=403, detail="Invalid token")
    await ws.accept()
    task = state.task_manager.get_task(task_id)
    if not task:
        await ws.close(code=4404)
        return

    state.task_manager.subscribe(task_id, ws)
    if task.result:
        await ws.send_bytes(proto2bytes(task.result.to_proto(task_id)))

    try:
        while ws.client_state == WebSocketState.CONNECTED:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state.task_manager.unsubscribe(task_id, ws)


@app.get("/task/{task_id}")
async def get_task_result(
    task_id: int,
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    result = state.task_manager.get_task_result(task_id)
    if result:
        return Rest(data=result)
    return Rest(msg="Task result not found", status_code=404)


@app.get("/tasks")
async def get_all_tasks(
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    """获取所有任务的状态信息"""
    tasks = state.task_manager.all()
    return Rest(data={"count": len(tasks), "tasks": [task.to_dict() for task in tasks]})


@app.get("/tasks/status/{status}")
async def get_tasks_by_status(
    status: str,
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
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
async def get_tasks_by_worker(
    worker_id: str,
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    """获取分配给指定worker的任务"""
    tasks = state.task_manager.get_tasks_by_worker(worker_id)
    return Rest(data={"count": len(tasks), "tasks": [task.to_dict() for task in tasks]})


@app.get("/task/{task_id}/status")
async def get_task_status(
    task_id: int,
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    """获取特定任务的详细状态"""
    task = state.task_manager.get_task(task_id)
    if task:
        return Rest(data=task.to_dict())
    return Rest(msg="Task not found", status_code=404)


@app.get("/task/{task_id}/events")
async def get_task_events(
    task_id: int,
    after_seq: int = Query(default=0, ge=0),
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    task = state.task_manager.get_task(task_id)
    if not task:
        return Rest(msg="Task not found", status_code=404)
    return Rest(data={"task_id": task_id, "events": state.task_manager.get_task_events(task_id, after_seq)})


@app.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    task = await state.task_manager.cancel_task(task_id)
    if not task:
        return Rest(msg="Task not found", status_code=404)
    if task.status == TaskStatus.CANCEL_REQUESTED and task.assigned_worker:
        await state.worker_manager.send_control_command(
            task.assigned_worker,
            ControlCommand.CommandType.CANCEL_TASK,
            {"task_id": task.task_id},
        )
    return Rest(data=task.to_dict())


@app.post("/worker/{worker_id}/drain")
async def set_worker_drain(
    worker_id: str,
    enabled: bool = Query(default=True),
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    ok = await state.worker_manager.set_drain(worker_id, enabled)
    if not ok:
        return Rest(msg="Worker not found", status_code=404)
    return Rest(data={"worker_id": worker_id, "drain": enabled})


@app.get("/stats")
async def get_system_stats(
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
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
