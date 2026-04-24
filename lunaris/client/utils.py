"""
多语言源码编译助手

将源代码编译为 WASM 字节码，支持 7 种语言：C、C++、Zig、Rust、Go、AssemblyScript、Grain。
编译过程在本地完成，生成的 WASM 字节码可直接提交到 Lunaris Master 执行。

支持的语言：
    - C: 使用 WASI SDK (wasm32-wasip1-clang) 或 Zig
    - C++: 使用 WASI SDK (wasm32-wasip1-clang++) 或 Zig
    - Zig: 使用 zig build-exe
    - Rust: 使用 rustc 或 cargo
    - Go: 使用 tinygo
    - AssemblyScript: 使用 asc
    - Grain: 使用 grain compile

典型用法：
    from lunaris.client.utils import compile_source

    wasm_bytes = compile_source("rust", source_code)
    # 然后通过 LunarisClient.submit_task() 提交 wasm_bytes
"""
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Sequence


# WASM 编译目标平台
WASI_TARGET = "wasm32-wasip1"

# 默认编译超时时间（秒）
DEFAULT_TIMEOUT_SECONDS = 60

# 支持的源代码语言类型
SourceLanguage = Literal["c", "cxx", "zig", "rust", "go", "assemblyscript", "grain"]

# 各工具链可用性缓存（None 表示尚未检测，True/False 表示检测结果）
HAS_WASI_SDK: Optional[bool] = None
HAS_WASI_SDK_CXX: Optional[bool] = None
HAS_ZIG: Optional[bool] = None
HAS_RUSTC: Optional[bool] = None
HAS_TINY_GO: Optional[bool] = None
HAS_GRAIN: Optional[bool] = None
HAS_ASSEMBLYSCRIPT: Optional[bool] = None


@dataclass
class CompileOptions:
    """编译选项配置

    用于控制源代码编译为 WASM 的行为，包括优化级别、额外编译参数、工具链选择等。

    Attributes:
        optimize_level: 优化级别，可选值取决于目标语言
            - C/C++/Rust/Go: "0", "1", "2", "3", "s", "z"
            - Zig: "0"(Debug), "1"/"2"/"3"(ReleaseFast), "s"(ReleaseSafe), "z"(ReleaseSmall)
            - AssemblyScript: "0", "1", "2", "3"
            - Grain: "s"/"z" 启用优化，其他值不启用
        options: 额外的编译参数列表，将追加到编译命令末尾
        use_zig: 是否使用 Zig 作为 C/C++ 编译器（替代 WASI SDK）
        use_binary: 是否编译为二进制可执行文件（仅 Rust 有效）
        use_cargo: 是否使用 Cargo 构建（仅 Rust 有效，默认 True）

    Examples:
        # 使用默认选项
        options = CompileOptions()

        # 高优化级别 + 自定义参数
        options = CompileOptions(optimize_level="3", options=["-flto"])

        # 使用 Zig 编译 C 代码
        options = CompileOptions(use_zig=True)
    """
    optimize_level: str = "2"
    options: list[str] = field(default_factory=list)
    use_zig: bool = False
    use_binary: bool = False
    use_cargo: bool = True


def _base_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """获取基础环境变量

    复制当前进程的环境变量，并可选择性地添加额外变量。
    用于子进程编译时继承父进程环境。

    Args:
        extra: 要添加或覆盖的环境变量字典

    Returns:
        合并后的环境变量字典
    """
    env = os.environ.copy()
    if extra:
        env.update(extra)
    return env


def _command_exists(command: str) -> bool:
    """检查命令是否存在于系统 PATH 中

    使用 shutil.which 查找命令的完整路径，用于判断工具链是否已安装。

    Args:
        command: 要检查的命令名称

    Returns:
        如果命令存在返回 True，否则返回 False
    """
    return shutil.which(command) is not None


