import os
import orjson
import time
from dataclasses import dataclass

from wasmtime import Config, Engine, Store, WasiConfig, Module, Linker
import tempfile

from lunaris.runtime.limits import ExecutionLimits


@dataclass
class WasmResult:
    result: str
    stdout: bytes
    stderr: bytes
    time: float
    succeeded: bool = True


class WasmSandbox:
    def __init__(self, execution_limits: ExecutionLimits | None = None):
        self.execution_limits = execution_limits or ExecutionLimits()
        config = Config()
        if self.execution_limits.max_fuel > 0:
            config.consume_fuel = True
        self.engine = Engine(config)

    def run(
        self,
        module_code: bytes,
        *args,
        entry: str = "main",
        env: dict[str, str] = {},
        wasi_args: dict[str, str] = {},
        execution_limits: ExecutionLimits | None = None,
    ) -> WasmResult:
        """
        执行 Wasm 模块，并返回结果。
        """

        result = ""
        limits = execution_limits or self.execution_limits

        if limits.max_module_bytes > 0 and len(module_code) > limits.max_module_bytes:
            raise ValueError(
                f"Wasm module too large: {len(module_code)} > {limits.max_module_bytes}"
            )

        module = Module(self.engine, module_code)
        linker = Linker(self.engine)
        linker.define_wasi()

        store = Store(self.engine)
        if limits.max_memory_bytes > 0:
            store.set_limits(memory_size=limits.max_memory_bytes)
        if limits.max_fuel > 0:
            store.set_fuel(limits.max_fuel)
        wasi = WasiConfig()

        wasi.env = env
        wasi.argv = wasi_args

        fd, stdout_temp = tempfile.mkstemp()
        os.close(fd)
        wasi.stdout_file = stdout_temp
        fd, stderr_temp = tempfile.mkstemp()
        os.close(fd)
        wasi.stderr_file = stderr_temp
        store.set_wasi(wasi)

        instance = linker.instantiate(store, module)
        main_func = instance.exports(store)[entry]

        start_time = time.perf_counter()
        result = main_func(store, *args)  # type: ignore
        run_time = time.perf_counter() - start_time

        with open(stdout_temp, "rb") as f:
            stdout = f.read()
        with open(stderr_temp, "rb") as f:
            stderr = f.read()
        os.remove(stdout_temp)
        os.remove(stderr_temp)

        try:
            result = orjson.dumps(result).decode("utf-8")

            return WasmResult(
                result=result,
                stdout=stdout,
                stderr=stderr,
                time=run_time * 1000,
            )
        except Exception as e:
            return WasmResult(
                result="",
                stdout=stdout,
                stderr="".format(e).encode("utf-8"),
                time=run_time * 1000,
                succeeded=False,
            )
