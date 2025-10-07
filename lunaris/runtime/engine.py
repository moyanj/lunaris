import json
from io import StringIO
import time
from dataclasses import dataclass

from wasmtime import Engine, Store, WasiConfig, Module, Linker


@dataclass
class WasmResult:
    result: str
    stdout: str
    stderr: str
    time: float
    succeeded: bool = True


class WasmSandbox:
    def __init__(self):
        self.engine = Engine()
        self.store = Store(self.engine)
        self.wasm_stdout = StringIO()
        self.wasm_stderr = StringIO()

        self.init()

    def init(self):
        wasi = WasiConfig()
        # wasi.stdout_file = self.wasm_stdout
        # wasi.stderr_file = self.wasm_stderr
        self.store.set_wasi(wasi)

    def run(
        self,
        module_code: bytes,
        *args,
        entry: str = "main",
        name="<script>",
    ) -> WasmResult:
        """
        执行 Wasm 模块，并返回结果。
        """

        result = ""

        module = Module(self.engine, module_code)
        linker = Linker(self.engine)
        linker.define_wasi()
        instance = linker.instantiate(self.store, module)
        main_func = instance.exports(self.store)[entry]
        start_time = time.perf_counter()
        result = main_func(self.store, *args)  # type: ignore
        run_time = time.perf_counter() - start_time

        try:
            result = json.dumps(result)

            return WasmResult(
                result=result,
                stdout=self.wasm_stdout.getvalue(),
                stderr=self.wasm_stderr.getvalue(),
                time=run_time * 1000,
            )
        except Exception as e:
            return WasmResult(
                result="",
                stdout=self.wasm_stdout.getvalue(),
                stderr="".format(e),
                time=run_time * 1000,
                succeeded=False,
            )
