# 安装指南

## 系统要求

- Python >= 3.9
- Rust 工具链（如需编译 Rust 工作节点）
- `protoc`（protobuf 编译器，生成 protobuf 文件需要）

## 安装方式

### 使用 uv（推荐）

uv 是现代 Python 包管理器，推荐用于安装 Lunaris：

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境
uv venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装 lunaris
uv add lunaris
```

### 使用 pip

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装
pip install lunaris
```

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/moyanj/Lunaris.git
cd Lunaris

# 使用 uv 安装
uv sync

# 或使用 pip
pip install -e .
```

## 安装 Rust 工作节点（可选）

Rust 工作节点提供更高的性能，适合 CPU 密集型任务：

```bash
# 安装 Rust 工具链（如未安装）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 编译 Rust 工作节点
cd rust-worker
cargo build --release

# 编译后的可执行文件位于
# ./target/release/lunaris-worker
```

## 安装 protobuf 编译器

如需修改协议定义，需要安装 `protoc`：

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y protobuf-compiler
```

### macOS
```bash
brew install protobuf
```

### Arch Linux
```bash
sudo pacman -S protobuf
```

### Windows
从 [protobuf releases](https://github.com/protocolbuffers/protobuf/releases) 下载预编译版本。

## 验证安装

```bash
# 检查 lunaris 命令
lunaris --help

# 或使用 uv
uv run python -m lunaris --help

# 输出应显示：
# usage: lunaris [-h] {master,worker} ...
```

## 环境变量

安装后，建议设置以下环境变量：

```bash
# 工作节点认证令牌
export WORKER_TOKEN="your-secret-token"

# 可选：覆盖默认执行限制
export LUNARIS_WORKER_MAX_FUEL=1000000
export LUNARIS_WORKER_MAX_MEMORY_BYTES=67108864
```

## 依赖说明

Lunaris 的主要依赖：

| 依赖 | 用途 |
|------|------|
| `fastapi` | 主节点 REST API 框架 |
| `uvicorn` | ASGI 服务器 |
| `websockets` | WebSocket 通信 |
| `wasmtime` | Python WASM 执行引擎 |
| `protobuf` | 协议序列化 |
| `zstandard` | 消息压缩 |
| `loguru` | 日志记录 |

## 故障排除

### 问题：`protoc` 未找到

**解决方案**：安装 protobuf 编译器（见上文）。

### 问题：wasmtime 安装失败

**解决方案**：
```bash
# 确保 pip 是最新版本
pip install --upgrade pip

# 重新安装
pip install wasmtime --no-cache-dir
```

### 问题：Rust 编译失败

**解决方案**：
```bash
# 更新 Rust 工具链
rustup update

# 清理并重新编译
cd rust-worker
cargo clean
cargo build --release
```

## 下一步

安装完成后，请参阅 [快速上手](quickstart.md) 开始使用 Lunaris。
