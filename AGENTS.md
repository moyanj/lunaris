# Lunaris 知识库

**生成时间：** 2026-04-25
**提交版本：** 8c6f84c
**分支：** main

## 概述

分布式WASM执行器，包含Python服务（FastAPI主节点 + Python工作节点 + 异步/同步SDK）、高性能Rust工作节点、ESP32 MCU工作节点，以及多语言Guest SDK。使用WebSocket进行工作节点通信，Protobuf协议，wasmtime执行WASM，支持持久化事件驱动调度和状态管理。

## 项目结构

```
lunaris/
├── master/     # FastAPI任务调度器 + WebSocket端点 + 状态持久化
├── worker/     # Python工作节点（多进程WASM执行器）
├── client/     # SDK（LunarisClient异步，SyncLunarisClient同步）
├── runtime/    # WASM沙箱 + ExecutionLimits
├── proto/      # 生成的protobuf文件（禁止编辑）
├── cli/        # argparse入口点
└── utils.py    # 协议编解码（Envelope+zstd）、Snowflake ID、Rest响应
rust-worker/    # Rust工作节点（wasmtime + mimalloc + tokio）
mcu-worker/     # ESP32 MCU工作节点（wasm3 + nanopb，C实现）
sdk/            # 多语言Guest SDK（Rust/C/C++/Zig/Go/AssemblyScript/Grain）
proto/          # Protobuf源定义（*.proto + build.sh）
testwasm/       # 示例WASM项目（非测试）
tests/          # pytest测试（WASI Preview1、源码编译语言）
deploy/         # Docker Compose部署 + Prometheus配置
docs/           # 项目文档（架构、SDK、部署、CLI）
```
lunaris/
├── master/     # FastAPI任务调度器 + WebSocket端点
├── worker/     # Python工作节点（多进程WASM执行器）
├── client/     # SDK（LunarisClient异步，SyncLunarisClient同步）
├── runtime/    # WASM沙箱 + ExecutionLimits
├── proto/      # 生成的protobuf文件（禁止编辑）
└── cli/        # argparse入口点
rust-worker/    # Rust工作节点（wasmtime + mimalloc）
proto/          # Protobuf源定义
testwasm/       # 示例WASM项目（非测试）
```

## 代码导航

| 任务 | 位置 | 说明 |
|------|------|------|
| 添加REST端点 | `lunaris/master/api.py` | FastAPI路由，需要认证令牌 |
| 修改任务调度 | `lunaris/master/manager.py` | TaskManager, WorkerManager类 |
| WebSocket主循环 | `lunaris/master/web_app.py` | AppState, distribute_tasks, 心跳+租约检测 |
| 工作节点连接逻辑 | `lunaris/worker/main.py` | WebSocket客户端，心跳循环 |
| WASM执行限制 | `lunaris/runtime/limits.py` | ExecutionLimits数据类 |
| WASM沙箱引擎 | `lunaris/runtime/engine.py` | WasmSandbox类，wasmtime封装 |
| 客户端SDK异步 | `lunaris/client/client.py` | LunarisClient, submit_task() |
| 客户端SDK同步 | `lunaris/client/sync.py` | SyncLunarisClient封装 |
| 源码编译助手 | `lunaris/client/utils.py` | compile_source, HAS_* 编译器检测 |
| 数据模型 | `lunaris/master/model.py` | Task, TaskStatus, TaskAttempt, TaskEvent |
| 状态持久化 | `lunaris/master/store_base.py` | StateStore抽象基类 |
| 文件状态后端 | `lunaris/master/file_store.py` | FileStateStore 快照+事件日志 |
| Prometheus指标 | `lunaris/master/metrics.py` | MasterMetrics, Counter/Gauge/Histogram |
| 协议编解码 | `lunaris/utils.py` | proto2bytes, bytes2proto, MESSAGE_TYPE_MAP |
| Rust工作节点核心 | `rust-worker/src/core.rs` | Worker结构体，WebSocket + 任务分发 |
| Rust WASM引擎 | `rust-worker/src/engine.rs` | Runner, run_wasm(), 资源限制 |
| Protobuf协议 | `proto/*.proto` | 编辑源文件，运行build.sh |
| CLI命令 | `lunaris/cli/main.py` | master/worker子命令 |
| MCU工作节点 | `mcu-worker/src/worker.c` | C实现，wasm3运行时，nanopb协议 |
| Guest SDK | `sdk/` | 多语言WASM Guest SDK |

## 代码地图

### Python入口点

| 符号 | 类型 | 位置 | 用途 |
|------|------|------|------|
| `main()` | 函数 | `lunaris/cli/main.py:124` | CLI入口，argparse |
| `Worker` | 类 | `lunaris/worker/main.py:36` | Python工作节点 |
| `Runner` | 类 | `lunaris/worker/core.py:107` | WASM执行器（ProcessPool） |
| `TaskManager` | 类 | `lunaris/master/manager.py:457` | 优先级队列 + 任务跟踪 + 重试 |
| `WorkerManager` | 类 | `lunaris/master/manager.py:165` | 工作节点注册 + 心跳 + drain |
| `AppState` | 类 | `lunaris/master/web_app.py:34` | 主节点共享状态（limits + store） |
| `LunarisClient` | 类 | `lunaris/client/client.py:27` | 异步SDK |
| `SyncLunarisClient` | 类 | `lunaris/client/sync.py:12` | 同步SDK封装 |
| `WasmSandbox` | 类 | `lunaris/runtime/engine.py:74` | WASM执行封装 |
| `ExecutionLimits` | 类 | `lunaris/runtime/limits.py:18` | 资源限制配置 |
| `IDGenerator` | 类 | `lunaris/utils.py:114` | Snowflake ID生成器 |
| `StateStore` | 类 | `lunaris/master/store_base.py:9` | 持久化抽象基类 |
| `MasterMetrics` | 类 | `lunaris/master/metrics.py:6` | Prometheus指标 |

### Rust入口点

| 符号 | 类型 | 位置 | 用途 |
|------|------|------|------|
| `Worker` | 结构体 | `rust-worker/src/core.rs:15` | 工作节点（WebSocket + 心跳） |
| `Runner` | 结构体 | `rust-worker/src/engine.rs:18` | WASM执行器池 |
| `run_wasm()` | 函数 | `rust-worker/src/engine.rs:126` | WASM执行核心 |
| `main()` | 函数 | `rust-worker/src/main.rs:16` | Rust工作节点入口 |

## 开发规范

### Python
- **类型注解**：公共API必须提供，内部可选
- **命名**：snake_case（函数/变量），PascalCase（类）
- **Protobuf**：禁止编辑 `lunaris/proto/*_pb2.py` - 编辑 `proto/*.proto` 后运行 `./proto/build.sh`
- **导入**：优先使用绝对路径（`from lunaris.client import LunarisClient`）

### Rust
- **格式化**：提交前运行 `cargo fmt`
- **版本**：Cargo.toml 中 `edition = "2021"`（已修复）
- **内存**：使用 `mimalloc` 全局分配器
- **异步**：tokio运行时，WASM执行使用 `spawn_blocking`

### 提交
- 风格：简短祈使句 + 可选作用域（`feat(cli):`、`fix(master):`）
- PR：描述行为变更，列出验证命令

## 反模式（本项目禁止）

### 绝对禁止

1. **硬编码令牌**：必须使用环境变量
   ```python
   # 禁止
   token = "my-secret-value"
   # 必须
   token = os.environ.get("WORKER_TOKEN")
   ```

2. **编辑生成的protobuf**：`lunaris/proto/*_pb2.py` 是自动生成的
   - 解决：编辑 `proto/*.proto` → 运行 `./proto/build.sh`

3. **随意修改ExecutionLimits默认值**：影响工作节点隔离和安全
   - `max_fuel`、`max_memory_bytes`、`max_module_bytes` 影响资源保护

4. **无服务运行测试**：集成测试需要活跃服务
   - 当前测试（`test_localhost_*.py`）需要 `ws://localhost:8000`

## 独特设计

### 双工作节点架构（Rust工作节点是一等公民）
- Python工作节点：`lunaris/worker/` - 多进程执行
- **Rust工作节点：`rust-worker/` - 高性能，wasmtime + mimalloc** ⭐ **一等公民**
- Rust工作节点不是实验性功能，而是与Python工作节点同等重要的生产级组件
- 两者通过相同WebSocket协议连接master，可互换使用
- Rust工作节点提供更高性能，适合CPU密集型和高频调用场景

### 持久化事件驱动调度（新功能）
- `StateStore`抽象层支持可插拔后端（文件、数据库等）
- `FileStateStore`实现：快照+事件日志持久化
- 事件溯源架构：`TaskEvent`记录所有状态变更
- 支持幂等性：`idempotency_key`防止重复提交
- 增量同步：基于序列号的事件订阅

### 协议层
- 信封包装 + zstd压缩（`lunaris/utils.py:proto2bytes`）
- 消息类型路由通过 `MESSAGE_TYPE_MAP`

### 客户端SDK设计
- 异步 `LunarisClient` + 同步 `SyncLunarisClient`，API完全一致
- 请求ID匹配机制确保可靠的任务创建跟踪
- 源码编译助手：`submit_c()`、`submit_rust()`、`submit_go()`、`submit_zig()`

## 命令

### 开发
```bash
# Python - 安装依赖
uv sync

# Python - 运行主节点
uv run python -m lunaris master --host 127.0.0.1 --port 8000

# Python - 运行工作节点
uv run python -m lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN

# Rust - 构建工作节点
cd rust-worker && cargo build --release

# Protobuf - 重新生成Python绑定
./proto/build.sh
```

### 环境变量
```bash
WORKER_TOKEN           # 工作节点认证
LUNARIS_WORKER_*       # 执行限制覆盖
```

### 前置条件
- `protoc`（protobuf编译器）- 生成protobuf必需
- Python >=3.9，Rust工具链

## 注意事项

- **无CI配置**：缺少 `.github/workflows/`
- **无测试目录**：测试文件散落在根目录（`test_localhost_*.py`）
- **Rust版本错误**：Cargo.toml 中 `edition = "2024"`（不存在，应为"2021"）
- **testwasm用途**：示例WASM项目，非正式测试套件
- 参见子目录AGENTS.md了解模块特定细节

## 新增模块

### MCU Worker (`mcu-worker/`)
- ESP32固件实现，wasm3运行时，nanopb协议
- 静态内存分配友好，单任务并发模型
- 跨平台抽象层，支持ESP32/STM32

### Guest SDK (`sdk/`)
- 多语言WASM Guest SDK：Rust/C/C++/Zig/Go/AssemblyScript/Grain
- 支持读取运行时上下文和宿主能力

### 状态持久化
- 事件驱动架构支持可插拔后端
- 快照+事件日志模式确保幂等性
