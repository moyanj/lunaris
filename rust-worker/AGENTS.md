# Rust工作节点 - 高性能WASM执行器

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

Rust工作节点实现：tokio异步运行时，wasmtime WASM引擎，mimalloc内存分配器，WebSocket通信。支持drain模式、任务取消、宿主能力注入。

## 项目结构

```
src/
├── main.rs            # 入口，#[global_allocator]，tokio::main
├── core.rs            # Worker结构体，WebSocket，心跳，任务分发
├── engine.rs          # Runner，run_wasm()，WASI上下文，限制
├── cli.rs             # clap参数解析
├── proto.rs           # Protobuf绑定（prost）
└── capabilities/      # 宿主能力模块
```

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| 工作节点入口 | `main.rs:16` | `main()`, `Worker::new()` |
| WebSocket循环 | `core.rs:326` | `Worker.run`, `handle_task` |
| WASM执行 | `engine.rs:192` | `run_wasm`, `spawn_blocking` |
| 并发控制 | `engine.rs:60` | `Semaphore`, `max concurrency` |
| 限制解析 | `engine.rs:397` | `clamp_limits`, `resolve_limit` |
| WASI配置 | `engine.rs` | `WasiCtx::builder()`, `envs()`, `args()` |
| 输出捕获 | `engine.rs` | `MemoryOutputPipe` 用于stdout/stderr |
| 宿主能力 | `capabilities/` | `CapabilityHostState`, `enabled_capabilities` |
| Drain模式 | `core.rs` | `drain_enabled`, 优雅关闭 |
| 任务取消 | `core.rs` | `cancelled_tasks`, 取消跟踪 |
| 心跳状态 | `core.rs:160` | `NodeState::Busy/Idle`, 10秒间隔 |

## 开发约定

### 异步架构
- `#[tokio::main]` - 多线程运行时
- `spawn_blocking` 执行WASM（非阻塞，必须使用）
- `Arc<Mutex<T>>` 共享状态（`running`, `num_running`, `drain_enabled`, `cancelled_tasks`）
- `mpsc::channel(100)` 结果传递

### 内存管理
- `#[global_allocator] static ALLOC: mimalloc::MiMalloc` - 高性能分配器
- `StoreLimitsBuilder` 设置WASM内存边界
- 发布版启用 `lto = true`, `codegen-units = 1`, `strip = true`

### WASM执行
- 每个任务：新 `Store`, `Module`, `Linker`, `Instance`
- 燃料：`store.set_fuel()` + `consume_fuel(true)`
- JSON参数 → WASM Val转换在 `run_wasm`
- 支持Reactor模式（`_initialize` 入口点检测）

### 信号量并发
- `Arc<Semaphore>` 限制并行WASM执行数量
- 提交前获取许可证

### Drain模式
- `drain_enabled` 标志控制是否进入排空模式
- 排空模式下不接受新任务，直接返回取消结果

### 任务取消
- `cancelled_tasks: Arc<Mutex<HashSet<String>>>` 跟踪已取消的任务
- 收到取消请求的任务直接返回失败结果

## 反模式（本模块）

1. **跳过cargo fmt**：提交前运行 `cargo fmt`
2. **异步中阻塞WASM**：必须使用 `spawn_blocking`，不能直接调用
3. **忽略信号量**：提交前必须获取许可证
4. **手动编辑proto.rs**：由 `prost-build` 在 `build.rs` 中生成
5. **忽略drain模式**：进入drain模式后应等待现有任务完成再关闭
6. **重用Store跨任务**：每个任务创建独立Store
