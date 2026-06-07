import unittest

from lunaris.client.utils import check_rustc, compile_rust
from lunaris.runtime.engine import WasmSandbox

WASI_P1_STDIO_ENV_ARGS = r"""
#[no_mangle]
pub extern "C" fn wmain() -> i32 {
    let env_value = std::env::var("LUNARIS_WASI_P1").unwrap_or_else(|_| "missing".to_string());
    let arg_value = std::env::args().nth(1).unwrap_or_else(|| "missing".to_string());

    println!("stdout env={env_value} arg={arg_value}");
    eprintln!("stderr env={env_value} arg={arg_value}");

    if env_value == "preview1" && arg_value == "alpha" {
        42
    } else {
        -1
    }
}
"""


WASI_P1_NO_PREOPEN_FS = r"""
#[no_mangle]
pub extern "C" fn wmain() -> i32 {
    match std::fs::read_to_string("/workspace/input.txt") {
        Ok(_) => 1,
        Err(err) => {
            eprintln!("fs_error={err}");
            0
        }
    }
}
"""


@unittest.skipUnless(check_rustc(), "rustc with wasm32-wasip1 target is required")
class WasiPreview1SupportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sandbox = WasmSandbox()

    def test_supports_stdio_env_and_args(self) -> None:
        wasm = compile_rust(WASI_P1_STDIO_ENV_ARGS)

        result = self.sandbox.run(
            wasm,
            entry="wmain",
            env={"LUNARIS_WASI_P1": "preview1"},
            wasi_args=["lunaris-test", "alpha"],
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(result.result, "42")
        self.assertIn(b"stdout env=preview1 arg=alpha", result.stdout)
        self.assertIn(b"stderr env=preview1 arg=alpha", result.stderr)

    def test_filesystem_access_is_not_exposed_without_preopens(self) -> None:
        wasm = compile_rust(WASI_P1_NO_PREOPEN_FS)

        result = self.sandbox.run(
            wasm,
            entry="wmain",
            wasi_args=["lunaris-test"],
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(result.result, "0")
        self.assertIn(b"fs_error=", result.stderr)


if __name__ == "__main__":
    unittest.main()
