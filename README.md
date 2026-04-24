# Lunaris

轻量级分布式 WASM 执行平面，支持 Python 与 Rust 双工作节点架构。

Lunaris 把 WebAssembly 任务分发到本地或远端 worker 执行，提供明确的资源限制、任务生命周期跟踪以及多语言 SDK。

## 核心特性

- **双工作节点架构**：Python worker 用于开发调试，Rust worker 面向生产高性能场景
- **多语言 Guest SDK**：支持 Rust、C、C++、Zig、Go、AssemblyScript、Grain
- **源码直传**：可直接提交源码，自动编译为 WASM 再执行
- **资源隔离**：通过 fuel、内存、模块大小三重限制控制执行边界
- **状态持久化**：基于快照 + 事件日志的文件存储，支持幂等性
- **可观测性**：内置健康检查与 Prometheus 指标
- **容器化部署**：提供完整的 Docker Compose 配置

## 架构概览

```text
+------------------+      WebSocket       +------------------+
| Python SDK       | <------------------> | Master           |
| Async / Sync     |                      | FastAPI + Store  |
+------------------+                      +--------+---------+
                                                  |
                                                  | WebSocket
                                                  |
                               +------------------+------------------+
                               |                                     |
                      +--------v---------+                  +--------v---------+
                      | Python Worker    |                  | Rust Worker      |
                      | wasmtime + proc  |                  | wasmtime + tokio |
                      +------------------+                  +------------------+
```

**组件说明**：

| 组件 | 技术栈 | 职责 |
|------|--------|------|
| Master | FastAPI + WebSocket | 任务调度、Worker 管理、状态持久化 |
| Python Worker | wasmtime + ProcessPool | 开发友好，多进程执行 |
| Rust Worker | wasmtime + tokio + mimalloc | 生产级高性能执行 |
| Client SDK | Python async/sync | 任务提交与状态查询 |

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
cp deploy/.env.example .env
mkdir -p deploy/state deploy/prometheus/data
docker compose up -d --build
```

启动后访问：

- Master API：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/readyz`
- Prometheus：`http://127.0.0.1:9090`

### 方式二：本地开发

```bash
# 安装依赖
uv sync

# 启动 Master
export CLIENT_TOKEN=dev-client-token
export WORKER_TOKEN=dev-worker-token

uv run python -m lunaris master \
  --host 127.0.0.1 \
  --port 8000 \
  --state-dir .lunaris-state

# 启动 Python Worker（新终端）
uv run python -m lunaris worker \
  --master ws://127.0.0.1:8000/worker \
  --token $WORKER_TOKEN \
  --concurrency 4

# 或启动 Rust Worker（新终端）
cd rust-worker && cargo build --release && cd ..
./rust-worker/target/release/lunaris-worker \
  --master ws://127.0.0.1:8000/worker \
  --token $WORKER_TOKEN \
  --concurrency 4
```

## 使用示例

### 提交 WASM 模块

```python
import asyncio
from lunaris.client import LunarisClient


async def main():
    async with LunarisClient("ws://127.0.0.1:8000", "dev-client-token") as client:
        wasm_bytes = open("guest.wasm", "rb").read()

        task_id = await client.submit_task(
            wasm_module=wasm_bytes,
            args=[1, 2],
            entry="wmain",
        )

        result = await client.wait_for_task(task_id, timeout=30)
        print("result:", result.result)
        print("stdout:", result.stdout.decode("utf-8", errors="replace"))


asyncio.run(main())
```

### 直接提交源码

```python
import asyncio
from lunaris.client import LunarisClient


async def main():
    source = """
export function wmain(a: i32, b: i32): i32 {
  return a + b;
}
"""

    async with LunarisClient("ws://127.0.0.1:8000", "dev-client-token") as client:
        task_id = await client.submit_assemblyscript(source, args=[3, 4])
        result = await client.wait_for_task(task_id, timeout=30)
        print(result.result)


asyncio.run(main())
```

## API 接口

### WebSocket

| 端点 | 用途 |
|------|------|
| `/task?token=...` | 任务提交与查询 |
| `/worker` | Worker 接入 |

### REST

