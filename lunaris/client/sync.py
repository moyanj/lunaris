import asyncio
import threading
from typing import Optional, Dict, Any, List
from lunaris.client.client import LunarisClient
from lunaris.client.utils import CompileOptions, SourceLanguage
from lunaris.proto.common_pb2 import TaskResult
from lunaris.runtime import ExecutionLimits
from loguru import logger
from lunaris.client.client import WasiEnv


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
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        idempotency_key: Optional[str] = None,
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
                wasi_env=wasi_env,
                execution_limits=execution_limits,
                idempotency_key=idempotency_key,
            )

        return asyncio.run_coroutine_threadsafe(_submit(), self._loop).result()  # type: ignore

    def submit_source(
        self,
        language: SourceLanguage,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _submit():
            return await self._client.submit_source(  # type: ignore
                language=language,
                source_code=source_code,
                args=args,
                entry=entry,
                priority=priority,
                wasi_env=wasi_env,
                execution_limits=execution_limits,
                compile_options=compile_options,
                idempotency_key=idempotency_key,
            )

        return asyncio.run_coroutine_threadsafe(_submit(), self._loop).result()  # type: ignore

    def submit_c(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        return self.submit_source(
            "c",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            idempotency_key=idempotency_key,
        )

    def submit_cxx(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        return self.submit_source(
            "cxx",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            idempotency_key=idempotency_key,
        )

    def submit_zig(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        return self.submit_source(
            "zig",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            idempotency_key=idempotency_key,
        )

    def submit_rust(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        return self.submit_source(
            "rust",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            idempotency_key=idempotency_key,
        )

    def submit_go(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        return self.submit_source(
            "go",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            idempotency_key=idempotency_key,
        )

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

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_status():
            return await self._client.get_task_status(task_id)  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_status(), self._loop).result()  # type: ignore

    def get_tasks(self) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_tasks():
            return await self._client.get_tasks()  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_tasks(), self._loop).result()  # type: ignore

    def get_tasks_by_status(self, status: str) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_tasks():
            return await self._client.get_tasks_by_status(status)  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_tasks(), self._loop).result()  # type: ignore

    def get_tasks_by_worker(self, worker_id: str) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_tasks():
            return await self._client.get_tasks_by_worker(worker_id)  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_tasks(), self._loop).result()  # type: ignore

    def get_workers(self) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_workers():
            return await self._client.get_workers()  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_workers(), self._loop).result()  # type: ignore

    def get_stats(self) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Client not connected")

        async def _get_stats():
            return await self._client.get_stats()  # type: ignore

        return asyncio.run_coroutine_threadsafe(_get_stats(), self._loop).result()  # type: ignore

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
