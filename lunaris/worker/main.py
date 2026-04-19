import asyncio
import json
import os
import secrets
import platform
import psutil
from typing import Optional
from websockets import ConnectionClosedError, State
from websockets.asyncio.client import connect, ClientConnection
from lunaris.utils import proto2bytes, bytes2proto
from lunaris.proto.worker_pb2 import (
    ControlCommand,
    NodeRegistration,
    NodeStatus,
    Task,
    TaskAccepted,
    UnregisterNode,
)
from lunaris.proto.common_pb2 import TaskResult
from lunaris.runtime import ExecutionLimits
from lunaris.runtime.engine import WasmResult
from lunaris.worker.core import Runner
from loguru import logger
from lunaris.worker import init_logger


def _env_limit(name: str, default: int = 0) -> int:
    try:
        return max(int(os.environ.get(name, default)), 0)
    except ValueError:
        return default


class Worker:
    def __init__(
        self,
        master_uri: str,
        token: str,
        name: Optional[str] = None,
        max_concurrency: Optional[int] = None,
        default_execution_limits: Optional[ExecutionLimits] = None,
        max_execution_limits: Optional[ExecutionLimits] = None,
    ) -> None:
        init_logger()
        # Worker 配置
        self.master_uri = master_uri
        self.name = name or f"worker-{secrets.token_hex(8)}"
        self.max_concurrency = max_concurrency or psutil.cpu_count() or 1
        self.node_id: str = ""
        self.running = False
        self.token = token
        self.default_execution_limits = default_execution_limits or ExecutionLimits(
            max_fuel=_env_limit("LUNARIS_WORKER_DEFAULT_MAX_FUEL"),
            max_memory_bytes=_env_limit("LUNARIS_WORKER_DEFAULT_MAX_MEMORY_BYTES"),
            max_module_bytes=_env_limit("LUNARIS_WORKER_DEFAULT_MAX_MODULE_BYTES"),
        )
        self.max_execution_limits = max_execution_limits or ExecutionLimits(
            max_fuel=_env_limit("LUNARIS_WORKER_MAX_FUEL"),
            max_memory_bytes=_env_limit("LUNARIS_WORKER_MAX_MEMORY_BYTES"),
            max_module_bytes=_env_limit("LUNARIS_WORKER_MAX_MODULE_BYTES"),
        )

        # WebSocket 连接
        self.ws: Optional[ClientConnection] = None

        # 任务执行器
        self.runner = Runner(
            max_workers=self.max_concurrency,
            report_callback=self.report_result,
            default_execution_limits=self.default_execution_limits,
            max_execution_limits=self.max_execution_limits,
        )
        self.num_running = 0
        self.drain_enabled = False
        self.cancelled_tasks: set[str] = set()

    async def connect(self) -> None:
        """建立与Master的WebSocket连接"""
        self.ws = await connect(self.master_uri).__aenter__()
        self.running = True

    async def heartbeat(self) -> None:
        if not self.ws:
            raise ConnectionError("WebSocket连接未建立")
        logger.info("Heartbeat task started")
        while self.running:
            state = NodeStatus.NodeState.IDLE
            if self.num_running == self.max_concurrency:
                state = NodeStatus.NodeState.BUSY

            await self.ws.send(
                proto2bytes(
                    NodeStatus(
                        node_id=self.node_id,
                        status=state,
                        current_task=self.num_running,
                    )
                )
            )

            await asyncio.sleep(10)

    async def disconnect(self) -> None:
        """关闭连接"""
        if self.ws and self.ws.state == State.OPEN:
            await self.ws.send(
                proto2bytes(
                    UnregisterNode(
                        node_id=self.node_id,
                    )
                )
            )
            self.ws = None
        if self.runner:
            await self.runner.close()
            self.runner = None

    async def register(self) -> None:
        """向Master注册Worker节点"""
        if not self.ws:
            raise ConnectionError("WebSocket未连接")

        registration = NodeRegistration(
            name=self.name,
            arch=platform.machine(),
            max_concurrency=self.max_concurrency,
            memory_size=psutil.virtual_memory().total // 1048576,
            token=self.token,
        )
        await self.ws.send(proto2bytes(registration))

        response = await self.ws.recv(decode=False)
        response = bytes2proto(response)
        if type(response) == ControlCommand:
            if response.type == ControlCommand.CommandType.SHUTDOWN:
                logger.info(f"Cannot connect to master. Reason: {response.data}")
                exit()
        else:
            self.node_id = response.node_id

        logger.info(f"Registered.")

    async def report_result(self, result: WasmResult, task_id: str, attempt: int) -> None:
        """向Master报告任务结果"""
        if not self.ws:
            raise ConnectionError("WebSocket未连接")

        # worker 无法强杀进程池中的任务时，取消命令退化为“结果收敛为已取消”。
        if task_id in self.cancelled_tasks:
            result = WasmResult(
                result="",
                stdout=result.stdout,
                stderr=b"task cancelled",
                time=result.time,
                succeeded=False,
            )
            self.cancelled_tasks.discard(task_id)

        proto = TaskResult(
            task_id=task_id,
            result=str(result.result),
            stdout=result.stdout,
            stderr=result.stderr,
            time=result.time,
            succeeded=result.succeeded,
            attempt=attempt,
        )
        self.num_running -= 1

        await self.ws.send(proto2bytes(proto))

    async def handle_task(self, task: Task) -> None:
        """处理接收到的任务"""
        if not self.runner:
            raise RuntimeError("执行器未初始化")
        logger.info(f"Received task: {task.task_id}")
        if not self.ws:
            raise ConnectionError("WebSocket连接未建立")
        if self.drain_enabled or task.task_id in self.cancelled_tasks:
            await self.report_result(
                WasmResult(
                    result="",
                    stdout=b"",
                    stderr=b"task cancelled",
                    time=0,
                    succeeded=False,
                ),
                task.task_id,
                task.attempt,
            )
            return
        await self.ws.send(
            proto2bytes(
                TaskAccepted(
                    task_id=task.task_id,
                    node_id=self.node_id,
                    attempt=task.attempt,
                )
            )
        )
        self.num_running += 1
        logger.debug(f"Number of running tasks:{self.num_running}")
        self.runner.submit(task)

    async def handle_control_command(self, command: ControlCommand) -> None:
        """处理 master 下发的控制命令。"""
        if command.type == ControlCommand.CommandType.SHUTDOWN:
            self.running = False
            return

        if command.type == ControlCommand.CommandType.SET_DRAIN:
            try:
                payload = json.loads(command.data or "{}")
            except json.JSONDecodeError:
                payload = {}
            self.drain_enabled = bool(payload.get("enabled", False))
            logger.info("Drain mode set to {}", self.drain_enabled)
            return

        if command.type == ControlCommand.CommandType.CANCEL_TASK:
            try:
                payload = json.loads(command.data or "{}")
            except json.JSONDecodeError:
                payload = {}
            task_id = payload.get("task_id")
            if task_id:
                self.cancelled_tasks.add(task_id)
                logger.info("Received cancel request for task {}", task_id)

    async def run(self) -> None:
        """Worker主循环"""
        try:
            await self.connect()
            await self.register()

            asyncio.create_task(self.heartbeat())
            if self.runner:
                self.runner.start()

            # 主消息处理循环
            while self.running and self.ws:
                message = await self.ws.recv(decode=False)
                proto = bytes2proto(message)
                if isinstance(proto, Task):
                    await self.handle_task(proto)
                elif isinstance(proto, ControlCommand):
                    await self.handle_control_command(proto)

        except (ConnectionError, asyncio.CancelledError) as e:
            import traceback

            logger.error(f"Connection error: {e}")
        except ConnectionClosedError:
            logger.warning("Connection closed")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """优雅关闭Worker"""
        self.running = False
        await self.disconnect()
