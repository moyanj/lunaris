# Client Module - SDK for WASM Task Submission

**Parent:** See root AGENTS.md for project overview

## OVERVIEW

User SDK: async `LunarisClient` + sync `SyncLunarisClient`, WebSocket task submission, multi-language source compilation helpers.

## WHERE TO LOOK

| Task | File | Key Symbols |
|------|------|-------------|
| Async client | `client.py:27` | `LunarisClient.connect`, `submit_task` |
| Sync wrapper | `sync.py:12` | `SyncLunarisClient` (thread + asyncio loop) |
| Submit with callback | `client.py:53` | `submit_task(callback=...)` |
| Wait for result | `client.py:421` | `wait_for_task(task_id, timeout)` |
| Source compilation | `utils.py` | `compile_source`, `compile_c/rust/go/zig` |
| Compiler detection | `utils.py` | `check_wasi_sdk`, `check_rustc`, `HAS_*` globals |
| REST fallback | `client.py:333` | `_get_rest_data` for status queries |

## CONVENTIONS

### Dual Client Pattern
- `LunarisClient`: async WebSocket client with callback-based results
- `SyncLunarisClient`: wraps async client with `asyncio.run_coroutine_threadsafe`
- Identical API surface: `submit_task`, `wait_for_task`, `get_task_result`

### Callback Mechanism
- Callback can be sync or async function
- Called in `_receive_messages()` when `TaskResult` arrives
- Removed after invocation (one-shot)

### Source Compilation
- `submit_c/cxx/zig/rust/go`: shorthand for `submit_source(language, code)`
- Compilation happens locally, WASM bytes sent to master
- Global `HAS_*` flags cache compiler availability

### Context Manager
- `async with LunarisClient(...)` - auto connect/close
- `with SyncLunarisClient(...)` - auto connect/close (sync version)

## ANTI-PATTERNS (THIS MODULE)

1. **Connect before submit**: Must call `connect()` or use context manager
2. **Timeout without cleanup**: Use `wait_for_task(timeout)` + handle `TimeoutError`
3. **Hard-code compiler paths**: Use `check_*` functions to verify toolchain
4. **Skip callback registration**: For async results, register callback or use `wait_for_task`
5. **REST for task submission**: WebSocket is primary; REST is fallback for status only