import asyncio
import threading
from typing import Optional, Dict, Any, List
from lunaris.client.client import LunarisClient
from lunaris.proto.common_pb2 import TaskResult
from lunaris.runtime import ExecutionLimits
from loguru import logger


class SyncLunarisClient:
    def __init__(self, master_uri: str, token: str):
        """
        同步客户端

        Args:
            master_uri: Master节点地址，如 "ws://localhost:8000"
            token: 客户端认证令牌
        """
        self.master_uri = master_uri
        self.token = token
        self._client = None
        self._loop = None
        self._thread = None
        self._connected = False

    def _run_async_loop(self):
        """在单独线程中运行异步事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def setup():
            self._client = LunarisClient(self.master_uri, self.token)
            await self._client.connect()
            self._connected = True

        self._loop.run_until_complete(setup())
        self._loop.run_forever()

    def connect(self):
        """连接到Master节点"""
        if self._connected:
            return

        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()

        # 等待连接建立
        import time

        for _ in range(30):  # 30秒超时
            if self._connected:
                logger.info("Connected to master")
                return
            time.sleep(1)

        raise TimeoutError("Failed to connect within 30 seconds")

    def submit_task(
        self,
        wasm_module: bytes,
        args: Optional[List[Any]] = None,
        entry: str = "main",
        priority: int = 0,
        execution_limits: Optional[ExecutionLimits] = None,
    ) -> str:
        """
        提交WASM任务

        Args:
            wasm_module: WASM模块字节码
            args: 任务参数列表
            entry: 入口函数名
            priority: 任务优先级

        Returns:
            任务ID
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _submit():
            return await self._client.submit_task(  # type: ignore
                wasm_module,
                args,
                entry,
                priority,
                execution_limits=execution_limits,
            )

        return asyncio.run_coroutine_threadsafe(_submit(), self._loop).result()  # type: ignore

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果字典，如果任务不存在则返回None
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_result():
            return await self._client.get_task_result(task_id)  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_result(), self._loop).result()  # type: ignore

    def wait_for_task(
        self, task_id: str, timeout: Optional[float] = None
    ) -> TaskResult:
        """
        等待特定任务完成

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）

        Returns:
            任务结果
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _wait():
            return await self._client.wait_for_task(task_id, timeout)  # type: ignore

        return asyncio.run_coroutine_threadsafe(_wait(), self._loop).result(timeout)  # type: ignore

    def unsubscribe_tasks(self, task_ids: List[str]):
        """
        取消订阅任务结果

        Args:
            task_ids: 要取消订阅的任务ID列表
        """
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _unsubscribe():
            await self._client.unsubscribe_tasks(task_ids)  # type: ignore

        asyncio.run_coroutine_threadsafe(_unsubscribe(), self._loop).result()  # type: ignore

    def close(self):
        """关闭客户端连接"""
        if self._loop and self._loop.is_running():

            async def _close():
                await self._client.close()  # type: ignore

            future = asyncio.run_coroutine_threadsafe(_close(), self._loop)
            try:
                future.result(timeout=5)  # 5秒超时
            except Exception as e:
                logger.warning(f"Error during client close: {e}")

            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5)

        self._connected = False
        logger.info("Client closed")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
