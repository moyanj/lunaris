from enum import StrEnum
from importlib import import_module
from typing import Any
from io import StringIO
import os
import time
from dataclasses import dataclass
import lunaris.runtime.libs as libs

from lupa import LuaRuntime, LuaSyntaxError, LuaMemoryError, LuaError, lua_type


class LuaVersion(StrEnum):
    LUA_51 = "lua51"
    LUA_52 = "lua52"
    LUA_53 = "lua53"
    LUA_54 = "lua54"
    LUA_JIT_20 = "luajit20"
    LUA_JIT_21 = "luajit21"


@dataclass
class LuaResult:
    result: Any
    stdout: str
    stderr: str
    time: float


class LuaSandbox:
    def __init__(self, version: LuaVersion = LuaVersion.LUA_54):
        self.lua_version = version
        self.lupa_module = import_module(f"lupa.{version}")
        self.lua: LuaRuntime = self.lupa_module.LuaRuntime(
            register_eval=False, register_builtins=False, unpack_returned_tuples=True
        )
        self.lua_stdout = StringIO()
        self.lua_stderr = StringIO()

        self._setup_sandbox()
        self._setup_hooks()

    def to_table(self, obj: dict):
        return self.lua.table_from(obj, recursive=True)

    def _setup_sandbox(self):
        # 清除全局环境
        self.lua.execute("local _G = {}")
        self.lua.execute("local _ENV = {}")
        self.lua.execute("local package = {}")

        # 禁用元表操作
        self.lua.execute("getmetatable = function() end")
        self.lua.execute("setmetatable = function() end")
        self.lua.execute("rawget = function() end")
        self.lua.execute("rawset = function() end")

        # 禁用调试功能
        self.lua.execute("debug = {}")

        # 禁用文件操作
        self.lua.execute("loadfile = function() end")
        self.lua.execute("dofile = function() end")

        # 禁用外部调用函数
        self.lua.execute("pcall = function() end")
        self.lua.execute("xpcall = function() end")
        self.lua.execute("load = function() end")

    def _setup_hooks(self):
        lua_globals = self.lua.globals()

        # 自定义 print 函数
        def safe_print(*args):
            self.lua_stdout.write(" ".join(map(str, args)) + "\n")

        # 自定义 error 处理
        def safe_error(msg):
            self.lua_stderr.write(f"Lua error: {msg}\n")

        # 设置全局钩子
        lua_globals["require"] = self._lua_require  # type: ignore
        lua_globals["print"] = safe_print  # type: ignore
        lua_globals["error"] = safe_error  # type: ignore
        lua_globals["io"] = self.to_table(  # type: ignore
            {
                "stdout": self.lua_stdout,
                "stderr": self.lua_stderr,
                "stdin": None,  # 显式禁用 stdin
            }
        )
        lua_globals["os"] = self.to_table(  # type: ignore
            {
                "getenv": lambda key: os.environ.get(key),
                "clock": time.time,
                "date": lambda fmt, t=None: time.strftime(
                    fmt, time.localtime(t) if t else time.localtime()
                ),
                "difftime": lambda x, y: float(y) - float(x),
                "time": lambda _: time.time(),
            }
        )
        self.lua.execute(
            "package.available_packages = {"
            + ",".join([f'"{x}"' for x in libs.LIBS])
            + "}"
        )

    def _lua_require(self, modulename: str) -> object:
        if modulename in libs.LIBS:
            attr = getattr(libs, modulename)
            if type(attr) == dict:
                return self.to_table(attr)
            else:
                return attr
        else:
            raise LuaError("module not found: " + modulename)

    def run(
        self,
        code: str,
        *args,
        main_func: str = "main",
        name="<script>",
    ) -> LuaResult:
        """
        执行 Lua 代码，并返回结果。
        """
        start_time = time.perf_counter()
        result = ""
        try:
            self.lua.execute(code, name=name)
            result = self.lua.eval(f"{main_func}(...)", *args, name=name)
        except LuaSyntaxError as e:
            self.lua_stderr.write(str(e))
        except LuaMemoryError as e:
            self.lua.gccollect()
            self.lua_stderr.write("Error: Memory limit exceeded.")
        except LuaError as e:
            self.lua_stderr.write("Error: " + str(e))
        except Exception as e:
            self.lua_stderr.write("Python Error: " + str(e))
        run_time = time.perf_counter() - start_time

        return LuaResult(
            result=result,
            stdout=self.lua_stdout.getvalue(),
            stderr=self.lua_stderr.getvalue(),
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
