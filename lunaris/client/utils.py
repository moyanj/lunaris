import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Sequence


WASI_TARGET = "wasm32-wasip1"
DEFAULT_TIMEOUT_SECONDS = 60
SourceLanguage = Literal["c", "cxx", "zig", "rust", "go", "assemblyscript", "grain"]

HAS_WASI_SDK: Optional[bool] = None
HAS_WASI_SDK_CXX: Optional[bool] = None
HAS_ZIG: Optional[bool] = None
HAS_RUSTC: Optional[bool] = None
HAS_TINY_GO: Optional[bool] = None
HAS_GRAIN: Optional[bool] = None
HAS_ASSEMBLYSCRIPT: Optional[bool] = None


@dataclass
class CompileOptions:
    optimize_level: str = "2"
    options: list[str] = field(default_factory=list)
    use_zig: bool = False
    use_binary: bool = False
    use_cargo: bool = True


def _base_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    env = os.environ.copy()
    if extra:
        env.update(extra)
    return env


def _command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def _run_check(
    args: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> bool:
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
    global HAS_WASI_SDK
    HAS_WASI_SDK = _run_check(["wasm32-wasip1-clang", "--version"])
    return HAS_WASI_SDK


def check_wasi_sdk_cxx() -> bool:
    global HAS_WASI_SDK_CXX
    HAS_WASI_SDK_CXX = _run_check(["wasm32-wasip1-clang++", "--version"])
    return HAS_WASI_SDK_CXX


def check_zig() -> bool:
    global HAS_ZIG
    HAS_ZIG = _run_check(["zig", "version"])
    return HAS_ZIG


def _has_rust_target(target: str) -> bool:
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
    return target in {line.strip() for line in result.stdout.splitlines()}


def check_rustc() -> bool:
    global HAS_RUSTC
    HAS_RUSTC = _command_exists("rustc") and _has_rust_target(WASI_TARGET)
    return HAS_RUSTC


def check_tiny_go() -> bool:
    global HAS_TINY_GO
    with tempfile.TemporaryDirectory() as tmpdir:
        test_go = Path(tmpdir) / "test.go"
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
    global HAS_GRAIN
    HAS_GRAIN = _run_check(["grain", "--version"])
    return HAS_GRAIN


def check_assemblyscript() -> bool:
    global HAS_ASSEMBLYSCRIPT
    HAS_ASSEMBLYSCRIPT = _run_check(["asc", "--version"])
    return HAS_ASSEMBLYSCRIPT


def _read_wasm_file(wasm_path: Path) -> bytes:
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
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        wasm_path = root / "temp.wasm"
        code_path = root / f"temp.{suffix}"
        code_path.write_text(code, encoding="utf-8")

        try:
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
            "-Wl,--export-all",
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
            "-Wl,--export-all",
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
    options = options or []
    if HAS_ZIG is None:
        check_zig()
    if not HAS_ZIG:
        raise RuntimeError("Zig is not available")

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
    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("cargo is not available")

    with tempfile.TemporaryDirectory(prefix="lunaris-client-rust-") as tmpdir:
        root = Path(tmpdir)
        src_dir = root / "src"
        src_dir.mkdir()

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

        (root / "Cargo.toml").write_text(manifest.strip() + "\n", encoding="utf-8")
        source_path.write_text(code, encoding="utf-8")

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
    options = options or []
    if HAS_ASSEMBLYSCRIPT is None:
        check_assemblyscript()
    if not HAS_ASSEMBLYSCRIPT:
        raise RuntimeError("AssemblyScript compiler 'asc' is not available")

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
            "stub",
            "--use",
            "abort=",
            *options,
        ],
        "ts",
    )


def compile_grain(
    code: str,
    optimize_level: str = "2",
    options: Optional[list[str]] = None,
) -> bytes:
    options = options or []
    if HAS_GRAIN is None:
        check_grain()
    if not HAS_GRAIN:
        raise RuntimeError("Grain compiler is not available")

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
