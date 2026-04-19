# CLI 参考

Lunaris 提供了命令行界面（CLI）来启动主节点和工作节点。

## 基本用法

```bash
lunaris [--help] {master,worker} ...
```

## master 命令

启动主节点（任务调度器）。

### 语法

```bash
lunaris master [选项]
```

### 选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | string | `127.0.0.1` | 绑定的主机地址 |
| `--port` | int | `8000` | 绑定的端口号 |
| `--default-max-fuel` | int | `0` | 默认燃料限制（0=无限制） |
| `--default-max-memory-bytes` | int | `0` | 默认内存限制（0=无限制） |
| `--default-max-module-bytes` | int | `0` | 默认模块大小限制（0=无限制） |
| `--max-fuel` | int | `0` | 最大燃料限制（0=无限制） |
| `--max-memory-bytes` | int | `0` | 最大内存限制（0=无限制） |
| `--max-module-bytes` | int | `0` | 最大模块大小限制（0=无限制） |
| `--state-dir` | string | 环境变量 | 状态持久化目录 |

### 示例

#### 基本启动

```bash
# 使用默认配置
lunaris master

# 指定地址和端口
lunaris master --host 0.0.0.0 --port 9000
```

#### 配置执行限制

```bash
# 设置默认限制
lunaris master \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --default-max-module-bytes 1048576

# 设置最大限制（工作节点不能超过此限制）
lunaris master \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912 \
  --max-module-bytes 10485760
```

#### 配置状态持久化

```bash
# 指定状态目录
lunaris master --state-dir /var/lib/lunaris/state

# 使用环境变量
export LUNARIS_STATE_DIR=/var/lib/lunaris/state
lunaris master
```

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `LUNARIS_STATE_DIR` | 状态持久化目录 |

## worker 命令

启动工作节点（WASM 执行器）。

### 语法

```bash
lunaris worker [选项]
```

### 选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--master` | string | **必填** | 主节点 WebSocket 地址 |
| `--token` | string | 环境变量 | 工作节点认证令牌 |
| `--name` | string | 自动生成 | 工作节点名称 |
| `--concurrency` | int | `4` | 最大并发任务数 |
| `--default-max-fuel` | int | `0` | 默认燃料限制（0=无限制） |
| `--default-max-memory-bytes` | int | `0` | 默认内存限制（0=无限制） |
| `--default-max-module-bytes` | int | `0` | 默认模块大小限制（0=无限制） |
| `--max-fuel` | int | `0` | 最大燃料限制（0=无限制） |
| `--max-memory-bytes` | int | `0` | 最大内存限制（0=无限制） |
| `--max-module-bytes` | int | `0` | 最大模块大小限制（0=无限制） |

### 示例

#### 基本启动

```bash
# 设置令牌
export WORKER_TOKEN="your-secret-token"

# 启动工作节点
lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN
```

#### 配置并发数

```bash
# 设置最大并发任务数
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --concurrency 8
```

#### 配置执行限制

```bash
# 设置默认限制
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864

# 设置最大限制
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912
```

#### 命名工作节点

```bash
# 为工作节点指定名称
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --name worker-1
```

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `WORKER_TOKEN` | 工作节点认证令牌 |
| `LUNARIS_WORKER_MAX_FUEL` | 燃料限制覆盖 |
| `LUNARIS_WORKER_MAX_MEMORY_BYTES` | 内存限制覆盖 |
| `LUNARIS_WORKER_MAX_MODULE_BYTES` | 模块大小限制覆盖 |

## 使用 uv 运行

如果您使用 uv 安装，可以使用以下命令：

```bash
# 启动主节点
uv run python -m lunaris master [选项]

# 启动工作节点
uv run python -m lunaris worker [选项]
```

## 使用 Python 模块运行

您也可以直接使用 Python 模块运行：

```bash
# 启动主节点
python -m lunaris master [选项]

# 启动工作节点
python -m lunaris worker [选项]
```

## 常见配置

### 开发环境

```bash
# 主节点 - 本地开发
lunaris master --host 127.0.0.1 --port 8000

# 工作节点 - 本地开发
export WORKER_TOKEN="dev-token"
lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN --concurrency 2
```

### 生产环境

```bash
# 主节点 - 生产环境
lunaris master \
  --host 0.0.0.0 \
  --port 8000 \
  --state-dir /var/lib/lunaris/state \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912

# 工作节点 - 生产环境
export WORKER_TOKEN="production-secret-token"
lunaris worker \
  --master ws://master.example.com:8000 \
  --token $WORKER_TOKEN \
  --name production-worker-1 \
  --concurrency 8 \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864
```

### 高性能工作节点

```bash
# Rust 工作节点 - 高性能
./rust-worker/target/release/lunaris-worker \
  --master ws://master.example.com:8000 \
  --token $WORKER_TOKEN \
  --name rust-worker-1 \
  --concurrency 16
```

## 故障排除

### 问题：端口被占用

**错误**：`Address already in use`

**解决方案**：
```bash
# 查找占用端口的进程
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或使用其他端口
lunaris master --port 8001
```

### 问题：连接被拒绝

**错误**：`Connection refused`

**解决方案**：
1. 检查主节点是否正在运行
2. 检查地址和端口是否正确
3. 检查防火墙设置

### 问题：认证失败

**错误**：`Invalid token`

**解决方案**：
1. 检查令牌是否正确
2. 检查环境变量是否设置
3. 确保主节点和工作节点使用相同的令牌

### 问题：内存不足

**错误**：`Out of memory`

**解决方案**：
```bash
# 减少并发数
lunaris worker --concurrency 2

# 设置内存限制
lunaris worker --default-max-memory-bytes 33554432  # 32 MB
```

## 下一步

- 查看 [部署指南](../deployment/guide.md) 了解生产环境配置
- 查看 [Python SDK 文档](../sdk/overview.md) 了解客户端 API
- 查看 [架构设计](../architecture/overview.md) 了解系统工作原理
