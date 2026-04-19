# 生产环境配置

本指南介绍如何在生产环境中配置和优化 Lunaris。

## 部署架构

Lunaris 采用单主节点架构，通过多个工作节点实现水平扩展：

```
┌─────────────────────────────────────────────────────────┐
│                      主节点 (单实例)                     │
│                   FastAPI + WebSocket                   │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
│ Rust 工作节点 │ │ Rust 工作 │ │ Python 工作   │
│ (推荐)        │ │ 节点      │ │ 节点          │
└───────────────┘ └───────────┘ └───────────────┘
```

**注意**：当前版本仅支持单主节点部署。工作节点自动负载均衡，无需额外配置。

## 性能优化

### 主节点优化

```bash
# 使用 uvloop 提高性能
lunaris master \
  --host 0.0.0.0 \
  --port 8000 \
  --state-dir /var/lib/lunaris/state
```

### 工作节点优化

```bash
# 使用 Rust 工作节点（更高性能）
./lunaris-worker \
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

## 安全配置

### 认证

```bash
# 使用强密码
export WORKER_TOKEN=$(openssl rand -hex 32)

# 定期轮换令牌（建议每月）
```

### 网络安全

```bash
# 防火墙配置
sudo ufw allow 8000/tcp
sudo ufw allow from 10.0.0.0/8 to any port 8000
```

### 资源限制

```bash
# 严格的 WASM 执行限制
lunaris master \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912
```

## 监控告警

### 健康检查

```bash
# 检查系统状态
curl -H "X-Client-Token: $TOKEN" http://localhost:8000/stats

# 检查工作节点
curl -H "X-Client-Token: $TOKEN" http://localhost:8000/worker
```

### Prometheus 集成（未来支持）

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'lunaris'
    static_configs:
      - targets: ['localhost:8000']
```

### 告警规则

```yaml
# alerts.yml
groups:
  - name: lunaris
    rules:
      - alert: HighTaskFailureRate
        expr: rate(lunaris_tasks_failed_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High task failure rate"
          
      - alert: WorkerDown
        expr: lunaris_workers_active < 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "No active workers"
```

## 日志管理

### 日志配置

```bash
# 配置日志级别（未来支持）
lunaris master --log-level info
```

### 日志轮转

```bash
# 使用 logrotate
# /etc/logrotate.d/lunaris
/var/log/lunaris/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 lunaris lunaris
    postrotate
        systemctl reload lunaris-master
    endscript
}
```

## 备份恢复

### 状态备份

```bash
# 定期备份状态目录
0 2 * * * tar -czf /backup/lunaris-state-$(date +\%Y\%m\%d).tar.gz /var/lib/lunaris/state

# 保留最近 30 天的备份
find /backup -name "lunaris-state-*.tar.gz" -mtime +30 -delete
```

### 恢复

```bash
# 恢复状态
tar -xzf /backup/lunaris-state-20260401.tar.gz -C /

# 重启主节点
sudo systemctl restart lunaris-master
```

## 故障排除

### 常见问题

1. **主节点无法启动**
   - 检查端口占用：`lsof -i :8000`
   - 检查权限：`sudo chown -R lunaris:lunaris /var/lib/lunaris`

2. **工作节点无法连接**
   - 检查网络：`ping master.example.com`
   - 检查令牌：`echo $WORKER_TOKEN`

3. **任务执行失败**
   - 检查日志：`sudo journalctl -u lunaris-worker -f`
   - 检查资源：`free -h`, `df -h`

## 更多信息

- 查看 [部署指南](guide.md) 了解基本部署
- 查看 [开发指南](../development/guide.md) 了解开发流程
