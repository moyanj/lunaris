"""
WASM 执行引擎模块

提供 WASM 沙箱执行环境，基于 wasmtime 实现。
负责加载 WASM 模块、配置执行环境、执行并返回结果。

主要组件：
    - WasmResult: 执行结果数据类
    - WasmSandbox: WASM 执行沙箱，管理整个执行生命周期

执行流程：
    1. 验证模块大小限制
    2. 编译 WASM 模块
    3. 创建 Store 并配置资源限制（内存、燃料）
    4. 配置 WASI 环境（环境变量、参数、标准输出/错误）
    5. 注册宿主能力函数
    6. 实例化模块并执行入口函数
    7. 收集输出并返回结果

注入的环境变量：
    - LUNARIS_TASK_ID: 当前任务 ID（可选）
    - LUNARIS_WORKER_VERSION: Worker 版本号
    - LUNARIS_HOST_CAPABILITIES: 启用的宿主能力（JSON 数组）
"""
import os
import orjson
import time
from dataclasses import dataclass
from importlib import metadata

from wasmtime import Config, Engine, Store, WasiConfig, Module, Linker
import tempfile

from lunaris.runtime.capabilities import HostContext, REGISTRY, normalize_host_capabilities
from lunaris.runtime.limits import ExecutionLimits

# 注入到 WASI 环境的变量名
INJECTED_TASK_ID_ENV = "LUNARIS_TASK_ID"
INJECTED_WORKER_VERSION_ENV = "LUNARIS_WORKER_VERSION"
INJECTED_HOST_CAPABILITIES_ENV = "LUNARIS_HOST_CAPABILITIES"

# Worker 版本号（从 pyproject.toml 读取）
try:
    WORKER_VERSION = metadata.version("lunaris")
except metadata.PackageNotFoundError:
    WORKER_VERSION = "unknown"


@dataclass
class WasmResult:
    """WASM 执行结果

    包含执行的输出、耗时和状态。

    Attributes:
        result: 函数返回值（JSON 字符串）
        stdout: 标准输出内容（字节）
        stderr: 标准错误输出内容（字节）
        time: 执行耗时（毫秒）
        succeeded: 是否执行成功

    Examples:
        >>> result = WasmResult(result='"hello"', stdout=b"", stderr=b"", time=1.5)
        >>> result.succeeded
        True
    """
    result: str
    stdout: bytes
    stderr: bytes
    time: float
    succeeded: bool = True


