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
    logger.info(f"Start executing task: {task_id}")
    try:
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
        result_queue.put((result, task_id, attempt))
        logger.info(f"Task {task_id} has been completed.")

    except Exception as e:
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
    def __init__(
        self,
        max_workers: int,
        report_callback: Callable[[WasmResult, int, int], Any],
        default_execution_limits: Optional[ExecutionLimits] = None,
        max_execution_limits: Optional[ExecutionLimits] = None,
    ):
        self.max_workers = (
            max_workers if max_workers and max_workers > 0 else psutil.cpu_count()
        )
        self.manager = multiprocessing.Manager()
        self.result_queue = self.manager.Queue()

        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self.report_callback = report_callback
        self.default_execution_limits = default_execution_limits or ExecutionLimits()
        self.max_execution_limits = max_execution_limits or ExecutionLimits()

        self._listener_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True

        self._listener_task = asyncio.create_task(self._listen_results())

    async def _listen_results(self):
        logger.info("Start the Runner result listening task.")
        while self._running:
            try:
                if not self.result_queue.empty():
                    result, task_id, attempt = self.result_queue.get()
                    logger.info(f"Received result from subprocess: {task_id}")
                    await self.report_callback(result, task_id, attempt)
                else:
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in result listener: {e}")
                await asyncio.sleep(1)

    def submit(self, task: Task) -> None:
        logger.info(f"Submit task {task.task_id} to the runner")
        try:
            args = orjson.loads(task.args)
        except orjson.JSONDecodeError:
            args = []

        wasi_env = dict(task.wasi_env.env) if task.HasField("wasi_env") else {}
        wasi_args = list(task.wasi_env.args) if task.HasField("wasi_env") else []
        host_capabilities = (
            list(task.host_capabilities.items) if task.HasField("host_capabilities") else []
        )
        execution_limits = ExecutionLimits.from_proto(task.execution_limits).clamp(
            defaults=self.default_execution_limits,
            maximums=self.max_execution_limits,
        )

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
        logger.info("Shutting down runner...")
        self.executor.shutdown(wait=True)

        self._running = False
        if self._listener_task:
            await self._listener_task
            self._listener_task = None

        self.manager.shutdown()
