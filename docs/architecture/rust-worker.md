# Rust 工作节点

Rust 工作节点是 Lunaris 的高性能工作节点实现，使用 wasmtime 原生库和 mimalloc 内存分配器，适合 CPU 密集型和高频调用场景。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Rust 工作节点                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ WebSocket   │  │  心跳循环   │  │ 任务分发    │     │
│  │ 客户端      │◄─┤             │◄─┤             │     │
│  └─────────────┘  └─────────────┘  └──────┬──────┘     │
│                                           │             │
│                                    ┌──────▼──────┐     │
│                                    │ Semaphore   │     │
│                                    │ 并发控制    │     │
│                                    └──────┬──────┘     │
│                                           │             │
│                                    ┌──────▼──────┐     │
│                                    │ tokio::spawn│     │
│                                    │ _blocking   │     │
│                                    └──────┬──────┘     │
│                                           │             │
│                          ┌────────────────┼────────┐   │
│                          │                │        │   │
│                    ┌─────▼─────┐    ┌─────▼─────┐  │   │
│                    │ Runner 1  │    │ Runner 2  │ ...  │
│                    │ run_wasm()│    │ run_wasm()│  │   │
│                    └───────────┘    └───────────┘  │   │
└─────────────────────────────────────────────────────────┘
```

## 核心优势

### 1. 高性能

- **wasmtime 原生库**：直接使用 Rust wasmtime，无 Python 开销
- **mimalloc 内存分配器**：高性能内存分配
- **零拷贝通信**：高效的 WebSocket 消息处理

### 2. 异步架构

- **tokio 运行时**：多线程异步执行
- **spawn_blocking**：WASM 执行不阻塞异步循环
- **信号量并发控制**：精确控制并行执行数量

### 3. 资源效率

- **低内存占用**：Rust 无 GC 开销
- **快速启动**：编译后的二进制文件秒级启动
- **高效序列化**：prost Protobuf 序列化

## 核心模块

### 1. main.rs - 入口点

```rust
#[global_allocator]
static ALLOC: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 解析命令行参数
    let cli = Cli::parse();
    
    // 创建工作节点
    let worker = Worker::new(
        &cli.master,
        &cli.token,
        cli.name.as_deref(),
        cli.concurrency,
    ).await?;
    
    // 运行工作节点
    worker.run().await?;
    
    Ok(())
}
```

**关键特性**：
- `#[global_allocator]` 使用 mimalloc
- `#[tokio::main]` 多线程运行时
- clap 命令行参数解析

### 2. core.rs - Worker 结构体

```rust
pub struct Worker {
    worker_id: String,
    master_url: String,
    token: String,
    name: Option<String>,
    max_concurrency: usize,
    running: Arc<Mutex<usize>>,
    drain_enabled: Arc<Mutex<bool>>,
    cancelled_tasks: Arc<Mutex<HashSet<String>>>,
}
```

**核心方法**：

```rust
impl Worker {
    pub async fn new(...) -> Result<Self> { ... }
    pub async fn run(&self) -> Result<()> { ... }
    async fn connect(&self) -> Result<WebSocketStream<...>> { ... }
    async fn handle_task(&self, task: Task) -> Result<()> { ... }
    async fn send_heartbeat(&self, ws: &mut WebSocketStream<...>) -> Result<()> { ... }
}
```

**关键流程**：

1. **连接主节点**：WebSocket 连接到 `/worker?token=<token>`
2. **注册**：发送 `WorkerRegister` 消息
3. **心跳循环**：每 10 秒发送 `WorkerHeartbeat`
4. **任务循环**：
   - 接收任务
   - 检查 drain 模式
   - 检查取消状态
   - 获取信号量许可
   - spawn_blocking 执行 WASM
   - 返回结果

### 3. engine.rs - Runner 结构体

```rust
pub struct Runner {
    semaphore: Arc<Semaphore>,
    limits: ExecutionLimits,
}

impl Runner {
    pub fn new(max_concurrency: usize, limits: ExecutionLimits) -> Self {
        Self {
            semaphore: Arc::new(Semaphore::new(max_concurrency)),
            limits,
        }
    }
    
    pub async fn run(&self, task: Task) -> Result<TaskResult> {
        // 获取信号量许可
        let _permit = self.semaphore.acquire().await?;
        
        // 在阻塞线程中执行 WASM
        let result = tokio::task::spawn_blocking(move || {
            run_wasm(&task.wasm_module, &task.args, ...)
        }).await??;
        
        Ok(result)
    }
}
```

### 4. run_wasm() 函数

WASM 执行的核心函数：

