from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from lunaris.client.client import LunarisClient
from lunaris.client.sync import SyncLunarisClient
from lunaris.client.utils import CompileOptions, compile_source


class CompileSourceDispatchTest(TestCase):
    def test_supports_assemblyscript(self) -> None:
        with patch("lunaris.client.utils.compile_assemblyscript", return_value=b"wasm") as mocked:
            result = compile_source("assemblyscript", "export function wmain(): i32 { return 1; }")
        self.assertEqual(result, b"wasm")
        mocked.assert_called_once()

    def test_supports_grain(self) -> None:
        with patch("lunaris.client.utils.compile_grain", return_value=b"wasm") as mocked:
            result = compile_source("grain", "export let wmain = (): Int32 => 1")
        self.assertEqual(result, b"wasm")
        mocked.assert_called_once()


class AsyncClientSourceShortcutTest(IsolatedAsyncioTestCase):
    async def test_submit_assemblyscript_uses_submit_source(self) -> None:
        client = LunarisClient("ws://localhost:8000", "token")
        client.submit_source = AsyncMock(return_value=123)

        task_id = await client.submit_assemblyscript(
            "export function wmain(a: i32, b: i32): i32 { return a + b; }",
            args=[1, 2],
            compile_options=CompileOptions(),
        )

        self.assertEqual(task_id, 123)
        client.submit_source.assert_awaited_once()
        self.assertEqual(client.submit_source.await_args.args[0], "assemblyscript")

    async def test_submit_grain_uses_submit_source(self) -> None:
        client = LunarisClient("ws://localhost:8000", "token")
        client.submit_source = AsyncMock(return_value=456)

        task_id = await client.submit_grain(
            "export let wmain = (a: Int32, b: Int32): Int32 => a + b",
            args=[1, 2],
            compile_options=CompileOptions(),
        )

        self.assertEqual(task_id, 456)
        client.submit_source.assert_awaited_once()
        self.assertEqual(client.submit_source.await_args.args[0], "grain")


class SyncClientSourceShortcutTest(TestCase):
    def test_submit_assemblyscript_uses_submit_source(self) -> None:
        client = SyncLunarisClient("ws://localhost:8000", "token")
        with patch.object(client, "submit_source", return_value=789) as mocked:
            task_id = client.submit_assemblyscript(
                "export function wmain(a: i32, b: i32): i32 { return a + b; }"
            )
        self.assertEqual(task_id, 789)
        self.assertEqual(mocked.call_args.args[0], "assemblyscript")

    def test_submit_grain_uses_submit_source(self) -> None:
        client = SyncLunarisClient("ws://localhost:8000", "token")
        with patch.object(client, "submit_source", return_value=321) as mocked:
            task_id = client.submit_grain(
                "export let wmain = (a: Int32, b: Int32): Int32 => a + b"
            )
        self.assertEqual(task_id, 321)
        self.assertEqual(mocked.call_args.args[0], "grain")

