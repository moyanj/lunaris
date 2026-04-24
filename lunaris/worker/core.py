"""
Worker 核心执行器模块

提供基于多进程的 WASM 任务执行能力。使用 ProcessPoolExecutor 绕过 Python GIL，
实现真正的并行 WASM 执行。

主要组件：
    - _execute_task: 子进程中执行的 WASM 任务函数
    - Runner: 任务执行器，管理进程池和结果监听

架构设计：
    Worker 主进程 (asyncio)
        ↓ submit(task)
    ProcessPoolExecutor
        ↓ _execute_task()
    子进程 (WasmSandbox.run())
        ↓ result_queue.put()
    结果监听 (_listen_results)
        ↓ report_callback()
    Worker 主进程 (结果上报)
"""
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Callable, Any
import psutil
from lunaris.proto.worker_pb2 import Task
from lunaris.runtime import ExecutionLimits, WasmResult, WasmSandbox
import orjson
import multiprocessing
from loguru import logger


def _execute_task(
    code: bytes,
    args: list,
    entry: str,
    env: dict[str, str],
    wasi_args: list[str],
    execution_limits: dict[str, int],
    host_capabilities: list[str],
    task_id: int,
    attempt: int,
    result_queue: multiprocessing.Queue,
):
    """子进程 WASM 执行函数

    在子进程中执行 WASM 模块，并将结果放入结果队列。
    此函数必须是模块级函数（pickle 要求），不能是类方法。

    执行流程：
        1. 从 execution_limits 字典创建 ExecutionLimits 对象
        2. 创建 WasmSandbox 执行环境
        3. 执行 WASM 模块并获取结果
        4. 将结果放入 result_queue

    Args:
        code: WASM 模块字节码
        args: 函数参数列表
        entry: 入口函数名称
        env: WASI 环境变量字典
        wasi_args: WASI 命令行参数列表
        execution_limits: 资源限制字典（用于跨进程传递）
        host_capabilities: 宿主能力列表
        task_id: 任务 ID
        attempt: 任务尝试次数
        result_queue: 结果队列，用于传递执行结果

    Note:
        - 异常会被捕获并转换为失败的 WasmResult
        - 结果格式为 (WasmResult, task_id, attempt) 元组
    """
    logger.info(f"Start executing task: {task_id}")
    try:
        # 从字典创建限制对象（跨进程传递需要）
        limits = ExecutionLimits.from_mapping(execution_limits)
        sandbox = WasmSandbox(limits)
        result = sandbox.run(
            code,
            *args,
            entry=entry,
            task_id=task_id,
            env=env,
            wasi_args=wasi_args,
            execution_limits=limits,
            host_capabilities=host_capabilities,
        )
        # 将结果放入队列，包含任务 ID 和尝试次数
        result_queue.put((result, task_id, attempt))
        logger.info(f"Task {task_id} has been completed.")

    except Exception as e:
        # 捕获所有异常，转换为失败结果
        import traceback

        traceback.print_exc()
        logger.error(f"Error executing task: {str(e)}")
        result = WasmResult(
            result="",
            stdout="".encode("utf-8"),
            stderr=repr(e).encode("utf-8"),
            time=0,
            succeeded=False,
        )
        result_queue.put((result, task_id, attempt))


