import asyncio
import secrets
import platform
import psutil
from typing import Optional
from websockets import ConnectionClosedError, State
from websockets.asyncio.client import connect, ClientConnection
from lunaris.utils import proto2bytes, bytes2proto
from lunaris.proto.task_pb2 import (
    NodeRegistration,
    NodeStatus,
    Task,
    TaskResult,
    UnregisterNode,
)
from lunaris.runtime.engine import LuaResult
from lunaris.worker.core import Runner
from loguru import logger


class Worker:
    def __init__(
        self,
        master_uri: str,
        name: Optional[str] = None,
        max_concurrency: Optional[int] = None,
    ) -> None:
        # Worker 配置
        self.master_uri = master_uri
        self.name = name or f"worker-{secrets.token_hex(8)}"
        self.max_concurrency = max_concurrency or psutil.cpu_count() or 1
        self.node_id: str = ""
        self.running = False

        # WebSocket 连接
        self.ws: Optional[ClientConnection] = None

        # 任务执行器
        self.runner = Runner(
            max_workers=self.max_concurrency, report_callback=self.report_result
        )
        self.num_running = 0

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
            os=platform.system(),
            arch=platform.machine(),
            max_concurrency=self.max_concurrency,
            num_cpu=psutil.cpu_count(),
            memory_size=psutil.virtual_memory().total // 1048576,
        )
        await self.ws.send(proto2bytes(registration))

        response = await self.ws.recv(decode=False)
        self.node_id = bytes2proto(response).node_id

        logger.info(f"Registered.")

    async def report_result(self, result: LuaResult, task_id: str) -> None:
        """向Master报告任务结果"""
        if not self.ws:
            raise ConnectionError("WebSocket未连接")

        proto = TaskResult(
            task_id=task_id,
            result=result.result,
            stdout=result.stdout,
            stderr=result.stderr,
            time=result.time,
            succeeded=result.succeeded,
        )
        await self.ws.send(proto2bytes(proto))

    async def handle_task(self, task: Task) -> None:
        """处理接收到的任务"""
        if not self.runner:
            raise RuntimeError("执行器未初始化")
        logger.info(f"Received task: {task.task_id}")
        self.num_running += 1
        logger.debug(f"Number of running tasks:{self.num_running}")
        self.runner.submit(task)

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

        except (ConnectionError, asyncio.CancelledError) as e:
            logger.error(f"Connection error: {e}")
        except ConnectionClosedError:
            logger.warning("Connection closed")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """优雅关闭Worker"""
        self.running = False
        await self.disconnect()
