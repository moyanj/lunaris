from ast import main
from enum import StrEnum
from importlib import import_module
import json
from typing import Any
from io import StringIO
import os
import time
from dataclasses import dataclass

from wasmtime import Engine, Store, WasiConfig, Module, Instance


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
        执行 Lua 代码，并返回结果。
        """
        start_time = time.perf_counter()
        result = ""
        module = Module(self.engine, module_code)
        instance = Instance(self.store, module, [])
        main_func = instance.exports(self.store)[entry]
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
