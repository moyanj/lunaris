# master 命令

`master` 命令用于启动 Lunaris 主节点（任务调度器）。

## 语法

```bash
lunaris master [选项]
```

## 选项

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

## 示例

### 基本启动

```bash
# 使用默认配置
lunaris master

# 指定地址和端口
lunaris master --host 0.0.0.0 --port 9000
```

### 配置执行限制

```bash
# 设置默认限制
lunaris master \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --default-max-module-bytes 1048576

# 设置最大限制
lunaris master \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912 \
  --max-module-bytes 10485760
```

### 配置状态持久化

```bash
# 指定状态目录
lunaris master --state-dir /var/lib/lunaris/state

# 使用环境变量
export LUNARIS_STATE_DIR=/var/lib/lunaris/state
lunaris master
```

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `LUNARIS_STATE_DIR` | 状态持久化目录 |

## 更多信息

- 查看 [CLI 概述](overview.md) 了解其他命令
- 查看 [部署指南](../deployment/guide.md) 了解生产环境配置