| 端点 | 用途 |
|------|------|
| `GET /task/{task_id}` | 查询任务详情 |
| `GET /task/{task_id}/status` | 查询任务状态 |
| `GET /tasks` | 列出所有任务 |
| `GET /worker` | 列出所有 Worker |
| `GET /stats` | 统计信息 |
| `GET /livez` | 存活检查 |
| `GET /readyz` | 就绪检查 |
| `GET /metrics` | Prometheus 指标 |

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CLIENT_TOKEN` | 客户端认证令牌 | 必填 |
| `WORKER_TOKEN` | Worker 认证令牌 | 必填 |
| `LUNARIS_STATE_DIR` | 状态存储目录 | `.lunaris-state` |
| `LUNARIS_DEFAULT_MAX_FUEL` | 默认 fuel 限制 | `1000000` |
| `LUNARIS_DEFAULT_MAX_MEMORY_BYTES` | 默认内存限制 | `67108864` (64MB) |
| `LUNARIS_DEFAULT_MAX_MODULE_BYTES` | 默认模块大小限制 | `1048576` (1MB) |
| `LUNARIS_MAX_FUEL` | 最大 fuel 限制 | `10000000` |
| `LUNARIS_MAX_MEMORY_BYTES` | 最大内存限制 | `536870912` (512MB) |
| `LUNARIS_MAX_MODULE_BYTES` | 最大模块大小限制 | `4194304` (4MB) |

## Guest SDK

让 WASM 模块读取 Lunaris 运行时上下文并调用宿主能力。

| 语言 | 路径 |
|------|------|
| Rust | `sdk/rust/lunaris-wasm` |
| C | `sdk/c/lunaris.h` |
| C++ | `sdk/cpp/lunaris.hpp` |
| Zig | `sdk/zig/lunaris.zig` |
| Go | `sdk/go/lunaris.go` |
| AssemblyScript | `sdk/assemblyscript/lunaris.ts` |
| Grain | `sdk/grain/lunaris.gr` |

详见 [WASM Guest SDK 文档](docs/sdk/wasm-guest.md)。

## 依赖要求

### 必需

- Python `>= 3.9`
- Rust toolchain
- `protoc`（protobuf 编译器）
- `uv`（推荐的 Python 包管理器）

### 源码编译助手（可选）

- `wasm32-wasip1-clang` / `wasm32-wasip1-clang++`
- `zig`
- `tinygo`
- `asc`（AssemblyScript）
- `grain`

## 项目结构

```
lunaris/
├── master/        # FastAPI 任务调度器
├── worker/        # Python Worker 实现
├── client/        # Python SDK
├── runtime/       # WASM 沙箱与资源限制
├── cli/           # 命令行入口
└── proto/         # 生成的 protobuf 文件
rust-worker/       # Rust Worker 实现
proto/             # Protobuf 源定义
sdk/               # Guest SDK
docs/              # 文档
```

## 适用场景

**适合**：

- 需要可控执行边界的 WASM 任务执行
- 希望在多种 Worker 实现间复用同一协议
- 资源受限的计算任务
- 从 Python 应用通过 SDK 提交任务

**当前限制**：

- 仅支持单 Master（无高可用）
- 默认持久化后端为本地文件系统
- 多租户隔离尚未完善

## 文档

- [快速开始](docs/getting-started/quickstart.md)
- [架构概览](docs/architecture/overview.md)
- [Python SDK](docs/sdk/overview.md)
- [WASM Guest SDK](docs/sdk/wasm-guest.md)
- [部署指南](docs/deployment/guide.md)
- [贡献指南](docs/development/contributing.md)

## 贡献

欢迎贡献！请先阅读[贡献指南](docs/development/contributing.md)。

提交代码时请注意：

- 保持改动范围清晰
- 提供验证步骤
- 行为变化时同步更新文档
- 不要直接编辑 `lunaris/proto/` 下的生成文件

## 许可证

当前仓库尚未添加 LICENSE 文件。在许可证明确之前，请不要默认该项目可以被自由分发、二次发布或商用。

## 安全

发现安全问题请通过仓库维护者的 GitHub 页面私下联系：<https://github.com/moyanj/lunaris>
