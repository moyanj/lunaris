import os
import sys
import orjson
from io import StringIO
import time
from dataclasses import dataclass

from wasmtime import Engine, Store, WasiConfig, Module, Linker
import tempfile


@dataclass
class WasmResult:
    result: str
    stdout: bytes
    stderr: bytes
    time: float
    succeeded: bool = True


class WasmSandbox:
    def __init__(self):
        self.engine = Engine()

    def run(
        self,
        module_code: bytes,
        *args,
        entry: str = "main",
        env: dict[str, str] = {},
        wasi_args: dict[str, str] = {},
    ) -> WasmResult:
        """
        执行 Wasm 模块，并返回结果。
        """

        result = ""

        module = Module(self.engine, module_code)
        linker = Linker(self.engine)
        linker.define_wasi()

        store = Store(self.engine)
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
