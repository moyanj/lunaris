# Python 工作节点

Python 工作节点是 Lunaris 的默认工作节点实现，基于 Python wasmtime 绑定，使用多进程架构执行 WASM 模块。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Python 工作节点                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ WebSocket   │  │  心跳循环   │  │ 任务分发    │     │
│  │ 客户端      │◄─┤             │◄─┤             │     │
│  └─────────────┘  └─────────────┘  └──────┬──────┘     │
│                                           │             │
│                                    ┌──────▼──────┐     │
│                                    │ ProcessPool │     │
│                                    │ Executor    │     │
│                                    └──────┬──────┘     │
│                                           │             │
│                          ┌────────────────┼────────┐   │
│                          │                │        │   │
│                    ┌─────▼─────┐    ┌─────▼─────┐  │   │
│                    │ 进程 1    │    │ 进程 2    │ ...  │
│                    │ WasmSandbox│    │ WasmSandbox│  │   │
│                    └───────────┘    └───────────┘  │   │
└─────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. Worker 类 (`main.py`)

工作节点的主入口，负责：

- **WebSocket 连接**：连接到主节点
- **心跳循环**：定期发送心跳
- **任务接收**：从主节点接收任务
- **任务分发**：将任务分发给 Runner 执行

```python
class Worker:
    def __init__(
        self,
        master_uri: str,
        token: str,
        name: Optional[str] = None,
        max_concurrency: int = 4,
        default_execution_limits: ExecutionLimits = ExecutionLimits(),
        max_execution_limits: ExecutionLimits = ExecutionLimits(),
    ): ...
    
    async def run(self) -> None: ...
    async def shutdown(self) -> None: ...
```

**关键流程**：

1. **连接主节点**：通过 WebSocket 连接到 `/worker?token=<token>`
2. **注册**：发送 `WorkerRegister` 消息
3. **心跳循环**：每 10 秒发送 `WorkerHeartbeat`
4. **任务循环**：接收任务 → 分发执行 → 返回结果

### 2. Runner 类 (`core.py`)

WASM 执行器，管理进程池：

```python
class Runner:
    def __init__(
        self,
        max_workers: int = 4,
        default_execution_limits: ExecutionLimits = ExecutionLimits(),
    ): ...
    
    async def run(
        self,
        wasm_module: bytes,
        args: List[Any],
        entry: str = "wmain",
        wasi_env: Optional[Dict[str, Any]] = None,
        execution_limits: Optional[ExecutionLimits] = None,
    ) -> TaskResult: ...
```

**关键特性**：

- **进程池**：使用 `ProcessPoolExecutor` 并行执行
- **隔离性**：每个 WASM 执行在独立进程中
- **超时控制**：支持任务执行超时
- **资源限制**：应用 `ExecutionLimits`

### 3. WasmSandbox 类 (`runtime/engine.py`)

WASM 执行沙箱，封装 wasmtime：

```python
class WasmSandbox:
    def __init__(self, execution_limits: ExecutionLimits | None = None): ...
    
    def run(
        self,
        module_code: bytes,
        *args,
        entry: str = "main",
        env: dict[str, str] = {},
        wasi_args: dict[str, str] = {},
        execution_limits: ExecutionLimits | None = None,
    ) -> WasmResult: ...
```

**执行流程**：

1. **验证模块大小**：检查 `max_module_bytes` 限制
2. **创建 Engine**：如果启用燃料，配置 `consume_fuel = True`
3. **创建 Store**：设置内存和燃料限制
4. **配置 WASI**：设置环境变量、参数、标准输出/错误
5. **实例化模块**：使用 Linker 实例化 WASM 模块
6. **执行入口函数**：调用指定的入口函数
7. **收集结果**：读取标准输出/错误，返回 `WasmResult`

### 4. ExecutionLimits 类 (`runtime/limits.py`)

资源限制配置：

```python
@dataclass
class ExecutionLimits:
    max_fuel: int = 0           # 燃料限制（指令计数）
    max_memory_bytes: int = 0   # 内存限制（字节）
    max_module_bytes: int = 0   # 模块大小限制（字节）
    
    def clamp(
        self,
        defaults: Optional["ExecutionLimits"] = None,
        maximums: Optional["ExecutionLimits"] = None,
    ) -> "ExecutionLimits": ...
```

**限制解析逻辑**：

```python
def _resolve_limit(requested: int, default: int, maximum: int) -> int:
    effective = requested if requested > 0 else default
    if maximum > 0 and (effective <= 0 or effective > maximum):
        return maximum
    return max(effective, 0)
```

## 任务执行流程

```
主节点发送任务
      │
      ▼
┌─────────────────┐
│ 接收任务        │◄─── WebSocket 消息
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 验证限制        │◄─── 应用 max_execution_limits
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 提交到进程池    │◄─── ProcessPoolExecutor.submit()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 创建 WasmSandbox│◄─── 每个任务独立沙箱
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 执行 WASM       │◄─── wasmtime Store/Module/Linker
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 收集结果        │◄─── stdout/stderr/result
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 返回结果        │◄─── TaskResult Protobuf 消息
└─────────────────┘
```

## 心跳状态

工作节点根据当前负载报告状态：

```python
class NodeState(Enum):
    IDLE = "idle"      # 当前任务数 < max_concurrency
    BUSY = "busy"      # 当前任务数 == max_concurrency
```

心跳消息包含：

```python
WorkerHeartbeat(
    worker_id=self.worker_id,
    state=NodeState.BUSY if self.current_tasks >= self.max_concurrency else NodeState.IDLE,
    current_tasks=self.current_tasks,
    max_concurrency=self.max_concurrency,
)
```

## 配置选项

### 命令行参数

```bash
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --name my-worker \
  --concurrency 8 \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912
```

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `WORKER_TOKEN` | 工作节点认证令牌 |
| `LUNARIS_WORKER_MAX_FUEL` | 燃料限制覆盖 |
| `LUNARIS_WORKER_MAX_MEMORY_BYTES` | 内存限制覆盖 |

## 性能考虑

### 进程池大小

`--concurrency` 参数控制并行 WASM 执行数量：

- **CPU 密集型**：设置为 CPU 核心数
- **I/O 密集型**：可以设置更高
- **内存受限**：根据可用内存调整

### 进程开销

每个 WASM 执行在独立进程中：

- **优点**：完全隔离，崩溃不影响其他任务
- **缺点**：进程创建开销，内存占用较高

### 燃料计量

启用燃料计量会增加约 5-10% 的执行开销：

```python
if limits.max_fuel > 0:
    config.consume_fuel = True  # 启用燃料计量
```

## 故障处理

### 任务超时

如果任务执行超时，进程池会强制终止进程：

```python
try:
    result = await asyncio.wait_for(
        loop.run_in_executor(executor, run_wasm),
        timeout=timeout
    )
except asyncio.TimeoutError:
    # 强制终止进程
    future.cancel()
```

### 进程崩溃

如果 WASM 执行导致进程崩溃：

1. 进程池自动重启新进程
2. 任务标记为失败
3. 返回错误信息给主节点

### 连接断开

如果与主节点的连接断开：

1. 停止接收新任务
2. 等待当前任务完成
3. 尝试重新连接
4. 重新注册工作节点

## 下一步

- 了解 [Rust 工作节点](rust-worker.md) 的高性能实现
- 了解 [通信协议](protocol.md) 的详细规范
- 查看 [Python SDK 文档](../sdk/overview.md) 了解客户端 API
