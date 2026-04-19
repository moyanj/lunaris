# 通信协议

Lunaris 使用 WebSocket + Protobuf 进行实时通信，使用 zstd 压算法减少网络开销。

## 协议栈

```
┌─────────────────────────────────────────────────────────┐
│                    应用层                                │
│  - 任务提交                                             │
│  - 结果返回                                             │
│  - 心跳                                                 │
│  - 控制命令                                             │
├─────────────────────────────────────────────────────────┤
│                    序列化层                              │
│  - Protocol Buffers (protobuf)                          │
│  - zstd 压缩                                            │
├─────────────────────────────────────────────────────────┤
│                    传输层                                │
│  - WebSocket                                            │
│  - HTTP/HTTPS                                           │
└─────────────────────────────────────────────────────────┘
```

## WebSocket 端点

### 客户端端点

| 端点 | 用途 | 认证 |
|------|------|------|
| `/task?token=<token>` | 提交任务、接收结果 | 查询参数 |
| `/task/{task_id}/subscribe?token=<token>` | 订阅特定任务 | 查询参数 |

### 工作节点端点

| 端点 | 用途 | 认证 |
|------|------|------|
| `/worker?token=<token>` | 注册、接收任务、返回结果 | 查询参数 |

## 消息类型

### 客户端 → 主节点

#### CreateTask

提交新任务：

```protobuf
message CreateTask {
    bytes wasm_module = 1;           // WASM 模块字节码
    string args = 2;                 // JSON 序列化的参数
    string entry = 3;                // 入口函数名
    int32 priority = 4;              // 任务优先级
    WasiEnv wasi_env = 5;            // WASI 环境变量
    ExecutionLimits execution_limits = 6;  // 执行限制
    string request_id = 7;           // 请求 ID（用于匹配响应）
    string idempotency_key = 8;      // 幂等键（防止重复提交）
}

message WasiEnv {
    map<string, string> env = 1;     // 环境变量
    repeated string args = 2;        // 命令行参数
}

message ExecutionLimits {
    uint64 max_fuel = 1;             // 燃料限制
    uint64 max_memory_bytes = 2;     // 内存限制
    uint64 max_module_bytes = 3;     // 模块大小限制
}
```

#### UnsubscribeTask

取消订阅任务结果：

```protobuf
message UnsubscribeTask {
    repeated string task_id = 1;     // 任务 ID 列表
}
```

### 主节点 → 客户端

#### TaskCreated

任务创建成功响应：

```protobuf
message TaskCreated {
    string task_id = 1;              // 任务 ID
    string request_id = 2;           // 匹配的请求 ID
}
```

#### TaskCreateFailed

任务创建失败响应：

```protobuf
message TaskCreateFailed {
    string error = 1;                // 错误信息
    string request_id = 2;           // 匹配的请求 ID
}
```

#### TaskResult

任务执行结果：

```protobuf
message TaskResult {
    string task_id = 1;              // 任务 ID
    string result = 2;               // 执行结果（JSON）
    bytes stdout = 3;                // 标准输出
    bytes stderr = 4;                // 标准错误
    uint64 time = 5;                 // 执行时间（毫秒）
    bool succeeded = 6;              // 是否成功
    uint32 attempt = 7;              // 执行尝试次数
}
```

### 工作节点 → 主节点

#### WorkerRegister

工作节点注册：

```protobuf
message WorkerRegister {
    string worker_id = 1;            // 工作节点 ID
    string name = 2;                 // 工作节点名称
    uint32 max_concurrency = 3;      // 最大并发数
    map<string, string> capabilities = 4;  // 能力描述
}
```

#### WorkerHeartbeat

工作节点心跳：

```protobuf
message WorkerHeartbeat {
    string worker_id = 1;            // 工作节点 ID
    NodeState state = 2;             // 节点状态
    uint32 current_tasks = 3;        // 当前任务数
    uint32 max_concurrency = 4;      // 最大并发数
}

enum NodeState {
    IDLE = 0;                        // 空闲
    BUSY = 1;                        // 忙碌
}
```

#### TaskResult

任务执行结果（与客户端相同）：

```protobuf
message TaskResult {
    string task_id = 1;
    string result = 2;
    bytes stdout = 3;
    bytes stderr = 4;
    uint64 time = 5;
    bool succeeded = 6;
    uint32 attempt = 7;
}
```

#### TaskAccepted

任务接受确认：

```protobuf
message TaskAccepted {
    string task_id = 1;              // 任务 ID
}
```

### 主节点 → 工作节点

#### TaskAssign

分配任务给工作节点：

