import asyncio
import os
import secrets
from typing import Optional
from fastapi import FastAPI, WebSocket, Depends
from fastapi.websockets import WebSocketState, WebSocketDisconnect
from lunaris.proto import common_pb2
from lunaris.utils import bytes2proto, proto2bytes
from lunaris.proto.worker_pb2 import (
    ControlCommand,
    NodeRegistration,
    Task as TaskProto,
)
from lunaris.proto.common_pb2 import Envelope
import lunaris.proto.worker_pb2 as worker_pb2
from lunaris.master.manager import WorkerManager, TaskManager
from lunaris.master.model import Task, WorkerStatus
from lunaris.master.store import PersistentStateStore
from contextlib import asynccontextmanager
import orjson
from loguru import logger
from lunaris.master import init_logger
from lunaris.runtime import ExecutionLimits


def _env_limit(name: str, default: int = 0) -> int:
    try:
        return max(int(os.environ.get(name, default)), 0)
    except ValueError:
        return default


class AppState:
    def __init__(
        self,
        default_execution_limits: Optional[ExecutionLimits] = None,
        max_execution_limits: Optional[ExecutionLimits] = None,
        state_dir: Optional[str] = None,
    ):
        self.state_dir = state_dir or os.environ.get(
            "LUNARIS_STATE_DIR",
            os.path.join(os.getcwd(), ".lunaris-state"),
        )
        self.store = PersistentStateStore(self.state_dir)
        self.worker_manager: Optional[WorkerManager] = None
        self.task_manager: Optional[TaskManager] = None
        self.scheduler_events: asyncio.Queue[str] = asyncio.Queue()
        self.client_token: str = os.environ.get("CLIENT_TOKEN", secrets.token_hex(16))
        self.worker_token: str = os.environ.get("WORKER_TOKEN", secrets.token_hex(16))
        self.default_execution_limits = default_execution_limits or ExecutionLimits(
            max_fuel=_env_limit("LUNARIS_DEFAULT_MAX_FUEL"),
            max_memory_bytes=_env_limit("LUNARIS_DEFAULT_MAX_MEMORY_BYTES"),
            max_module_bytes=_env_limit("LUNARIS_DEFAULT_MAX_MODULE_BYTES"),
        )
        self.max_execution_limits = max_execution_limits or ExecutionLimits(
            max_fuel=_env_limit("LUNARIS_MAX_FUEL"),
            max_memory_bytes=_env_limit("LUNARIS_MAX_MEMORY_BYTES"),
            max_module_bytes=_env_limit("LUNARIS_MAX_MODULE_BYTES"),
        )

    def apply_execution_limits(self, requested: ExecutionLimits) -> ExecutionLimits:
        return requested.clamp(
            defaults=self.default_execution_limits,
            maximums=self.max_execution_limits,
        )

    async def initialize(self) -> None:
        await self.store.load()
        self.worker_manager = WorkerManager(self.store, self.notify_scheduler)
        self.task_manager = TaskManager(self.store, self.notify_scheduler)

    async def notify_scheduler(self, reason: str) -> None:
        # 调度循环基于事件触发，任何容量或任务状态变化都投递一次唤醒事件。
        await self.scheduler_events.put(reason)

    async def close(self):
        if self.worker_manager:
            await self.worker_manager.close()


def get_app_state() -> AppState:
    return app.state.state


@asynccontextmanager
async def lifecycle(app: FastAPI):
    init_logger()
    from lunaris.master.api import app as api

    app.state.state = AppState(
        default_execution_limits=getattr(app.state, "default_execution_limits", None),
        max_execution_limits=getattr(app.state, "max_execution_limits", None),
        state_dir=getattr(app.state, "state_dir", None),
    )
    await app.state.state.initialize()
    await app.state.state.task_manager.flush_recovery()  # type: ignore[union-attr]
    await app.state.state.notify_scheduler("startup")
    logger.info(f"Worker Token: {app.state.state.worker_token}")
    logger.info(f"Client Token: {app.state.state.client_token}")
    asyncio.create_task(check_heartbeat(app.state.state))
    asyncio.create_task(check_task_leases(app.state.state))
    asyncio.create_task(check_retry_queue(app.state.state))
    asyncio.create_task(distribute_tasks(app.state.state))
    app.include_router(api)
    yield
    await app.state.state.close()


app = FastAPI(lifespan=lifecycle)


