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
    wasi_args: dict[str, str],
    execution_limits: dict[str, int],
    task_id: str,
    attempt: int,
    result_queue: multiprocessing.Queue,
):
    """
    在子进程中执行Wasm模块。这是一个独立的函数。

    Args:
        code: Wasm模块。
        args: 传递给Wasm模块的参数列表。
        entry: Wasm模块的入口点函数名。
        task_id: 任务ID。
        result_queue: 用于将结果传回主进程的multiprocessing.Queue。
    """
    logger.info(f"Start executing task: {task_id}")
    try:
        limits = ExecutionLimits.from_mapping(execution_limits)
        sandbox = WasmSandbox(limits)
        result = sandbox.run(
            code,
            *args,
            entry=entry,
            env=env,
            wasi_args=wasi_args,
            execution_limits=limits,
        )
        # 将结果和任务ID放入队列
        result_queue.put((result, task_id, attempt))
        logger.info(f"Task {task_id} has been completed.")

    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error(f"Error executing task: {str(e)}")
        result = WasmResult(
            result="",
            stdout="".encode("utf-8"),
            stderr=str(e).encode("utf-8"),
            time=0,
            succeeded=False,
        )
        result_queue.put((result, task_id, attempt))


class Runner:
    def __init__(
        self,
        max_workers: int,
        report_callback: Callable[[WasmResult, str, int], Any],
        default_execution_limits: Optional[ExecutionLimits] = None,
        max_execution_limits: Optional[ExecutionLimits] = None,
    ):
        """
        初始化Runner
        """
        self.max_workers = (
            max_workers if max_workers and max_workers > 0 else psutil.cpu_count()
        )
        self.manager = multiprocessing.Manager()
        self.result_queue = self.manager.Queue()  # 用于子进程向主进程发送结果

        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self.report_callback = report_callback  # 存储异步报告函数
        self.default_execution_limits = default_execution_limits or ExecutionLimits()
        self.max_execution_limits = max_execution_limits or ExecutionLimits()

        # 用于控制结果监听循环的标志
        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        """
        启动Runner，包括启动结果监听任务。
        """
        if self._running:
            return
        self._running = True

        # 在事件循环中创建一个异步任务来持续监听结果
        self._listener_task = asyncio.create_task(self._listen_results())

    async def _listen_results(self):
        """持续监听multiprocessing.Queue中的结果"""
        logger.info("Start the Runner result listening task.")
        while self._running:
            try:
                # 使用非阻塞方式检查队列
                if not self.result_queue.empty():
                    result, task_id, attempt = self.result_queue.get()
                    logger.info(f"Received result from subprocess: {task_id}")
                    await self.report_callback(result, task_id, attempt)
                else:
                    # 队列为空时短暂休眠，避免忙等待
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in result listener: {e}")
                await asyncio.sleep(1)  # 错误时等待更长时间

    def submit(self, task: Task) -> None:
        """
        提交一个Wasm模块任务到执行器。

        Args:
            task: 待执行的任务对象。
        """
        logger.info(f"Submit task {task.task_id} to the runner")
        try:
            args = orjson.loads(task.args)
        except orjson.JSONDecodeError:
            args = []
        execution_limits = ExecutionLimits.from_proto(task.execution_limits).clamp(
            defaults=self.default_execution_limits,
            maximums=self.max_execution_limits,
        )

        self.executor.submit(
            _execute_task,
            task.wasm_module,
            args,
            task.entry,
            dict(task.wasi_env.env),  # type: ignore
            list(task.wasi_env.args),  # type: ignore
            execution_limits.to_dict(),
            task.task_id,
            task.attempt,
            self.result_queue,  # type: ignore 将共享队列传递给子进程
        )

    async def close(self):
        """
        关闭执行器，等待所有提交的任务完成，并停止结果监听。
        """
        logger.info("Shutting down runner...")
        self.executor.shutdown(wait=True)  # 等待所有子进程任务完成

        # 停止结果监听任务
        if self._listener_task:
            self._running = False  # 设置标志以退出循环
            await self._listener_task  # 等待监听任务完成
            self._listener_task = None

        # 关闭Manager以释放资源
        self.manager.shutdown()
