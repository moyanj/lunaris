import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Callable, Any
import psutil
from lunaris.proto.worker_pb2 import Task
from lunaris.runtime import WasmResult, WasmSandbox
import orjson
import multiprocessing
from loguru import logger


def _execute_task(
    code: bytes,
    args: list,
    entry: str,
    task_id: str,
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
        sandbox = WasmSandbox()
        result = sandbox.run(
            code,
            *args,
            entry=entry,
        )
        # 将结果和任务ID放入队列
        result_queue.put((result, task_id))
        logger.info(f"Task {task_id} has been completed.")

    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error(f"Error executing task: {str(e)}")
        result = WasmResult(
            result="",
            stdout="",
            stderr=str(e),
            time=0,
            succeeded=False,
        )
        result_queue.put((result, task_id))


class Runner:
    def __init__(
        self, max_workers: int, report_callback: Callable[[WasmResult, str], Any]
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
        """
        持续监听multiprocessing.Queue中的结果，并在收到时调用报告回调。
        """
        logger.info("Start the Runner result listening task.")
        while self._running:
            try:
                # 尝试从队列中获取结果，非阻塞地检查
                if not self.result_queue.empty():
                    result, task_id = self.result_queue.get()
                    logger.info(f"Received result from subprocess: {task_id}")
                    # 在这里调用异步报告回调函数
                    await self.report_callback(result, task_id)
                else:
                    # 如果队列为空，短暂休眠，避免忙等待
                    await asyncio.sleep(0.01)
            except Exception as e:
                import traceback

                traceback.print_exc()

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

        self.executor.submit(
            _execute_task,
            task.wasm_module,
            args,
            task.entry,
            task.task_id,
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