class WasmSandbox:
    """WASM 执行沙箱

    提供完整的 WASM 执行环境，包括：
    - wasmtime Engine（编译和执行引擎）
    - 资源限制（燃料、内存、模块大小）
    - WASI 环境配置
    - 宿主能力注册

    每次执行创建新的 Store，确保执行隔离。

    Attributes:
        execution_limits: 默认资源限制配置
        engine: wasmtime 编译引擎

    Examples:
        >>> sandbox = WasmSandbox()
        >>> result = sandbox.run(wasm_code, 1, 2, entry="add")
        >>> print(result.result)
        "3"
    """

    def __init__(self, execution_limits: ExecutionLimits | None = None):
        """初始化 WASM 沙箱

        Args:
            execution_limits: 资源限制配置，None 表示无限制

        Note:
            - 如果 max_fuel > 0，启用燃料计量执行
            - Engine 是线程安全的，可在多个线程中使用
        """
        self.execution_limits = execution_limits or ExecutionLimits()
        # 配置 wasmtime Engine
        config = Config()
        # 如果设置了燃料限制，启用燃料消耗
        if self.execution_limits.max_fuel > 0:
            config.consume_fuel = True
        self.engine = Engine(config)

    def run(
        self,
        module_code: bytes,
        *args,
        entry: str = "main",
        task_id: int | None = None,
        env: dict[str, str] | None = None,
        wasi_args: list[str] | None = None,
        execution_limits: ExecutionLimits | None = None,
        host_capabilities: list[str] | None = None,
    ) -> WasmResult:
        """执行 WASM 模块

        完整的 WASM 执行流程：验证、编译、配置、执行、收集结果。

        Args:
            module_code: WASM 模块字节码
            *args: 传递给入口函数的参数
            entry: 入口函数名称（默认 "main"）
            task_id: 任务 ID（可选，会注入到环境变量）
            env: 额外的 WASI 环境变量
            wasi_args: WASI 命令行参数
            execution_limits: 本次执行的资源限制（覆盖默认值）
            host_capabilities: 启用的宿主能力列表

        Returns:
            WasmResult 包含执行结果、输出和耗时

        Raises:
            ValueError: 模块大小超过限制
            wasmtime.Error: WASM 编译或执行错误

        Note:
            - 每次执行创建新的 Store，确保隔离
            - 标准输出/错误通过临时文件捕获
            - 执行完成后自动清理临时文件
        """
        result = ""
        # 使用传入的限制或默认限制
        limits = execution_limits or self.execution_limits

        # 验证模块大小限制
        if limits.max_module_bytes > 0 and len(module_code) > limits.max_module_bytes:
            raise ValueError(
                f"Wasm module too large: {len(module_code)} > {limits.max_module_bytes}"
            )

        # 编译 WASM 模块
        module = Module(self.engine, module_code)
        # 创建 Linker 并定义 WASI
        linker = Linker(self.engine)
        linker.define_wasi()

        # 创建 Store 并配置资源限制
        store = Store(self.engine)
        if limits.max_memory_bytes > 0:
            store.set_limits(memory_size=limits.max_memory_bytes)
        if limits.max_fuel > 0:
            store.set_fuel(limits.max_fuel)

        # 准备 WASI 环境变量
        wasi_env = dict(env or {})
        # 规范化宿主能力
        normalized_capabilities = normalize_host_capabilities(host_capabilities)
        # 注入 Lunaris 特定的环境变量
        if task_id is not None:
            wasi_env[INJECTED_TASK_ID_ENV] = str(task_id)
        wasi_env[INJECTED_WORKER_VERSION_ENV] = WORKER_VERSION
        wasi_env[INJECTED_HOST_CAPABILITIES_ENV] = orjson.dumps(
            normalized_capabilities
        ).decode("utf-8")

        # 配置 WASI
        wasi = WasiConfig()
        wasi.env = list(wasi_env.items())
        wasi.argv = list(wasi_args or [])

        # 创建临时文件用于捕获标准输出/错误
        fd, stdout_temp = tempfile.mkstemp()
        os.close(fd)
        wasi.stdout_file = stdout_temp
        fd, stderr_temp = tempfile.mkstemp()
        os.close(fd)
        wasi.stderr_file = stderr_temp
        store.set_wasi(wasi)

        # 注册宿主能力函数
        REGISTRY.register_all(
            linker,
            store,
            HostContext(enabled_capabilities=frozenset(normalized_capabilities)),
            normalized_capabilities,
        )

        # 实例化模块
        instance = linker.instantiate(store, module)
        # 获取入口函数
        main_func = instance.exports(store)[entry]

        # 执行并计时
        start_time = time.perf_counter()
        result = main_func(store, *args)  # type: ignore
        run_time = time.perf_counter() - start_time

        # 读取标准输出/错误
        with open(stdout_temp, "rb") as f:
            stdout = f.read()
        with open(stderr_temp, "rb") as f:
            stderr = f.read()
        # 清理临时文件
        os.remove(stdout_temp)
        os.remove(stderr_temp)

        # 序列化结果并返回
        try:
            result = orjson.dumps(result).decode("utf-8")

            return WasmResult(
                result=result,
                stdout=stdout,
                stderr=stderr,
                time=run_time * 1000,  # 转换为毫秒
            )
        except Exception as e:
            # 结果序列化失败，返回失败状态
            return WasmResult(
                result="",
                stdout=stdout,
                stderr="".format(e).encode("utf-8"),
                time=run_time * 1000,
                succeeded=False,
            )