```protobuf
message TaskAssign {
    string task_id = 1;              // 任务 ID
    bytes wasm_module = 2;           // WASM 模块
    string args = 3;                 // 参数（JSON）
    string entry = 4;                // 入口函数
    WasiEnv wasi_env = 5;            // WASI 环境
    ExecutionLimits execution_limits = 6;  // 执行限制
}
```

#### ControlCommand

控制命令：

```protobuf
message ControlCommand {
    CommandType command = 1;         // 命令类型
    map<string, string> params = 2;  // 命令参数
}

enum CommandType {
    CANCEL_TASK = 0;                 // 取消任务
    DRAIN = 1;                       // 进入排空模式
    SHUTDOWN = 2;                    // 关闭
}
```

## 消息序列化

### Protobuf 序列化

所有消息使用 Protocol Buffers 序列化：

```python
# Python 序列化
from lunaris.utils import proto2bytes, bytes2proto

# 序列化
data = proto2bytes(create_task_message)

# 反序列化
message = bytes2proto(data)
```

```rust
// Rust 序列化
use prost::Message;

// 序列化
let data = create_task.encode_to_vec();

// 反序列化
let message = CreateTask::decode(&data[..])?;
```

### zstd 压缩

所有 Protobuf 消息使用 zstd 箏法压缩：

```python
# Python 压缩/解压
import zstandard as zstd

# 压缩
compressed = zstd.compress(data, level=3)

# 解压
decompressed = zstd.decompress(compressed)
```

```rust
// Rust 压缩/解压
use zstd::stream::{encode_all, decode_all};

// 压缩
let compressed = encode_all(&data[..], 3)?;

// 解压
let decompressed = decode_all(&compressed[..])?;
```

## 消息流程

### 任务提交流程

```
客户端                           主节点                           工作节点
   │                               │                               │
   │──── CreateTask ──────────────►│                               │
   │                               │                               │
   │◄─── TaskCreated ──────────────│                               │
   │     (request_id)              │                               │
   │                               │                               │
   │                               │──── TaskAssign ──────────────►│
   │                               │                               │
   │                               │◄─── TaskAccepted ─────────────│
   │                               │                               │
   │                               │                               │ (执行 WASM)
   │                               │                               │
   │                               │◄─── TaskResult ───────────────│
   │                               │                               │
   │◄─── TaskResult ───────────────│                               │
   │                               │                               │
```

### 心跳流程

```
工作节点                         主节点
   │                               │
   │──── WorkerHeartbeat ─────────►│
   │     (state, current_tasks)    │
   │                               │
   │◄─── (无响应，成功) ──────────│
   │                               │
   │──── WorkerHeartbeat ─────────►│
   │     (state, current_tasks)    │
   │                               │
   │◄─── (无响应，成功) ──────────│
   │                               │
```

### 任务取消流程

```
客户端                           主节点                           工作节点
   │                               │                               │
   │──── POST /task/{id}/cancel ──►│                               │
   │                               │                               │
   │                               │──── ControlCommand ──────────►│
   │                               │     (CANCEL_TASK)             │
   │                               │                               │
   │                               │◄─── TaskResult ───────────────│
   │                               │     (cancelled)               │
   │                               │                               │
   │◄─── 响应 ────────────────────│                               │
```

## 错误处理

### 连接错误

- **WebSocket 断开**：尝试重新连接
- **认证失败**：返回 403 错误
- **超时**：返回超时错误

### 任务错误

- **WASM 执行失败**：返回 `TaskResult`，`succeeded = false`
- **燃料耗尽**：返回 `TaskResult`，包含错误信息
- **内存超限**：返回 `TaskResult`，包含错误信息

### 协议错误

- **无效消息**：忽略或关闭连接
- **版本不匹配**：返回错误信息

## 安全考虑

### 认证

- 使用 `secrets.compare_digest()` 进行令牌比较
- 防止时序攻击

### 压缩

- zstd 压减少网络带宽
- 压缩级别 3（平衡压缩率和速度）

### 隔离

- WASM 沙箱隔离
- 资源限制（燃料、内存）
- 进程隔离（Python 工作节点）

## 性能优化

### 消息大小

- Protobuf 二进制序列化
- zstd 压缩（约 50-70% 压缩率）
- 批量消息（未来支持）

### 连接复用

- 单个 WebSocket 连接处理多个任务
- 长连接减少握手开销

### 异步处理

- 非阻塞消息处理
- 并发任务执行

## 下一步

- 查看 [主节点架构](master.md) 了解端点实现
- 查看 [Python 工作节点](python-worker.md) 了解消息处理
- 查看 [Rust 工作节点](rust-worker.md) 了解高性能实现
