import asyncio
from dataclasses import dataclass, field
import json
import secrets
from typing import Callable, Optional, Dict, Any, List, Union
from urllib import request
from urllib.error import HTTPError
from websockets import connect, ConnectionClosed
from lunaris.proto.client_pb2 import (
    CreateTask,
    TaskCreateFailed,
    TaskCreated,
    UnsubscribeTask,
)
from lunaris.proto.common_pb2 import TaskResult
from lunaris.utils import proto2bytes, bytes2proto
from lunaris.runtime import ExecutionLimits
from lunaris.client.utils import CompileOptions, SourceLanguage, compile_source


@dataclass
class WasiEnv:
    env: Dict[str, str] = field(default_factory=dict)
    args: List[str] = field(default_factory=list)


class LunarisClient:
    def __init__(self, master_uri: str, token: str):
        """
        异步客户端

        Args:
            master_uri: Master节点地址，如 "ws://localhost:8000"
            token: 客户端认证令牌
        """
        self.master_uri = master_uri
        self.token = token
        self.websocket = None
        self._task_callbacks = {}
        self._create_futures = {}
        self._running = False
        self._receive_task = None

    async def connect(self):
        """连接到Master节点"""
        try:
            self.websocket = await connect(f"{self.master_uri}/task?token={self.token}")
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_messages())
        except Exception as e:
            raise

    async def submit_task(
        self,
        wasm_module: Union[bytes, str],
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
        host_capabilities: Optional[List[str]] = None,
    ) -> int:
        """
        提交WASM任务

        Args:
            wasm_module: WASM模块字节码
            args: 任务参数列表
            entry: 入口函数名
            priority: 任务优先级
            execution_limits: 执行资源限制
            callback: 任务完成回调函数

        Returns:
            任务ID
        """
        if not self.websocket:
            raise RuntimeError("Client not connected")

        if type(wasm_module) is str:
            wasm_module = wasm_module.encode("utf-8")

        request_id = secrets.token_hex(16)
        create_task = CreateTask(
            wasm_module=wasm_module,  # type: ignore
            args=json.dumps(args or []),
            entry=entry,
            priority=priority,
            wasi_env=wasi_env.__dict__ if wasi_env else {},
            execution_limits=execution_limits.to_dict() if execution_limits else {},
            request_id=request_id,
            idempotency_key=idempotency_key or "",
            host_capabilities={"items": host_capabilities or []},
        )

        # 创建未来对象来等待任务创建响应
        future = asyncio.get_running_loop().create_future()
        self._create_futures[request_id] = future

        await self.websocket.send(proto2bytes(create_task))

        # 等待任务创建确认
        try:
            task_id = await asyncio.wait_for(future, timeout=10.0)

            if callback:
                self._task_callbacks[task_id] = callback

            return task_id
        except asyncio.TimeoutError:
            self._create_futures.pop(request_id, None)
            raise RuntimeError("Task creation timeout")

    async def submit_source(
        self,
        language: SourceLanguage,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
        host_capabilities: Optional[List[str]] = None,
    ) -> int:
        wasm_module = compile_source(language, source_code, compile_options)
        return await self.submit_task(
            wasm_module=wasm_module,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            callback=callback,
            idempotency_key=idempotency_key,
            host_capabilities=host_capabilities,
        )

    async def submit_c(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "c",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_cxx(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "cxx",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_zig(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "zig",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_rust(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "rust",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_go(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "go",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_assemblyscript(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "assemblyscript",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_grain(
        self,
        source_code: str,
        args: Optional[List[Any]] = None,
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        compile_options: Optional[CompileOptions] = None,
        callback: Optional[Callable] = None,
        idempotency_key: Optional[str] = None,
    ) -> int:
        return await self.submit_source(
            "grain",
            source_code,
            args=args,
            entry=entry,
            priority=priority,
            wasi_env=wasi_env,
            execution_limits=execution_limits,
            compile_options=compile_options,
            callback=callback,
            idempotency_key=idempotency_key,
        )

    async def submit_task_many(
        self,
        wasm_module: Union[bytes, str],
        args_list: List[List[Any]],
        entry: str = "wmain",
        priority: int = 0,
        wasi_env: Optional[WasiEnv] = None,
        execution_limits: Optional[ExecutionLimits] = None,
        timeout: Optional[float] = None,
    ) -> List[TaskResult]:
        """
        并发提交多个任务，除 args 外其他参数相同
        Args:
            wasm_module: WASM模块字节码
            args_list: 多组参数列表，每个元素是一个 args 列表
            entry: 入口函数名
            priority: 任务优先级
            wasi_env: 环境参数
            timeout: 超时时间（秒）
        Returns:
            所有任务结果列表，顺序与 args_list 一致
        """
        futures = []
        task_ids = []
        # 提交所有任务并为每个任务创建 future
        for args in args_list:
            future = asyncio.Future()
            # 提交任务
            task_id = await self.submit_task(
                wasm_module=wasm_module,
                args=args,
                entry=entry,
                priority=priority,
                wasi_env=wasi_env,
                execution_limits=execution_limits,
                callback=lambda result, fut=future: fut.set_result(result),
            )
            task_ids.append(task_id)
            futures.append(future)
        try:
            # 使用 asyncio.wait 等待所有 future 完成
            done, pending = await asyncio.wait(
                futures, timeout=timeout, return_when=asyncio.ALL_COMPLETED
            )
            if pending:
                # 可选：取消未完成的任务
                await self.unsubscribe_tasks(
                    [task_ids[i] for i, f in enumerate(futures) if f in pending]
                )
                raise asyncio.TimeoutError(f"Timeout waiting for {len(pending)} tasks")
            # 返回结果，保持顺序
            return [future.result() for future in futures]
        except asyncio.TimeoutError:
            raise

    async def get_task_result(self, task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务结果（REST 接口）

        通过 REST API 查询任务的完整信息，包括执行结果、输出、状态等。

        Args:
            task_id: 任务 ID

        Returns:
            任务信息字典，包含：
                - task_id: 任务 ID
                - status: 任务状态
                - result: 执行结果（JSON 字符串）
                - stdout: 标准输出
                - stderr: 标准错误输出
                - time: 执行耗时
            如果任务不存在返回 None

        Examples:
            >>> result = await client.get_task_result(123)
            >>> if result:
            ...     print(result["result"])
        """
        return await self._get_rest_data(f"/task/{task_id}")

    async def get_task_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务状态（REST 接口）

        通过 REST API 查询任务的轻量级状态信息，不包含完整的执行结果。

        Args:
            task_id: 任务 ID

        Returns:
            任务状态字典，包含：
                - task_id: 任务 ID
                - status: 任务状态（CREATED/QUEUED/LEASED/RUNNING/SUCCEEDED/FAILED）
                - worker_id: 执行任务的 Worker ID（如果已分配）
                - attempt: 当前尝试次数
            如果任务不存在返回 None

        Examples:
            >>> status = await client.get_task_status(123)
            >>> if status:
            ...     print(status["status"])
        """
        return await self._get_rest_data(f"/task/{task_id}/status")

    async def get_tasks(self) -> Dict[str, Any]:
        """获取所有任务列表（REST 接口）

        通过 REST API 查询所有任务的摘要信息。

        Returns:
            包含任务列表的字典：
                - count: 任务总数
                - tasks: 任务摘要列表

        Examples:
            >>> tasks = await client.get_tasks()
            >>> print(f"Total tasks: {tasks['count']}")
        """
        return await self._get_rest_data("/tasks") or {"count": 0, "tasks": []}

    async def get_tasks_by_status(self, status: str) -> Dict[str, Any]:
        """按状态获取任务列表（REST 接口）

        通过 REST API 查询指定状态的任务列表。

        Args:
            status: 任务状态，可选值：
                - CREATED: 已创建
                - QUEUED: 排队中
                - LEASED: 已分配
                - RUNNING: 运行中
                - SUCCEEDED: 成功
                - FAILED: 失败

        Returns:
            包含任务列表的字典：
                - count: 任务数量
                - tasks: 任务摘要列表

        Examples:
            >>> running_tasks = await client.get_tasks_by_status("RUNNING")
            >>> print(f"Running tasks: {running_tasks['count']}")
        """
        return await self._get_rest_data(f"/tasks/status/{status}") or {
            "count": 0,
            "tasks": [],
        }

    async def get_tasks_by_worker(self, worker_id: str) -> Dict[str, Any]:
        """按 Worker 获取任务列表（REST 接口）

        通过 REST API 查询分配给指定 Worker 的任务列表。

        Args:
            worker_id: Worker 节点 ID

        Returns:
            包含任务列表的字典：
                - count: 任务数量
                - tasks: 任务摘要列表

        Examples:
            >>> worker_tasks = await client.get_tasks_by_worker("worker-abc123")
            >>> print(f"Tasks on worker: {worker_tasks['count']}")
        """
        return await self._get_rest_data(f"/tasks/worker/{worker_id}") or {
            "count": 0,
            "tasks": [],
        }

    async def get_workers(self) -> Dict[str, Any]:
        """获取所有 Worker 列表（REST 接口）

        通过 REST API 查询所有已连接的 Worker 节点信息。

        Returns:
            包含 Worker 列表的字典：
                - count: Worker 数量
                - workers: Worker 信息列表，每个包含：
                    - node_id: 节点 ID
                    - status: 节点状态
                    - last_heartbeat: 最后心跳时间

        Examples:
            >>> workers = await client.get_workers()
            >>> print(f"Connected workers: {workers['count']}")
        """
        return await self._get_rest_data("/worker") or {"count": 0, "workers": []}

    async def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息（REST 接口）

        通过 REST API 查询系统的统计信息，包括任务状态分布、Worker 数量等。

        Returns:
            统计信息字典，包含：
                - total_tasks: 任务总数
                - tasks_by_status: 按状态分布的任务数
                - connected_workers: 已连接的 Worker 数
                - running_tasks: 正在运行的任务数

        Examples:
            >>> stats = await client.get_stats()
            >>> print(f"Total tasks: {stats.get('total_tasks', 0)}")
        """
        return await self._get_rest_data("/stats") or {}

    async def _get_rest_data(self, path: str) -> Optional[Dict[str, Any]]:
        def _fetch():
            url = f"{self._http_base_uri()}{path}"
            req = request.Request(url, headers={"X-Client-Token": self.token})
            try:
                with request.urlopen(req, timeout=10) as response:
                    body = response.read()
            except HTTPError as exc:
                if exc.code == 404:
                    return None
                error_body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc

            payload = json.loads(body)
            if payload.get("code") == 404:
                return None
            if payload.get("code", 200) >= 400:
                raise RuntimeError(payload.get("msg", "Request failed"))
            return payload.get("data")

        return await asyncio.to_thread(_fetch)

    def _http_base_uri(self) -> str:
        if self.master_uri.startswith("ws://"):
            return "http://" + self.master_uri[len("ws://") :]
        if self.master_uri.startswith("wss://"):
            return "https://" + self.master_uri[len("wss://") :]
        return self.master_uri.rstrip("/")

    async def unsubscribe_tasks(self, task_ids: List[int]):
        """
        取消订阅任务结果

        Args:
            task_ids: 要取消订阅的任务ID列表
        """
        if not self.websocket:
            raise RuntimeError("Client not connected")

        unsubscribe = UnsubscribeTask(task_id=task_ids)
        await self.websocket.send(proto2bytes(unsubscribe))

        # 移除回调
        for task_id in task_ids:
            self._task_callbacks.pop(task_id, None)

    async def _receive_messages(self):
        """接收来自Master的消息"""
        while self._running and self.websocket:
            try:
                message = await self.websocket.recv(decode=False)
                result = bytes2proto(message)

                # 处理任务创建响应
                if isinstance(result, TaskCreated):
                    future = self._create_futures.pop(result.request_id, None)
                    if future:
                        if not future.done():
                            future.set_result(result.task_id)

                elif isinstance(result, TaskCreateFailed):
                    future = self._create_futures.pop(result.request_id, None)
                    if future:
                        if not future.done():
                            future.set_exception(RuntimeError(result.error))

                # 处理任务结果
                elif isinstance(result, TaskResult):
                    task_id = result.task_id

                    # 调用回调函数
                    callback = self._task_callbacks.get(task_id)
                    if callback:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(result)
                            else:
                                callback(result)
                        except Exception as e:
                            pass
                        # 移除已完成的回调
                        self._task_callbacks.pop(task_id, None)

            except ConnectionClosed:
                break
            except Exception as e:
                await asyncio.sleep(1)  # 避免频繁错误

    async def wait_for_task(
        self, task_id: int, timeout: Optional[float] = None
    ) -> TaskResult:
        """
        等待特定任务完成

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）

        Returns:
            任务结果

        Raises:
            asyncio.TimeoutError: 如果超时
        """
        deadline = None if timeout is None else asyncio.get_running_loop().time() + timeout

        while True:
            status = await self.get_task_status(task_id)
            if status is None:
                raise RuntimeError("Task not found")

            task_status = status.get("status")
            if task_status in {"succeeded", "failed", "cancelled"}:
                result = await self.get_task_result(task_id)
                if result is None:
                    raise RuntimeError("Task reached terminal state without persisted result")
                return TaskResult(
                    task_id=task_id,
                    result=result.get("result", ""),
                    stdout=result.get("stdout", "").encode("utf-8"),
                    stderr=result.get("stderr", "").encode("utf-8"),
                    time=result.get("time", 0),
                    succeeded=bool(result.get("succeeded", False)),
                    attempt=result.get("attempt", 0),
                )

            if deadline is not None and asyncio.get_running_loop().time() >= deadline:
                raise asyncio.TimeoutError()

            await asyncio.sleep(0.2)

    async def close(self):
        """关闭客户端连接"""
        self._running = False

        # 取消所有未完成的任务创建
        for future in self._create_futures.values():
            if not future.done():
                future.cancel()
        self._create_futures.clear()

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
