from ast import main
from enum import StrEnum
from importlib import import_module
from typing import Any
from io import StringIO
import os
import time
from dataclasses import dataclass

from wasmtime import Engine, Store, WasiConfig, Module, Instance


@dataclass
class WasmResult:
    result: Any
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

        return WasmResult(
            result=result,
            stdout=self.wasm_stdout.getvalue(),
            stderr=self.wasm_stderr.getvalue(),
            time=run_time * 1000,
        )


def lua_dir(table, file, level=0, indent="    ", visited=None, max_depth=5):
    if level > max_depth:
        file.write(f"{indent * level}[达到最大深度{max_depth}]\n")
        return

    if visited is None:
        visited = set()

    # 防止循环引用
    table_id = id(table)
    if table_id in visited:
        file.write(f"{indent * level}[已遍历的表]\n")
        return
    visited.add(table_id)

    try:
        items = list(table.items())
    except Exception as e:
        file.write(f"{indent * level}[遍历错误: {str(e)}]\n")
        return

    for k, v in items:
        if k in ["_G", "loaded"]:
            continue
        try:
            if type(v).__name__ == "_LuaTable":
                file.write(f"{indent * level}{k}:\n")
                lua_dir(v, file, level + 1, indent, visited, max_depth)
            else:
                file.write(f"{indent * level}{k}: {type(v).__name__}\n")
        except Exception as e:
            file.write(f"{indent * level}{k}: [读取错误: {str(e)}]\n")
