# worker 命令

`worker` 命令用于启动 Lunaris 工作节点（WASM 执行器）。

## 语法

```bash
lunaris worker [选项]
```

## 选项

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

## 示例

### 基本启动

```bash
# 设置令牌
export WORKER_TOKEN="your-secret-token"

# 启动工作节点
lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN
```

### 配置并发数

```bash
# 设置最大并发任务数
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --concurrency 8
```

### 配置执行限制

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

### 命名工作节点

```bash
# 为工作节点指定名称
lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --name worker-1
```

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `WORKER_TOKEN` | 工作节点认证令牌 |
| `LUNARIS_WORKER_MAX_FUEL` | 燃料限制覆盖 |
| `LUNARIS_WORKER_MAX_MEMORY_BYTES` | 内存限制覆盖 |
| `LUNARIS_WORKER_MAX_MODULE_BYTES` | 模块大小限制覆盖 |

## 更多信息

- 查看 [CLI 概述](overview.md) 了解其他命令
- 查看 [部署指南](../deployment/guide.md) 了解生产环境配置