```rust
pub fn run_wasm(
    wasm_bytes: &[u8],
    args: &[serde_json::Value],
    entry: &str,
    limits: &ExecutionLimits,
    wasi_env: &WasiEnv,
) -> Result<WasmResult> {
    // 1. 创建配置
    let mut config = Config::new();
    if limits.max_fuel > 0 {
        config.consume_fuel(true);
    }
    
    // 2. 创建引擎和存储
    let engine = Engine::new(&config)?;
    let mut store = Store::new(&engine, ());
    
    // 3. 设置限制
    if limits.max_memory_bytes > 0 {
        store.limiter(|s| &mut s.memory_limit);
    }
    if limits.max_fuel > 0 {
        store.set_fuel(limits.max_fuel)?;
    }
    
    // 4. 配置 WASI
    let wasi = WasiCtx::builder()
        .envs(&wasi_env.env)
        .args(&wasi_env.args)
        .stdout(MemoryOutputPipe::new(1024 * 1024))
        .stderr(MemoryOutputPipe::new(1024 * 1024))
        .build();
    
    // 5. 实例化模块
    let module = Module::new(&engine, wasm_bytes)?;
    let mut linker = Linker::new(&engine);
    wasmtime_wasi::add_to_linker(&mut linker, |s| s)?;
    
    let instance = linker.instantiate(&mut store, &module)?;
    
    // 6. 调用入口函数
    let func = instance.get_func(&mut store, entry)
        .ok_or_else(|| anyhow::anyhow!("Function '{}' not found", entry))?;
    
    let results = func.call(&mut store, args)?;
    
    // 7. 收集输出
    let stdout = wasi.stdout.read()?;
    let stderr = wasi.stderr.read()?;
    
    Ok(WasmResult { result, stdout, stderr, time })
}
```

## 并发控制

### 信号量机制

使用 `tokio::sync::Semaphore` 控制并发：

```rust
// 创建信号量
let semaphore = Arc::new(Semaphore::new(max_concurrency));

// 获取许可
let _permit = semaphore.acquire().await?;

// 执行任务（许可自动释放）
let result = execute_task().await;
```

### 并发状态跟踪

```rust
// 原子计数器跟踪运行中的任务
let running = Arc::new(Mutex::new(0));

// 任务开始
*running.lock().await += 1;

// 任务结束
*running.lock().await -= 1;

// 心跳时报告状态
let state = if *running.lock().await >= max_concurrency {
    NodeState::Busy
} else {
    NodeState::Idle
};
```

## Drain 模式

Drain 模式用于优雅关闭：

```rust
// 启用 drain 模式
*drain_enabled.lock().await = true;

// 接收新任务时检查
if *drain_enabled.lock().await {
    // 不接受新任务，直接返回取消结果
    return TaskResult::cancelled(task_id);
}

// 等待现有任务完成
while *running.lock().await > 0 {
    tokio::time::sleep(Duration::from_millis(100)).await;
}
```

## 任务取消

任务取消通过共享状态实现：

```rust
// 收到取消命令时
cancelled_tasks.lock().await.insert(task_id.clone());

// 执行前检查
if cancelled_tasks.lock().await.contains(&task.task_id) {
    return TaskResult::cancelled(task.task_id);
}
```

## 内存管理

### mimalloc 全局分配器

```rust
#[global_allocator]
static ALLOC: mimalloc::MiMalloc = mimalloc::MiMalloc;
```

**优势**：
- 比系统默认分配器快 20-30%
- 更好的多线程性能
- 更低的内存碎片

### WASM 内存限制

```rust
// 设置 Store 内存限制
store.limiter(
    |s| &mut s.memory_limit,
    limits.max_memory_bytes,
);
```

## 配置选项

### 命令行参数

```bash
./lunaris-worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --name rust-worker-1 \
  --concurrency 8
```

### 编译选项

`Cargo.toml` 中的 release 配置：

```toml
[profile.release]
lto = true              # 链接时优化
codegen-units = 1       # 单代码生成单元
strip = true            # 去除调试符号
opt-level = "s"         # 优化大小
```

## 性能对比

### Rust vs Python 工作节点

| 指标 | Rust 工作节点 | Python 工作节点 |
|------|--------------|----------------|
| 启动时间 | ~10ms | ~500ms |
| 内存占用 | ~10MB | ~50MB |
| WASM 执行开销 | 基准 | +20-30% |
| 并发效率 | 高（异步） | 中（进程池） |
| 隔离性 | 中（线程） | 高（进程） |

### 适用场景

**Rust 工作节点**：
- CPU 密集型任务
- 高频短任务
- 资源受限环境
- 需要低延迟

**Python 工作节点**：
- 需要强隔离性
- 内存泄漏风险高的 WASM
- 需要 Python 生态集成

## 故障处理

### 连接断开

```rust
loop {
    match ws.next().await {
        Some(Ok(msg)) => { ... }
        Some(Err(e)) => {
            // 连接错误，尝试重连
            warn!("WebSocket error: {}", e);
            break;
        }
        None => {
            // 连接关闭，尝试重连
            info!("WebSocket closed, reconnecting...");
            break;
        }
    }
}
```

### WASM 执行错误

```rust
match run_wasm(...) {
    Ok(result) => { ... }
    Err(e) => {
        // 返回错误结果
        TaskResult::failed(task_id, e.to_string())
    }
}
```

## 下一步

- 了解 [通信协议](protocol.md) 的详细规范
- 查看 [部署指南](../deployment/guide.md) 了解生产环境配置
- 阅读 [开发指南](../development/guide.md) 了解如何贡献代码
