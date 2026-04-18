# Worker Module - Python WASM Executor

**Parent:** See root AGENTS.md for project overview

## OVERVIEW

Python worker node: multiprocessing WASM execution, WebSocket connection to master, heartbeat loop.

## WHERE TO LOOK

| Task | File | Key Symbols |
|------|------|-------------|
| Worker lifecycle | `main.py:32` | `Worker.run`, `Worker.shutdown` |
| WebSocket connection | `main.py` | `connect()`, `register()`, heartbeat every 10s |
| Task execution | `core.py:63` | `Runner.submit`, `ProcessPoolExecutor` |
| Subprocess WASM run | `core.py:12` | `_execute_task` (runs in child process) |
| Result reporting | `main.py` | `report_result()`, callback to master |
| Resource limits | `core.py:129` | `ExecutionLimits.from_proto().clamp()` |

## CONVENTIONS

### Multiprocessing Architecture
- `ProcessPoolExecutor` for WASM execution (bypasses Python GIL)
- `multiprocessing.Queue` for subprocess → main result passing
- `_execute_task` is standalone function (pickle requirement)

### Async + ProcessPool Hybrid
- `_listen_results()` asyncio task polls `result_queue`
- `Runner.start()` creates listener task
- `Runner.close()` waits for executor shutdown + listener completion

### Resource Limit Flow
```
proto limits → ExecutionLimits.from_proto() → clamp(defaults, maximums) → WasmSandbox
```

### Heartbeat Pattern
- Interval: 10 seconds
- Status: `NodeStatus.IDLE` or `NodeStatus.BUSY`
- Master timeout: 20 seconds (see master module)

## ANTI-PATTERNS (THIS MODULE)

1. **Skip result listener**: Must call `Runner.start()` before submitting tasks
2. **Direct queue access**: Only `_listen_results()` should read `result_queue`
3. **Manual num_running**: Don't modify - only `Runner.submit()` updates it
4. **Close before shutdown**: Call `runner.close()` before WebSocket disconnect
5. **Ignore ExecutionLimits clamp**: Always clamp against `defaults` and `maximums`