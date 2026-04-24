# 部署指南

本指南介绍如何将 Lunaris 部署到生产环境。

## 部署架构

Lunaris 采用**单主节点 + 多工作节点**架构。通过增加工作节点实现水平扩展。

### 单主节点部署

```
┌─────────────────────────────────────────────────────────┐
│                      单台服务器                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  主节点     │  │ Rust 工作   │  │ Rust 工作   │     │
│  │  (FastAPI)  │  │ 节点 ⭐     │  │ 节点        │     │
│  │  :8000      │  │             │  │             │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 分布式工作节点部署

```
┌─────────────────────────────────────────────────────────┐
│                      主节点 (单实例)                     │
│                   FastAPI + WebSocket                   │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
│ Rust 工作节点 │ │ Rust 工作 │ │ Rust 工作     │
│ ⭐ (推荐)     │ │ 节点      │ │ 节点          │
└───────────────┘ └───────────┘ └───────────────┘
```

**说明**：
- 当前版本仅支持**单主节点**部署
- 工作节点可以分布在多台服务器上
- Rust 工作节点是一等公民，推荐用于生产环境
- 工作节点自动负载均衡，无需额外配置

## 系统要求

### 主节点

- **CPU**: 2+ 核心
- **内存**: 4+ GB
- **磁盘**: 10+ GB（用于状态持久化）
- **网络**: 稳定的网络连接

### 工作节点

- **CPU**: 4+ 核心（根据并发数调整）
- **内存**: 8+ GB（根据 WASM 内存限制调整）
- **磁盘**: 10+ GB
- **网络**: 与主节点的低延迟连接

## 安装

### 使用 Docker（推荐）

仓库根目录已提供可重复部署所需文件：

- `Dockerfile.master`
- `Dockerfile.worker`
- `Dockerfile.rust-worker`
- `docker-compose.yml`
- `deploy/.env.example`
- `deploy/prometheus/prometheus.yml`

最小启动流程：

```bash
cp deploy/.env.example .env
mkdir -p deploy/state deploy/prometheus/data
docker compose up -d --build
```

启动后可验证：

```bash
curl http://localhost:8000/livez
curl http://localhost:8000/readyz
curl http://localhost:8000/metrics
curl http://localhost:9090/-/ready
```

#### 主节点 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
RUN pip install lunaris

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["lunaris", "master", "--host", "0.0.0.0", "--port", "8000"]
```

#### 工作节点 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
RUN pip install lunaris

# 启动命令
CMD ["lunaris", "worker", "--master", "${MASTER_URI}", "--token", "${WORKER_TOKEN}"]
```

#### Rust 工作节点 Dockerfile

```dockerfile
FROM rust:1.75 AS builder

WORKDIR /app
COPY rust-worker/ .
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/lunaris-worker .

CMD ["./lunaris-worker", "--master", "${MASTER_URI}", "--token", "${WORKER_TOKEN}"]
```

### 使用 systemd

#### 主节点服务

创建 `/etc/systemd/system/lunaris-master.service`：

```ini
[Unit]
Description=Lunaris Master Node
After=network.target

[Service]
Type=simple
User=lunaris
Group=lunaris
WorkingDirectory=/opt/lunaris
Environment=WORKER_TOKEN=your-secret-token
ExecStart=/opt/lunaris/venv/bin/lunaris master --host 0.0.0.0 --port 8000 --state-dir /var/lib/lunaris/state
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 工作节点服务

创建 `/etc/systemd/system/lunaris-worker.service`：

```ini
[Unit]
Description=Lunaris Worker Node
After=network.target lunaris-master.service

[Service]
Type=simple
User=lunaris
Group=lunaris
WorkingDirectory=/opt/lunaris
Environment=WORKER_TOKEN=your-secret-token
ExecStart=/opt/lunaris/venv/bin/lunaris worker --master ws://master.example.com:8000 --token ${WORKER_TOKEN} --concurrency 8
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 启用服务

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start lunaris-master
sudo systemctl start lunaris-worker

# 设置开机自启
sudo systemctl enable lunaris-master
sudo systemctl enable lunaris-worker

# 查看状态
sudo systemctl status lunaris-master
sudo systemctl status lunaris-worker
```

## 配置

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `WORKER_TOKEN` | 工作节点认证令牌 | `your-secret-token` |
| `LUNARIS_STATE_DIR` | 状态持久化目录 | `/var/lib/lunaris/state` |
| `LUNARIS_WORKER_MAX_FUEL` | 燃料限制覆盖 | `1000000` |
| `LUNARIS_WORKER_MAX_MEMORY_BYTES` | 内存限制覆盖 | `67108864` |

