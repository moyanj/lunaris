# Lunaris - 分布式 WASM 执行器

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-2021-edition-orange.svg)](https://www.rust-lang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688.svg)](https://fastapi.tiangolo.com/)
[![wasmtime](https://img.shields.io/badge/wasmtime-latest-purple.svg)](https://wasmtime.dev/)

Lunaris 是一个分布式 WASM 执行器，支持 Python 和 Rust 双工作节点架构。通过 WebSocket 通信和 Protobuf 协议，提供高性能、可扩展的 WebAssembly 执行环境。

## 核心特性

- **双工作节点架构**：Python 工作节点（多进程执行）+ Rust 工作节点（高性能，wasmtime + mimalloc）
- **持久化调度**：基于事件溯源的 `StateStore` 抽象层，支持可插拔后端
- **高性能通信**：WebSocket + Protobuf 协议，zstd 压缩
- **灵活的 SDK**：异步 `LunarisClient` + 同步 `SyncLunarisClient`
- **资源隔离**：`ExecutionLimits` 精确控制 WASM 执行资源
- **优雅关闭**：支持 drain 模式和任务取消

## 快速开始

### 安装

```bash
# 使用 uv 安装（推荐）
uv add lunaris

# 或使用 pip
pip install lunaris
```

### 启动主节点

```bash
# 使用 uv
uv run python -m lunaris master --host 127.0.0.1 --port 8000

# 或使用 pip 安装后
lunaris master --host 127.0.0.1 --port 8000
```

### 启动工作节点

```bash
# Rust 工作节点（推荐，生产环境）
cd rust-worker && cargo build --release
./target/release/lunaris-worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN

# Python 工作节点（开发和调试）
uv run python -m lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN
```

### 提交任务

```python
from lunaris.client import LunarisClient

async def main():
    async with LunarisClient("http://127.0.0.1:8000") as client:
        # 提交 WASM 任务
        task = await client.submit_task(
            wasm_bytes=open("test.wasm", "rb").read(),
            params={"key": "value"}
        )
        print(f"任务 ID: {task.id}, 状态: {task.status}")

import asyncio
asyncio.run(main())
```

## 项目结构

```
lunaris/
├── master/     # FastAPI 主节点（任务调度 + WebSocket 端点）
├── worker/     # Python 工作节点（多进程 WASM 执行器）
├── client/     # SDK（LunarisClient 异步，SyncLunarisClient 同步）
├── runtime/    # WASM 沙箱 + ExecutionLimits
├── proto/      # 生成的 protobuf 文件（禁止编辑）
└── cli/        # argparse 入口点
rust-worker/    # Rust 工作节点 ⭐（一等公民，wasmtime + mimalloc）
proto/          # Protobuf 源定义
```

**说明**：`rust-worker/` 是一等公民，与 Python 工作节点同等重要，推荐用于生产环境。

## 适用场景

- **边缘计算**：在分布式节点上执行 WASM 模块
- **微服务**：将业务逻辑编译为 WASM，动态部署
- **插件系统**：安全地执行用户提交的代码
- **高性能计算**：利用 Rust 工作节点处理 CPU 密集型任务

## 环境要求

- Python >= 3.9
- Rust 工具链（如需编译 Rust 工作节点）
- `protoc`（protobuf 编译器）

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `WORKER_TOKEN` | 工作节点认证令牌 |
| `LUNARIS_WORKER_*` | 执行限制覆盖 |

## 许可证

请参阅项目根目录的 LICENSE 文件。

## 相关链接

- [GitHub 仓库](https://github.com/moyanj/Lunaris)
- [问题反馈](https://github.com/moyanj/Lunaris/issues)