def _run_check(
    args: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> bool:
    """执行命令并检查是否成功

    用于检测工具链是否可用，通过尝试执行命令并检查返回码。
    静默执行，不输出到标准输出/错误。

    Args:
        args: 要执行的命令和参数列表
        cwd: 工作目录，None 表示使用当前目录
        env: 环境变量，None 表示使用 _base_env()

    Returns:
        命令执行成功返回 True，失败返回 False
    """
    try:
        subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            cwd=cwd,
            env=env or _base_env(),
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_wasi_sdk() -> bool:
    """检测 WASI SDK 是否可用

    检查 wasm32-wasip1-clang 编译器是否已安装并可用。
    结果缓存到 HAS_WASI_SDK 全局变量。

    Returns:
        WASI SDK 可用返回 True，否则返回 False
    """
    global HAS_WASI_SDK
    HAS_WASI_SDK = _run_check(["wasm32-wasip1-clang", "--version"])
    return HAS_WASI_SDK


def check_wasi_sdk_cxx() -> bool:
    """检测 WASI SDK C++ 编译器是否可用

    检查 wasm32-wasip1-clang++ 编译器是否已安装并可用。
    结果缓存到 HAS_WASI_SDK_CXX 全局变量。

    Returns:
        WASI SDK C++ 编译器可用返回 True，否则返回 False
    """
    global HAS_WASI_SDK_CXX
    HAS_WASI_SDK_CXX = _run_check(["wasm32-wasip1-clang++", "--version"])
    return HAS_WASI_SDK_CXX


def check_zig() -> bool:
    """检测 Zig 编译器是否可用

    检查 zig 编译器是否已安装并可用。
    结果缓存到 HAS_ZIG 全局变量。

    Returns:
        Zig 编译器可用返回 True，否则返回 False
    """
    global HAS_ZIG
    HAS_ZIG = _run_check(["zig", "version"])
    return HAS_ZIG


def _has_rust_target(target: str) -> bool:
    """检查 Rust 是否已安装指定编译目标

    使用 rustup 命令查询已安装的编译目标列表。

    Args:
        target: 要检查的目标平台，如 "wasm32-wasip1"

    Returns:
        如果目标已安装返回 True，否则返回 False
    """
    if not _command_exists("rustup"):
        return False
    try:
        result = subprocess.run(
            ["rustup", "target", "list", "--installed"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            env=_base_env(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    # 检查目标是否在已安装列表中
    return target in {line.strip() for line in result.stdout.splitlines()}


def check_rustc() -> bool:
    """检测 Rust 编译器是否可用

    检查 rustc 编译器是否已安装，并且 wasm32-wasip1 目标是否已添加。
    结果缓存到 HAS_RUSTC 全局变量。

    Returns:
        Rust 编译器可用且目标已安装返回 True，否则返回 False
    """
    global HAS_RUSTC
    HAS_RUSTC = _command_exists("rustc") and _has_rust_target(WASI_TARGET)
    return HAS_RUSTC


def check_tiny_go() -> bool:
    """检测 TinyGo 编译器是否可用

    创建临时 Go 文件并尝试使用 tinygo 编译为 WASM。
    结果缓存到 HAS_TINY_GO 全局变量。

    检测逻辑：
        1. 创建包含简单 add 函数的临时 Go 文件
        2. 尝试使用 tinygo 编译为 WASM
        3. 编译成功表示可用

    Returns:
        TinyGo 编译器可用返回 True，否则返回 False
    """
    global HAS_TINY_GO
    with tempfile.TemporaryDirectory() as tmpdir:
        test_go = Path(tmpdir) / "test.go"
        # 创建测试用的简单 Go 代码
        test_go.write_text(
            """package main

//go:wasmexport add
func add(x, y uint32) uint32 {
    return x + y
}
""",
            encoding="utf-8",
        )
        HAS_TINY_GO = _run_check(
            [
                "tinygo",
                "build",
                "-buildmode=c-shared",
                "-target=wasip1",
                str(test_go),
            ],
            cwd=tmpdir,
            env=_base_env({"GOARCH": "wasm", "GOOS": "wasip1"}),
        )
    return HAS_TINY_GO


def check_grain() -> bool:
    """检测 Grain 编译器是否可用

    检查 grain 编译器是否已安装并可用。
    结果缓存到 HAS_GRAIN 全局变量。

    Returns:
        Grain 编译器可用返回 True，否则返回 False
    """
    global HAS_GRAIN
    HAS_GRAIN = _run_check(["grain", "--version"])
    return HAS_GRAIN


def check_assemblyscript() -> bool:
    """检测 AssemblyScript 编译器是否可用

    检查 asc (AssemblyScript Compiler) 是否已安装并可用。
    结果缓存到 HAS_ASSEMBLYSCRIPT 全局变量。

    Returns:
        AssemblyScript 编译器可用返回 True，否则返回 False
    """
    global HAS_ASSEMBLYSCRIPT
    HAS_ASSEMBLYSCRIPT = _run_check(["asc", "--version"])
    return HAS_ASSEMBLYSCRIPT


def _read_wasm_file(wasm_path: Path) -> bytes:
    """读取编译生成的 WASM 文件

    检查 WASM 文件是否存在并读取其内容。

    Args:
        wasm_path: WASM 文件路径

    Returns:
        WASM 文件的字节内容

    Raises:
        RuntimeError: WASM 文件不存在（编译可能失败）
    """
    if not wasm_path.exists():
        raise RuntimeError("WASM file was not generated during compilation")
    return wasm_path.read_bytes()


def _compile(
    code: str,
    command: Sequence[str],
    suffix: str,
    *,
    env: Optional[dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """通用编译函数

    将源代码写入临时文件，执行编译命令，返回生成的 WASM 字节码。
    支持命令模板中的占位符替换：
        - {code_file}: 源代码文件路径
        - {wasm_file}: 输出 WASM 文件路径

    Args:
        code: 源代码字符串
        command: 编译命令列表，支持 {code_file} 和 {wasm_file} 占位符
        suffix: 源代码文件扩展名（如 "c", "rs", "go"）
        env: 编译环境变量，None 表示使用 _base_env()
        timeout: 编译超时时间（秒）

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: 编译失败、超时或编译器不存在
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        wasm_path = root / "temp.wasm"
        code_path = root / f"temp.{suffix}"
        # 写入源代码到临时文件
        code_path.write_text(code, encoding="utf-8")

        try:
            # 执行编译命令，替换占位符
            subprocess.run(
                [arg.format(code_file=str(code_path), wasm_file=str(wasm_path)) for arg in command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                cwd=tmpdir,
                timeout=timeout,
                env=env or _base_env(),
            )
        except subprocess.CalledProcessError as exc:
            # 编译失败，提取错误信息
            error_msg = (
                exc.stderr.decode("utf-8", errors="ignore").strip()
                if exc.stderr
                else "Unknown error"
            )
            raise RuntimeError(f"Failed to compile code: {error_msg}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Compilation timed out after {timeout} seconds"
            ) from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Compiler not found. Install the requested toolchain first."
            ) from exc

        return _read_wasm_file(wasm_path)


def compile_c(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
    use_zig: bool = False,
) -> bytes:
    """编译 C 源代码为 WASM

    支持两种编译方式：
        1. WASI SDK (wasm32-wasip1-clang) - 默认
        2. Zig (zig cc) - 当 use_zig=True 时使用

    Args:
        code: C 源代码字符串
        optimize_level: 优化级别，可选 "0", "1", "2", "3", "s", "z"
        options: 额外的编译参数列表
        use_zig: 是否使用 Zig 作为编译器

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: 编译器不可用或编译失败

    Examples:
        # 使用 WASI SDK 编译
        wasm = compile_c('int add(int a, int b) { return a + b; }')

        # 使用 Zig 编译
        wasm = compile_c('int add(int a, int b) { return a + b; }', use_zig=True)
    """
    options = options or []
    if use_zig:
        if HAS_ZIG is None:
            check_zig()
        if not HAS_ZIG:
            raise RuntimeError("Zig is not available")
        return _compile(
            code,
            [
                "zig",
                "cc",
                "-target",
                "wasm32-wasi",
                f"-O{optimize_level}",
                "-o",
                "{wasm_file}",
                *options,
                "{code_file}",
            ],
            "c",
        )

    # 使用 WASI SDK
    if HAS_WASI_SDK is None:
        check_wasi_sdk()
    if not HAS_WASI_SDK:
        raise RuntimeError("wasm32-wasip1-clang is not available")

    return _compile(
        code,
        [
            "wasm32-wasip1-clang",
            f"-O{optimize_level}",
            "-o",
            "{wasm_file}",
            "-Wl,--export-all",  # 导出所有符号
            *options,
            "{code_file}",
        ],
        "c",
    )


def compile_cxx(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
    use_zig: bool = False,
) -> bytes:
    """编译 C++ 源代码为 WASM

    支持两种编译方式：
        1. WASI SDK (wasm32-wasip1-clang++) - 默认
        2. Zig (zig c++) - 当 use_zig=True 时使用

    Args:
        code: C++ 源代码字符串
        optimize_level: 优化级别，可选 "0", "1", "2", "3", "s", "z"
        options: 额外的编译参数列表
        use_zig: 是否使用 Zig 作为编译器

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: 编译器不可用或编译失败
    """
    options = options or []
    if use_zig:
        if HAS_ZIG is None:
            check_zig()
        if not HAS_ZIG:
            raise RuntimeError("Zig is not available")
        return _compile(
            code,
            [
                "zig",
                "c++",
                "-target",
                "wasm32-wasi",
                f"-O{optimize_level}",
                "-o",
                "{wasm_file}",
                *options,
                "{code_file}",
            ],
            "cpp",
        )

    # 使用 WASI SDK
    if HAS_WASI_SDK_CXX is None:
        check_wasi_sdk_cxx()
    if not HAS_WASI_SDK_CXX:
        raise RuntimeError("wasm32-wasip1-clang++ is not available")

    return _compile(
        code,
        [
            "wasm32-wasip1-clang++",
            f"-O{optimize_level}",
            "-o",
            "{wasm_file}",
            "-Wl,--export-all",  # 导出所有符号
            *options,
            "{code_file}",
        ],
        "cpp",
    )


def compile_zig(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
) -> bytes:
    """编译 Zig 源代码为 WASM

    使用 zig build-exe 命令编译。

    Args:
        code: Zig 源代码字符串
        optimize_level: 优化级别，映射关系：
            - "0": Debug
            - "1"/"2"/"3": ReleaseFast
            - "s": ReleaseSafe
            - "z": ReleaseSmall
        options: 额外的编译参数列表

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: Zig 编译器不可用或编译失败
    """
    options = options or []
    if HAS_ZIG is None:
        check_zig()
    if not HAS_ZIG:
        raise RuntimeError("Zig is not available")

    # Zig 优化级别映射
    optimize_level_map = {
        "0": "Debug",
        "1": "ReleaseFast",
        "2": "ReleaseFast",
        "3": "ReleaseFast",
        "s": "ReleaseSafe",
        "z": "ReleaseSmall",
    }
    zig_opt = optimize_level_map.get(optimize_level, "ReleaseFast")
    return _compile(
        code,
        [
            "zig",
            "build-exe",
            "-target",
            "wasm32-wasi",
            "-O",
            zig_opt,
            "-femit-bin={wasm_file}",
            *options,
            "{code_file}",
        ],
        "zig",
    )


def compile_rust(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
    use_binary: bool = False,
    use_cargo: bool = True,
) -> bytes:
    """编译 Rust 源代码为 WASM

    支持两种编译方式：
        1. Cargo 构建（默认）- 创建临时 Cargo 项目，适合复杂代码
        2. rustc 直接编译 - 适合简单代码，速度更快

    Args:
        code: Rust 源代码字符串
        optimize_level: 优化级别，可选 "0", "1", "2", "3", "s", "z"
        options: 额外的编译参数（RUSTFLAGS）
        use_binary: 是否编译为二进制可执行文件（默认 False，编译为 cdylib）
        use_cargo: 是否使用 Cargo 构建（默认 True）

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: Rust 工具链不可用或编译失败

    Examples:
        # 编译为库（默认）
        wasm = compile_rust('pub fn add(a: i32, b: i32) -> i32 { a + b }')

        # 编译为二进制
        wasm = compile_rust('fn main() { println!("Hello"); }', use_binary=True)

        # 使用 rustc 直接编译
        wasm = compile_rust('...', use_cargo=False)
    """
    options = options or []
    if HAS_RUSTC is None:
        check_rustc()
    if not HAS_RUSTC:
        raise RuntimeError(
            f"Rust toolchain for target {WASI_TARGET} is not available. "
            f"Install it with: rustup target add {WASI_TARGET}"
        )

    if use_cargo:
        return _compile_rust_with_cargo(
            code,
            optimize_level=optimize_level,
            options=options,
            use_binary=use_binary,
        )

    # 使用 rustc 直接编译
    crate_type = "bin" if use_binary else "cdylib"
    return _compile(
        code,
        [
            "rustc",
            "{code_file}",
            "--crate-type",
            crate_type,
            "--target",
            WASI_TARGET,
            "-o",
            "{wasm_file}",
            "-C",
            f"opt-level={optimize_level}",
            *options,
        ],
        "rs",
    )


def _compile_rust_with_cargo(
    code: str,
    *,
    optimize_level: str,
    options: list[str],
    use_binary: bool,
) -> bytes:
    """使用 Cargo 编译 Rust 代码

    创建临时 Cargo 项目，包含完整的项目结构，然后执行 cargo build。
    适合需要依赖或复杂构建配置的代码。

    Args:
        code: Rust 源代码字符串
        optimize_level: 优化级别
        options: 额外的编译参数（RUSTFLAGS）
        use_binary: 是否编译为二进制可执行文件

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: Cargo 不可用或编译失败
    """
    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("cargo is not available")

    with tempfile.TemporaryDirectory(prefix="lunaris-client-rust-") as tmpdir:
        root = Path(tmpdir)
        src_dir = root / "src"
        src_dir.mkdir()

        # 根据编译类型创建不同的 Cargo.toml
        if use_binary:
            manifest = """
[package]
name = "lunaris_client_compile"
version = "0.1.0"
edition = "2021"
"""
            source_path = src_dir / "main.rs"
            wasm_path = root / f"target/{WASI_TARGET}/release/lunaris_client_compile.wasm"
        else:
            manifest = """
[package]
name = "lunaris_client_compile"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]
"""
            source_path = src_dir / "lib.rs"
            wasm_path = root / f"target/{WASI_TARGET}/release/lunaris_client_compile.wasm"

        # 写入 Cargo.toml 和源代码
        (root / "Cargo.toml").write_text(manifest.strip() + "\n", encoding="utf-8")
        source_path.write_text(code, encoding="utf-8")

        # 设置编译环境
        env = _base_env()
        if options:
            env["RUSTFLAGS"] = " ".join(options)

        try:
            subprocess.run(
                [
                    cargo,
                    "build",
                    "--release",
                    "--target",
                    WASI_TARGET,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                cwd=tmpdir,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            # 提取编译错误信息
            error_msg = (
                exc.stderr.decode("utf-8", errors="ignore").strip()
                if exc.stderr
                else "Unknown error"
            )
            raise RuntimeError(f"Failed to compile Rust code: {error_msg}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Rust compilation timed out after {DEFAULT_TIMEOUT_SECONDS} seconds"
            ) from exc

        return _read_wasm_file(wasm_path)


def compile_go(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
) -> bytes:
    """编译 Go 源代码为 WASM

    使用 TinyGo 编译器将 Go 代码编译为 WASM。

    Args:
        code: Go 源代码字符串
        optimize_level: 优化级别（TinyGo 支持有限，"s"/"z" 启用优化）
        options: 额外的编译参数列表

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: TinyGo 编译器不可用或编译失败
    """
    options = options or []
    if HAS_TINY_GO is None:
        check_tiny_go()
    if not HAS_TINY_GO:
        raise RuntimeError("tinygo is not available")

    return _compile(
        code,
        [
            "tinygo",
            "build",
            "-target",
            "wasm",
            "-o",
            "{wasm_file}",
            *options,
            "{code_file}",
        ],
        "go",
    )


def compile_assemblyscript(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
) -> bytes:
    """编译 AssemblyScript 源代码为 WASM

    使用 asc (AssemblyScript Compiler) 编译器。

    Args:
        code: AssemblyScript 源代码字符串
        optimize_level: 优化级别，可选 "0", "1", "2", "3"
        options: 额外的编译参数列表

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: AssemblyScript 编译器不可用或编译失败
    """
    options = options or []
    if HAS_ASSEMBLYSCRIPT is None:
        check_assemblyscript()
    if not HAS_ASSEMBLYSCRIPT:
        raise RuntimeError("AssemblyScript compiler 'asc' is not available")

    # AssemblyScript 优化级别限制在 0-3
    asc_optimize_level = optimize_level if optimize_level in {"0", "1", "2", "3"} else "2"
    return _compile(
        code,
        [
            "asc",
            "{code_file}",
            "--outFile",
            "{wasm_file}",
            f"-O{asc_optimize_level}",
            "--runtime",
            "stub",  # 使用精简运行时
            "--use",
            "abort=",  # 禁用 abort 函数
            *options,
        ],
        "ts",
    )


def compile_grain(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
) -> bytes:
    """编译 Grain 源代码为 WASM

    使用 grain compile 命令编译。

    Args:
        code: Grain 源代码字符串
        optimize_level: 优化级别，"s"/"z" 启用优化，其他值不启用
        options: 额外的编译参数列表

    Returns:
        编译生成的 WASM 字节码

    Raises:
        RuntimeError: Grain 编译器不可用或编译失败
    """
    options = options or []
    if HAS_GRAIN is None:
        check_grain()
    if not HAS_GRAIN:
        raise RuntimeError("Grain compiler is not available")

    # Grain 优化选项
    grain_options = list(options)
    if optimize_level in {"s", "z"}:
        grain_options = ["--optimize"] + grain_options

    return _compile(
        code,
        [
            "grain",
            "compile",
            "{code_file}",
            "-o",
            "{wasm_file}",
            *grain_options,
        ],
        "gr",
    )


def compile_source(
    language: SourceLanguage,
    code: str,
    compile_options: Optional[CompileOptions] = None,
) -> bytes:
    """通用源代码编译接口

    根据指定的语言类型，调用相应的编译函数将源代码编译为 WASM。
    这是客户端 SDK 的主要编译入口。

    Args:
        language: 源代码语言，支持 "c", "cxx", "zig", "rust", "go", "assemblyscript", "grain"
        code: 源代码字符串
        compile_options: 编译选项，None 表示使用默认选项

    Returns:
        编译生成的 WASM 字节码

    Raises:
        ValueError: 不支持的语言类型
        RuntimeError: 编译器不可用或编译失败

    Examples:
        # 编译 Rust 代码
        wasm = compile_source("rust", "pub fn add(a: i32, b: i32) -> i32 { a + b }")

        # 编译 C 代码（高优化级别）
        options = CompileOptions(optimize_level="3")
        wasm = compile_source("c", "int add(int a, int b) { return a + b; }", options)
    """
    compile_options = compile_options or CompileOptions()

    if language == "c":
        return compile_c(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
            use_zig=compile_options.use_zig,
        )
    if language == "cxx":
        return compile_cxx(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
            use_zig=compile_options.use_zig,
        )
    if language == "zig":
        return compile_zig(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
        )
    if language == "rust":
        return compile_rust(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
            use_binary=compile_options.use_binary,
            use_cargo=compile_options.use_cargo,
        )
    if language == "go":
        return compile_go(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
        )
    if language == "assemblyscript":
        return compile_assemblyscript(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
        )
    if language == "grain":
        return compile_grain(
            code,
            optimize_level=compile_options.optimize_level,
            options=compile_options.options,
        )

    raise ValueError(f"Unsupported source language: {language}")