### 配置文件

创建 `/etc/lunaris/config.env`：

```bash
# 认证令牌
WORKER_TOKEN=your-secret-token

# 状态持久化
LUNARIS_STATE_DIR=/var/lib/lunaris/state

# 执行限制
LUNARIS_WORKER_MAX_FUEL=1000000
LUNARIS_WORKER_MAX_MEMORY_BYTES=67108864
LUNARIS_WORKER_MAX_MODULE_BYTES=1048576
```

在 systemd 服务中加载：

```ini
[Service]
EnvironmentFile=/etc/lunaris/config.env
```

## 状态持久化

### 文件系统持久化

```bash
# 创建状态目录
sudo mkdir -p /var/lib/lunaris/state
sudo chown lunaris:lunaris /var/lib/lunaris/state

# 启动主节点时指定状态目录
lunaris master --state-dir /var/lib/lunaris/state
```

### 备份策略

```bash
# 定期备份状态目录
0 2 * * * tar -czf /backup/lunaris-state-$(date +\%Y\%m\%d).tar.gz /var/lib/lunaris/state

# 保留最近 7 天的备份
find /backup -name "lunaris-state-*.tar.gz" -mtime +7 -delete
```

## 监控

### 健康检查

主节点提供 REST API 用于健康检查：

```bash
# 存活检查
curl http://localhost:8000/livez

# 就绪检查
curl http://localhost:8000/readyz

# 检查系统统计
curl -H "X-Client-Token: your-token" http://localhost:8000/stats

# 检查工作节点
curl -H "X-Client-Token: your-token" http://localhost:8000/worker

# 检查任务状态
curl -H "X-Client-Token: your-token" http://localhost:8000/tasks

# Prometheus 指标
curl http://localhost:8000/metrics
```

### Compose 默认组件

- `master`: 暴露 `8000`，挂载 `deploy/state`
- `rust-worker`: 默认连接 `ws://master:8000/worker`
- `prometheus`: 暴露 `9090`，抓取 `master:8000/metrics`

### Prometheus 指标

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'lunaris'
    static_configs:
      - targets: ['localhost:8000']
```

### 日志

```bash
# 查看主节点日志
sudo journalctl -u lunaris-master -f

# 查看工作节点日志
sudo journalctl -u lunaris-worker -f

# 日志级别配置（未来支持）
lunaris master --log-level info
```

## 安全

### 认证

- 使用强密码作为 `WORKER_TOKEN`
- 定期轮换令牌
- 使用 HTTPS/WSS 加密通信

### 网络安全

```bash
# 防火墙配置
sudo ufw allow 8000/tcp  # 主节点端口
sudo ufw allow from 10.0.0.0/8 to any port 8000  # 仅允许内部网络
```

### 资源限制

```bash
# 设置 WASM 执行限制
lunaris master \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912
```

## 性能优化

### 主节点优化

```bash
# 使用 uvloop 提高性能
pip install uvloop

# 启动主节点（自动使用 uvloop）
lunaris master --host 0.0.0.0 --port 8000
```

### 工作节点优化

```bash
# 使用 Rust 工作节点（更高性能）
cd rust-worker && cargo build --release

# 启动 Rust 工作节点
./target/release/lunaris-worker \
  --master ws://master.example.com:8000 \
  --token $WORKER_TOKEN \
  --concurrency 16
```

### 并发调优

根据服务器配置调整并发数：

```bash
# CPU 密集型任务
lunaris worker --concurrency $(nproc)

# I/O 密集型任务
lunaris worker --concurrency $(($(nproc) * 2))
```

## 扩展

### 水平扩展

```bash
# 启动多个工作节点
for i in {1..4}; do
  lunaris worker \
    --master ws://master.example.com:8000 \
    --token $WORKER_TOKEN \
    --name worker-$i \
    --concurrency 4 &
done
```

## 故障排除

### 主节点无法启动

**检查端口占用**：
```bash
lsof -i :8000
```

**检查权限**：
```bash
sudo chown -R lunaris:lunaris /var/lib/lunaris
```

### 工作节点无法连接

**检查网络**：
```bash
ping master.example.com
telnet master.example.com 8000
```

**检查令牌**：
```bash
# 确保主节点和工作节点使用相同的令牌
echo $WORKER_TOKEN
```

### 任务执行失败

**检查工作节点日志**：
```bash
sudo journalctl -u lunaris-worker -f
```

**检查资源限制**：
```bash
# 查看系统资源
free -h
df -h
```

## 下一步

- 查看 [生产环境配置](production.md) 了解高级配置
- 查看 [开发指南](../development/guide.md) 了解如何贡献代码
