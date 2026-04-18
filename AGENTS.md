# Lunaris Knowledge Base

**Generated:** 2026-04-17
**Commit:** 96f409d
**Branch:** main

## OVERVIEW

Distributed WASM executor with Python services (FastAPI master + Python worker + async/sync SDK) and a high-performance Rust worker. Uses WebSocket for worker communication, Protobuf for protocol, and wasmtime for WASM execution.

## STRUCTURE

```
lunaris/
├── master/     # FastAPI task scheduler + WebSocket endpoint
├── worker/     # Python worker (multiprocessing WASM executor)
├── client/     # SDK (LunarisClient async, SyncLunarisClient)
├── runtime/    # WASM sandbox + ExecutionLimits
├── proto/      # Generated protobuf (DO NOT EDIT)
└── cli/        # argparse entry point
rust-worker/    # Rust worker (wasmtime + mimalloc)
proto/          # Protobuf source definitions
testwasm/       # Sample WASM project (not tests)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add REST endpoint | `lunaris/master/api.py` | FastAPI router, requires auth token |
| Modify task scheduling | `lunaris/master/manager.py` | TaskManager, WorkerManager classes |
| Worker connection logic | `lunaris/worker/main.py` | WebSocket client, heartbeat loop |
| WASM execution limits | `lunaris/runtime/limits.py` | ExecutionLimits dataclass |
| WASM sandbox engine | `lunaris/runtime/engine.py` | WasmSandbox class, wasmtime wrapper |
| Client SDK async | `lunaris/client/client.py` | LunarisClient, submit_task() |
| Client SDK sync | `lunaris/client/sync.py` | SyncLunarisClient wrapper |
| Rust worker core | `rust-worker/src/core.rs` | Worker struct, WebSocket + task dispatch |
| Rust WASM engine | `rust-worker/src/engine.rs` | Runner, run_wasm(), resource limits |
| Protobuf protocol | `proto/*.proto` | Edit source, run build.sh |
| CLI commands | `lunaris/cli/main.py` | master/worker subcommands |

## CODE MAP

### Python Entry Points

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `main()` | Function | `lunaris/cli/main.py:124` | CLI entry, argparse |
| `Worker` | Class | `lunaris/worker/main.py:32` | Python worker node |
| `Runner` | Class | `lunaris/worker/core.py:63` | WASM executor (ProcessPool) |
| `TaskManager` | Class | `lunaris/master/manager.py:154` | Priority queue + task tracking |
| `WorkerManager` | Class | `lunaris/master/manager.py:69` | Worker registration + heartbeat |
| `LunarisClient` | Class | `lunaris/client/client.py:27` | Async SDK |
| `SyncLunarisClient` | Class | `lunaris/client/sync.py:12` | Sync SDK wrapper |
| `WasmSandbox` | Class | `lunaris/runtime/engine.py:21` | WASM execution wrapper |
| `ExecutionLimits` | Class | `lunaris/runtime/limits.py:18` | Resource limit config |
| `IDGenerator` | Class | `lunaris/utils.py:98` | Snowflake ID generator |

### Rust Entry Points

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `Worker` | Struct | `rust-worker/src/core.rs:15` | Worker node (WebSocket + heartbeat) |
| `Runner` | Struct | `rust-worker/src/engine.rs:18` | WASM executor pool |
| `run_wasm()` | Function | `rust-worker/src/engine.rs:126` | WASM execution core |
| `main()` | Function | `rust-worker/src/main.rs:16` | Rust worker entry |

## CONVENTIONS

### Python
- **Type hints**: Required for public APIs, optional internally
- **Naming**: snake_case (functions/vars), PascalCase (classes)
- **Protobuf**: NEVER edit `lunaris/proto/*_pb2.py` - edit `proto/*.proto` then `./proto/build.sh`
- **Imports**: Absolute paths preferred (`from lunaris.client import LunarisClient`)

### Rust
- **Formatting**: Run `cargo fmt` before commit
- **Edition**: 2024 in Cargo.toml (should be 2021 - needs fix)
- **Memory**: Uses `mimalloc` global allocator
- **Async**: tokio runtime, `spawn_blocking` for WASM execution

### Commits
- Style: Short imperative + optional scope (`feat(cli):`, `fix(master):`)
- PRs: Describe behavior change, list validation commands

## ANTI-PATTERNS (THIS PROJECT)

### NEVER Do These

1. **Hard-code tokens**: Use `WORKER_TOKEN` / `CLIENT_TOKEN` env vars
   ```python
   # FORBIDDEN
   token = "my-secret-value"
   # REQUIRED
   token = os.environ.get("WORKER_TOKEN")
   ```

2. **Edit generated protobuf**: Files in `lunaris/proto/*_pb2.py` are auto-generated
   - Fix: Edit `proto/*.proto` → run `./proto/build.sh`

3. **Modify ExecutionLimits defaults carelessly**: Affects worker isolation and safety
   - `max_fuel`, `max_memory_bytes`, `max_module_bytes` impact resource protection

4. **Run tests without master/worker**: Integration tests require live services
   - Current tests (`test_localhost_*.py`) need `ws://localhost:8000`

## UNIQUE STYLES

### Dual Worker Architecture
- Python worker: `lunaris/worker/` - multiprocessing execution
- Rust worker: `rust-worker/` - high-performance, wasmtime + mimalloc
- Both connect to same master via WebSocket

### Protocol Layer
- Envelope wrapper with zstd compression (`lunaris/utils.py:proto2bytes`)
- Message type routing via `MESSAGE_TYPE_MAP`

### Client SDK Design
- Async `LunarisClient` + sync `SyncLunarisClient` with identical API
- Source compilation helpers: `submit_c()`, `submit_rust()`, `submit_go()`, `submit_zig()`

## COMMANDS

### Development
```bash
# Python - install deps
uv sync

# Python - run master
uv run python -m lunaris master --host 127.0.0.1 --port 8000

# Python - run worker
uv run python -m lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN

# Rust - build worker
cd rust-worker && cargo build --release

# Protobuf - regenerate Python bindings
./proto/build.sh
```

### Environment Variables
```bash
WORKER_TOKEN           # Worker authentication
LUNARIS_WORKER_*       # Execution limits overrides
```

### Prerequisites
- `protoc` (protobuf compiler) - required for proto generation
- Python >=3.9, Rust toolchain

## NOTES

- **No CI configured**: Missing `.github/workflows/`
- **No test directory**: Tests scattered at root (`test_localhost_*.py`)
- **Rust edition typo**: Cargo.toml has `edition = "2024"` (non-existent, should be "2021")
- **testwasm purpose**: Sample WASM project, not formal test suite
- See subdirectory AGENTS.md for module-specific details