class Runner:
    """WASM 任务执行器

    管理 ProcessPoolExecutor 进程池，提供异步的任务提交和结果监听。
    通过 multiprocessing.Manager().Queue() 实现跨进程的结果传递。

    Attributes:
        max_workers: 最大工作进程数
        report_callback: 结果回调函数，接收 (WasmResult, task_id, attempt)
        default_execution_limits: 默认资源限制
        max_execution_limits: 最大资源限制（用于钳制用户请求）
    """

    def __init__(
        self,
        max_workers: int,
        report_callback: Callable[[WasmResult, int, int], Any],
        default_execution_limits: Optional[ExecutionLimits] = None,
        max_execution_limits: Optional[ExecutionLimits] = None,
    ):
        """初始化任务执行器

        Args:
            max_workers: 最大工作进程数，0 或负数表示使用 CPU 核心数
            report_callback: 结果回调函数
            default_execution_limits: 默认资源限制
            max_execution_limits: 最大资源限制
        """
        # 设置最大工作进程数，fallback 到 CPU 核心数
        self.max_workers = (
            max_workers if max_workers and max_workers > 0 else psutil.cpu_count()
        )
        # 创建进程间通信的 Manager 和 Queue
        self.manager = multiprocessing.Manager()
        self.result_queue = self.manager.Queue()

        # 创建进程池执行器
        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self.report_callback = report_callback
        self.default_execution_limits = default_execution_limits or ExecutionLimits()
        self.max_execution_limits = max_execution_limits or ExecutionLimits()

        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        """启动结果监听任务

        创建异步任务监听结果队列，将子进程的结果通过回调函数上报。
        必须在 submit() 之前调用。
        """
        if self._running:
            return
        self._running = True

        # 创建异步监听任务
        self._listener_task = asyncio.create_task(self._listen_results())

    async def _listen_results(self):
        """异步结果监听循环

        持续监听结果队列，当有结果时调用回调函数上报。
        使用 0.1 秒的轮询间隔避免忙等待。

        Note:
            - 异常会被捕获并记录日志，不会中断监听循环
            - 异常后等待 1 秒再继续，避免快速循环
        """
        logger.info("Start the Runner result listening task.")
        while self._running:
            try:
                if not self.result_queue.empty():
                    # 从队列获取结果
                    result, task_id, attempt = self.result_queue.get()
                    logger.info(f"Received result from subprocess: {task_id}")
                    # 调用回调函数上报结果
                    await self.report_callback(result, task_id, attempt)
                else:
                    # 队列为空，等待 0.1 秒
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in result listener: {e}")
                # 异常后等待 1 秒，避免快速循环
                await asyncio.sleep(1)

    def submit(self, task: Task) -> None:
        """提交 WASM 任务到进程池

        解析任务参数，钳制资源限制，然后提交到进程池执行。

        Args:
            task: Protobuf Task 消息，包含 WASM 模块和执行参数

        Note:
            - 参数通过 orjson 解析，解析失败则使用空列表
            - 资源限制会经过 default 和 maximum 双重钳制
            - 任务在子进程中异步执行，结果通过 result_queue 传递
        """
        logger.info(f"Submit task {task.task_id} to the runner")
        # 解析 JSON 参数
        try:
            args = orjson.loads(task.args)
        except orjson.JSONDecodeError:
            args = []

        # 提取 WASI 环境变量和参数
        wasi_env = dict(task.wasi_env.env) if task.HasField("wasi_env") else {}
        wasi_args = list(task.wasi_env.args) if task.HasField("wasi_env") else []
        # 提取宿主能力列表
        host_capabilities = (
            list(task.host_capabilities.items) if task.HasField("host_capabilities") else []
        )
        # 钳制资源限制：用户请求 → 默认值 → 最大值
        execution_limits = ExecutionLimits.from_proto(task.execution_limits).clamp(
            defaults=self.default_execution_limits,
            maximums=self.max_execution_limits,
        )

        # 提交到进程池执行
        self.executor.submit(
            _execute_task,
            task.wasm_module,
            args,
            task.entry,
            wasi_env,
            wasi_args,
            execution_limits.to_dict(),
            host_capabilities,
            task.task_id,
            task.attempt,
            self.result_queue,
        )

    async def close(self):
        """关闭执行器

        优雅关闭进程池和监听任务：
        1. 等待所有正在执行的任务完成
        2. 停止结果监听循环
        3. 关闭 Manager

        Note:
            - 关闭后不能再调用 submit()
            - 必须在 Worker 关闭前调用
        """
        logger.info("Shutting down runner...")
        # 等待所有任务完成
        self.executor.shutdown(wait=True)

        # 停止监听循环
        self._running = False
        if self._listener_task:
            await self._listener_task
            self._listener_task = None

        # 关闭 Manager（释放共享内存）
        self.manager.shutdown()
