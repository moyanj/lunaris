import asyncio
import json
from typing import Callable, Optional, Dict, Any, List, Union
from websockets import connect, ConnectionClosed
from lunaris.proto.client_pb2 import CreateTask, UnsubscribeTask, TaskCreated
from lunaris.proto.common_pb2 import TaskResult
from lunaris.utils import proto2bytes, bytes2proto


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
        self._create_futures = {}  # 存储任务创建的未来对象
        self._running = False
        self._receive_task = None
        self._message_queue = asyncio.Queue()  # 消息队列

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
        entry: str = "main",
        priority: int = 0,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        提交WASM任务

        Args:
            wasm_module: WASM模块字节码
            args: 任务参数列表
            entry: 入口函数名
            priority: 任务优先级
            callback: 任务完成回调函数

        Returns:
            任务ID
        """
        if not self.websocket:
            raise RuntimeError("Client not connected")

        if type(wasm_module) is str:
            wasm_module = wasm_module.encode("utf-8")

        create_task = CreateTask(
            wasm_module=wasm_module,  # type: ignore
            args=json.dumps(args or []),
            entry=entry,
            priority=priority,
        )

        # 创建未来对象来等待任务创建响应
        future = asyncio.Future()
        # 暂时存储future，在收到TaskCreated时会设置它
        self._create_futures["pending"] = future

        await self.websocket.send(proto2bytes(create_task))

        # 等待任务创建确认
        try:
            task_id = await asyncio.wait_for(future, timeout=10.0)

            if callback:
                self._task_callbacks[task_id] = callback

            return task_id
        except asyncio.TimeoutError:
            self._create_futures.pop("pending", None)
            raise RuntimeError("Task creation timeout")

    '''
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        通过HTTP API获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果字典，如果任务不存在则返回None
        """
        import aiohttp

        # 从master_uri中提取HTTP地址
        http_uri = self.master_uri.replace("ws://", "http://").replace(
            "wss://", "https://"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{http_uri}/task/{task_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data")
                else:
                    return None
    '''

    async def unsubscribe_tasks(self, task_ids: List[str]):
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
                    if "pending" in self._create_futures:
                        future = self._create_futures.pop("pending")
                        if not future.done():
                            future.set_result(result.task_id)

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
        self, task_id: str, timeout: Optional[float] = None
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
        if not self.websocket:
            raise RuntimeError("Client not connected")

        future = asyncio.Future()

        async def callback(result):
            if not future.done():
                future.set_result(result)

        self._task_callbacks[task_id] = callback

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self._task_callbacks.pop(task_id, None)
            raise

    async def close(self):
        """关闭客户端连接"""
        self._running = False

        # 取消所有未完成的任务创建
        for future in self._create_futures.values():
            if not future.done():
                future.cancel()

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
