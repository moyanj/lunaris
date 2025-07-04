# main.py
from os import system
from websockets.asyncio.client import connect, ClientConnection
from lunaris.runtime.engine import LuaResult
from lunaris.utils import proto2bytes, bytes2proto
from lunaris.worker.core import Runner
from lunaris.proto.task_pb2 import NodeRegistration, NodeStatus, Task, TaskResult
from typing import Any, Optional
import secrets
import platform
import psutil


class Worker:
    def __init__(
        self, master_uri: str, name: Optional[str] = None, max_concurrency: int = 32
    ) -> None:
        self.master_uri = master_uri
        self.name = name or f"worker-{secrets.token_hex(8)}"
        self.max_concurrency = max_concurrency
        self.ws: ClientConnection = None  # type: ignore
        self.node_id = "114514"
        self.runner = Runner(
            max_workers=self.max_concurrency, callback=self.report_result
        )

    async def connect(self) -> None:
        self.ws = await connect(self.master_uri).__aenter__()

    async def disconnect(self) -> None:
        await self.ws.close()
        await self.ws.__aexit__(None, None, None)

    async def report_result(self, task_id: str, result: LuaResult) -> None:
        proto = TaskResult(
            task_id=task_id,
            result=result.result,
            stdout=result.stdout,
            stderr=result.stderr,
            time=result.time,
        )
        await self.ws.send(proto2bytes(proto))

    async def register(self) -> None:
        registration = NodeRegistration(
            hostname=self.name,
            os=platform.system(),
            arch=platform.machine(),
            max_concurrency=self.max_concurrency,
            num_cpu=psutil.cpu_count(),
            memory_size=psutil.virtual_memory().total // 1048576,
        )
        await self.ws.send(proto2bytes(registration))

    async def on_message(self, data: Any) -> None:
        if isinstance(data, Task):
            self.runner.submit(data)

    async def run(self):
        await self.connect()
        await self.register()
        node_id = bytes2proto(await self.ws.recv(decode=False)).node_id
        self.node_id = node_id

        while True:
            proto = bytes2proto(await self.ws.recv(decode=False))
            await self.on_message(proto)