@app.websocket("/worker")
async def websocket_endpoint(ws: WebSocket, state: AppState = Depends(get_app_state)):
    await ws.accept()
    worker_removed = False
    try:
        reg_data: Optional[bytes] = None
        try:
            reg_data = await asyncio.wait_for(ws.receive_bytes(), timeout=10.0)
        except asyncio.TimeoutError:
            await ws.close()
            return

        registration = bytes2proto(reg_data)
        if type(registration) != NodeRegistration:
            await ws.close()
            return
        if not registration.token == state.worker_token:
            await ws.send_bytes(
                proto2bytes(
                    ControlCommand(
                        type=ControlCommand.CommandType.SHUTDOWN, data="Invalid token"
                    )
                )
            )
            await ws.close()
            return
        await state.worker_manager.register(ws, registration)

        while True and ws.client_state == WebSocketState.CONNECTED:
            data = await ws.receive_bytes()
            try:
                data = bytes2proto(data)
            except ValueError:
                continue
            if type(data) == worker_pb2.NodeStatus:
                await state.worker_manager.handle_heartbeat(ws, data)
            elif type(data) == worker_pb2.TaskAccepted:
                worker = state.worker_manager.get_worker_by_ws(ws)
                if not worker:
                    logger.warning("Rejected task acceptance from unregistered worker")
                    break
                if data.node_id and data.node_id != worker.node_id:
                    logger.warning(
                        f"Rejected task acceptance from mismatched node_id {data.node_id}"
                    )
                    break
                await state.task_manager.mark_task_running(
                    data.task_id,
                    worker,
                    data.attempt,
                )
            elif type(data) == common_pb2.TaskResult:
                worker = state.worker_manager.get_worker_by_ws(ws)
                if not worker:
                    logger.warning("Rejected task result from unregistered worker connection")
                    break
                await state.task_manager.put_result(
                    data, state.worker_manager, worker
                )
            elif type(data) == worker_pb2.UnregisterNode:
                worker = state.worker_manager.get_worker_by_ws(ws)
                if not worker:
                    logger.warning("Rejected unregister request from unknown worker connection")
                    break
                if data.node_id and data.node_id != worker.node_id:
                    logger.warning(
                        f"Rejected unregister request for mismatched node_id {data.node_id}"
                    )
                    break
                await state.task_manager.requeue_worker_tasks(
                    worker, reason="worker unregistered"
                )
                await state.worker_manager.remove_worker(worker)
                worker_removed = True
                logger.info(f"Unregistered node {worker.node_id}")
                break

            else:
                await ws.send_text("Invalid message")
                break
    except WebSocketDisconnect:
        logger.warning("A worker disconnected")
    except Exception as e:
        import traceback

        logger.error(traceback.format_exc())
        logger.error(f"Error: {e}")
    finally:
        if not worker_removed:
            worker = state.worker_manager.get_worker_by_ws(ws)
            if worker:
                await state.task_manager.requeue_worker_tasks(
                    worker, reason="worker websocket disconnected"
                )
                await state.worker_manager.remove_worker(worker, status=WorkerStatus.LOST)

        if ws.client_state != WebSocketState.DISCONNECTED:
            try:
                await ws.close()
            except Exception:
                pass


async def check_heartbeat(state: AppState):
    logger.info("Heartbeat detection task started")
    try:
        while True:
            await asyncio.sleep(20)
            removed_workers = await state.worker_manager.remove_inactive_workers()
            for worker in removed_workers:
                await state.task_manager.requeue_worker_tasks(
                    worker, reason="worker heartbeat timeout"
                )
    except asyncio.CancelledError:
        pass


async def check_task_leases(state: AppState):
    logger.info("Task lease detection task started")
    try:
        while True:
            await asyncio.sleep(5)
            await state.task_manager.requeue_expired_leases(state.worker_manager)
            for worker in list(state.worker_manager.workers):
                await state.worker_manager.sync_worker_state(worker)
    except asyncio.CancelledError:
        pass


async def check_retry_queue(state: AppState):
    logger.info("Task retry scheduler started")
    try:
        while True:
            await asyncio.sleep(1)
            await state.task_manager.process_retry_queue()
    except asyncio.CancelledError:
        pass


async def distribute_tasks(state: AppState):
    logger.info("Task distribution started")
    while True:
        reason = await state.scheduler_events.get()
        logger.debug("Scheduler awakened by {}", reason)
        while True:
            deferred: list[Task] = []
            task: Optional[Task] = None
            worker = None
            while True:
                candidate = state.task_manager.pop_next_queued_task_nowait()
                if not candidate:
                    break
                candidate_worker = state.worker_manager.get_available_worker_nowait(
                    candidate.host_capabilities
                )
                if candidate_worker:
                    task = candidate
                    worker = candidate_worker
                    break
                deferred.append(candidate)

            for deferred_task in deferred:
                state.task_manager._enqueue_task(deferred_task)

            if not task or not worker:
                break

            logger.info(f"Distributing task {task.task_id} to {worker.registration.name}")

            # 分配任务给worker
            await state.task_manager.assign_task_to_worker(task, worker)
            await state.worker_manager.sync_worker_state(worker)

            # 发送任务到worker
            try:
                await worker.websocket.send_bytes(
                    proto2bytes(
                        TaskProto(
                            task_id=task.task_id,
                            wasm_module=task.wasm_module,
                            args=orjson.dumps(task.args).decode("utf-8"),
                            entry=task.entry,
                            priority=task.priority,
                            wasi_env=task.wasi_env,
                            execution_limits=task.execution_limits,
                            attempt=task.attempt_count,
                            host_capabilities={
                                "items": task.host_capabilities,
                            },
                        ),
                        Envelope.MessageType.TASK,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to dispatch task {} to worker {}: {}",
                    task.task_id,
                    worker.node_id,
                    exc,
                )
                worker.remove_task(task.task_id)
                await state.worker_manager.sync_worker_state(worker)
                state.task_manager.running_tasks.pop(task.task_id, None)
                task.mark_queued()
                state.task_manager._enqueue_task(task)
                await state.task_manager._schedule_retry_or_fail(task, "task dispatch failed")
                await state.store.persist()
                break
