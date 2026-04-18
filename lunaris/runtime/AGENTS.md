# Runtime Module - WASM Execution Layer

**Parent:** See root AGENTS.md for project overview

## OVERVIEW

WASM execution sandbox: wasmtime wrapper, WASI environment, execution limits (fuel, memory, module size).

## WHERE TO LOOK

| Task | File | Key Symbols |
|------|------|-------------|
| WASM execution | `engine.py:21` | `WasmSandbox.run`, wasmtime Store/Module/Linker |
| Resource limits | `limits.py:18` | `ExecutionLimits`, `clamp()` |
| Limit resolution | `limits.py:76` | `_resolve_limit(requested, default, maximum)` |
| WASI config | `engine.py:59` | `WasiConfig`, env/argv/stdout_file |
| Result format | `engine.py:12` | `WasmResult` dataclass |

## CONVENTIONS

### WASM Execution Flow
```
WasmSandbox(limits) → run(code, args, entry) → Module → Linker → Store → Instance → main_func()
```

### Limit Semantics
- **0 = unlimited**: Non-zero values enforce limits
- **Three-layer resolution**: `requested → default → maximum`
  - If requested ≤ 0, use default
  - If maximum > 0 and (requested > maximum), use maximum

### WASI Setup
- `WasiConfig.env` - environment variables dict
- `WasiConfig.argv` - command line args list
- Stdout/stderr via temp files (`tempfile.mkstemp`)

### Fuel-based Execution
- `Config.consume_fuel = True` if `max_fuel > 0`
- `store.set_fuel(max_fuel)` before instantiation
- Out-of-fuel traps execution

## ANTI-PATTERNS (THIS MODULE)

1. **Skip limit clamp**: Always clamp user limits against defaults and maximums
2. **Large modules**: Check `max_module_bytes` before instantiation
3. **Temp file cleanup**: Temp stdout/stderr are auto-deleted; don't rely on them persisting
4. **Reuse Store**: Each `run()` creates new Store - don't reuse
5. **Ignore fuel trap**: Low fuel may cause incomplete execution