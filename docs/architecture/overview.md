# 架构概述

Lunaris 是一个分布式 WASM 执行器，采用主从架构设计。系统由三个核心组件组成：主节点（Master）、工作节点（Worker）和客户端 SDK。

## 系统架构

```
┌─────────────────┐    WebSocket    ┌─────────────────┐
│                 │◄───────────────►│                 │
│   客户端 SDK    │                 │    主节点       │
│  (LunarisClient)│                 │   (FastAPI)     │
│                 │                 │                 │
└─────────────────┘                 └────────┬────────┘
                                             │
                                             │ WebSocket
                                             │
                                    ┌────────▼────────┐
                                    │                 │
                                    │   工作节点      │
                                    │  (Python/Rust)  │
                                    │                 │
                                    └─────────────────┘
```

## 核心组件

### 1. 主节点 (Master)

主节点是系统的控制中心，负责：

- **任务调度**：接收客户端提交的任务，分配给可用的工作节点
- **工作节点管理**：管理工作节点的注册、心跳和状态
- **状态持久化**：通过 `StateStore` 抽象层持久化任务状态
- **REST API**：提供任务查询、统计等 REST 接口
- **WebSocket 端点**：处理客户端和工作节点的实时通信

**技术栈**：FastAPI + Uvicorn + WebSocket

**关键模块**：
- `master/api.py` - REST 和 WebSocket 端点
- `master/manager.py` - 任务和工作节点管理器
- `master/model.py` - 数据模型（Task, Worker 等）
- `master/store.py` - 状态持久化

### 2. 工作节点 (Worker)

工作节点负责执行 WASM 模块，支持两种实现：

#### Rust 工作节点（一等公民，推荐）⭐

Rust 工作节点是 Lunaris 的**一等公民**，提供生产级高性能 WASM 执行能力：

- **高性能**：使用 wasmtime 原生库 + mimalloc 内存分配器
- **异步执行**：tokio 运行时 + `spawn_blocking` 执行 WASM
- **并发控制**：信号量限制并行 WASM 执行数量
- **低资源占用**：相比 Python 工作节点，内存占用更低，启动更快
- **生产就绪**：推荐用于生产环境

**关键模块**：
- `rust-worker/src/core.rs` - Worker 结构体，WebSocket 通信
- `rust-worker/src/engine.rs` - Runner，WASM 执行核心

#### Python 工作节点

Python 工作节点适合开发和调试场景：

- **多进程执行**：使用 `ProcessPoolExecutor` 并行执行 WASM
- **wasmtime 引擎**：通过 Python wasmtime 绑定执行 WASM
- **资源限制**：支持燃料、内存、模块大小限制
- **强隔离性**：每个 WASM 在独立进程中执行

**关键模块**：
- `worker/main.py` - WebSocket 客户端和心跳循环
- `worker/core.py` - WASM 执行器（Runner）
- `runtime/engine.py` - WasmSandbox 类

### 3. 客户端 SDK

提供异步和同步两种 API，用于提交和管理任务：

#### 异步客户端 (LunarisClient)

- 基于 WebSocket 的实时通信
- 支持回调机制
- 上下文管理器支持

#### 同步客户端 (SyncLunarisClient)

- 封装异步客户端
- 使用独立线程运行事件循环
- API 与异步客户端完全一致

**关键模块**：
- `client/client.py` - 异步客户端
- `client/sync.py` - 同步客户端封装
- `client/utils.py` - 源代码编译工具

## 通信协议

### WebSocket 协议

客户端与主节点、工作节点与主节点之间使用 WebSocket 进行实时通信：

- **客户端连接**：`/task?token=<token>` - 提交任务和接收结果
- **工作节点连接**：`/worker?token=<token>` - 接收任务和返回结果
- **任务订阅**：`/task/{task_id}/subscribe?token=<token>` - 订阅特定任务结果

### Protobuf 消息

所有 WebSocket 消息使用 Protocol Buffers 序列化：

- `CreateTask` - 客户端提交任务
- `TaskCreated` - 主节点确认任务创建
- `TaskResult` - 工作节点返回执行结果
- `WorkerHeartbeat` - 工作节点心跳
- `ControlCommand` - 主节点控制命令（取消任务等）

### zstd 压缩

所有 Protobuf 消息使用 zstd 箏法压缩，减少网络传输开销。

## 任务生命周期

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ CREATED │────►│ QUEUED  │────►│ LEASED  │────►│ RUNNING │
└─────────┘     └─────────┘     └─────────┘     └────┬────┘
                                                      │
                              ┌───────────────────────┼───────────────────────┐
                              │                       │                       │
                              ▼                       ▼                       ▼
                        ┌──────────┐           ┌──────────┐           ┌──────────┐
                        │SUCCEEDED │           │  FAILED  │           │CANCELLED │
                        └──────────┘           └──────────┘           └──────────┘
```

1. **CREATED** - 任务已创建
2. **QUEUED** - 任务进入调度队列
3. **LEASED** - 任务已分配给工作节点
4. **RUNNING** - 工作节点正在执行
5. **SUCCEEDED** - 执行成功
6. **FAILED** - 执行失败
7. **CANCELLED** - 任务被取消

## 状态持久化

系统采用事件溯源架构持久化状态：

- **StateStore 抽象层**：支持可插拔后端（文件、数据库等）
- **FileStateStore 实现**：快照 + 事件日志持久化
- **TaskEvent 记录**：记录所有状态变更
- **幂等性支持**：`idempotency_key` 防止重复提交
- **增量同步**：基于序列号的事件订阅

## 资源隔离

通过 `ExecutionLimits` 精确控制 WASM 执行资源：

| 限制类型 | 说明 | 默认值 |
|---------|------|--------|
| `max_fuel` | 燃料限制（指令计数） | 0（无限制） |
| `max_memory_bytes` | 内存限制（字节） | 0（无限制） |
| `max_module_bytes` | 模块大小限制（字节） | 0（无限制） |

限制解析逻辑：
- 如果请求值 ≤ 0，使用默认值
- 如果最大值 > 0 且请求值 > 最大值，使用最大值
- 三层解析：`requested → default → maximum`

## 下一步

- 了解 [主节点架构](master.md) 的详细设计
- 了解 [Python 工作节点](python-worker.md) 的实现
- 了解 [Rust 工作节点](rust-worker.md) 的高性能特性
- 了解 [通信协议](protocol.md) 的详细规范
