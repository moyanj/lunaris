# 主节点模块 - FastAPI任务调度器

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

FastAPI主节点：任务调度、工作节点管理、客户端/工作节点通信的WebSocket端点。包含持久化事件驱动调度、租约管理、重试队列与状态机。

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| 添加REST端点 | `api.py` | `@app.get/@app.websocket`, `require_client_token` |
| 修改任务队列 | `manager.py:457` | `TaskManager.add_task`, `PriorityQueue` |
| 工作节点负载均衡 | `manager.py:165` | `WorkerManager.get_available_worker_nowait`, `available_slots` |
| 任务重试逻辑 | `manager.py:826` | `TaskManager.put_result`, `failed_count`, `max_retries` |
| WebSocket主循环 | `web_app.py:122` | `websocket_endpoint`, 注册+心跳+结果 |
| 任务分发循环 | `web_app.py:263` | `distribute_tasks`, `scheduler_events` 队列驱动 |
| 心跳监控 | `web_app.py:227` | `check_heartbeat`, 20秒超时 |
| 租约检测 | `web_app.py:241` | `check_task_leases`, 5秒轮询 |
| 重试调度 | `web_app.py:253` | `check_retry_queue`, 1秒轮询 |
| 令牌认证 | `api.py:46` | `require_client_token`, `secrets.compare_digest` |
| 数据模型 | `model.py` | `Task`, `TaskStatus`, `TaskAttempt`, `TaskEvent`, `WorkerRecord` |
| 状态持久化 | `store_base.py` | `StateStore` 抽象基类 |
| 文件后端 | `file_store.py` | `FileStateStore` 快照 + 事件日志 |
| 持久化入口 | `store.py` | `PersistentStateStore = FileStateStore` |
| Prometheus指标 | `metrics.py` | `MasterMetrics`, Counter/Gauge/Histogram |
| 应用状态 | `web_app.py:34` | `AppState`, 令牌/limits/store共享 |

## 开发约定

### FastAPI模式
- **依赖注入**：`AppState = Depends(get_app_state)` 共享状态
- **令牌认证**：所有端点通过 `Depends` 使用 `require_client_token`
- **响应封装**：`Rest(msg, code, data)` 统一JSON响应格式

### 事件驱动调度
- `scheduler_events: asyncio.Queue` 队列触发分发循环
- `notify_scheduler(reason)` 投递唤醒事件（任务状态变更/工作节点变化）
- `distribute_tasks()` 消费队列，循环分配直到无可用任务或工作节点

### 异步后台任务（lifespan启动）
- `check_heartbeat()` - 20秒轮询，移除无响应工作节点
- `check_task_leases()` - 5秒轮询，回收过期租约
- `check_retry_queue()` - 1秒轮询，处理重试等待中的任务

### 状态管理
- `StateStore` 抽象基类在 `store_base.py` - 支持后端替换
- `FileStateStore` 在 `file_store.py` - 快照 + 事件日志持久化
- `TaskEvent` 记录状态转换，支持增量订阅（`after_seq`）
- 幂等性支持：`idempotency_index` 防止重复提交

### 状态机
- `TaskStatus`：CREATED → QUEUED → LEASED → RUNNING → SUCCEEDED/FAILED
- `TaskStatus` 特殊：RETRY_WAIT、CANCEL_REQUESTED、CANCELLED
- `AttemptStatus`：DISPATCHED → ACCEPTED → RUNNING → FINISHED/LOST/CANCELLED
- `WorkerStatus`：ACTIVE → DRAINING → OFFLINE → LOST

## 反模式（本模块）

1. **直接操作Task字段**：使用 `assign_to_worker()` / `mark_queued()` 等方法
2. **跳过工作节点负载检查**：分配前必须检查 `worker.available_slots`
3. **硬编码令牌**：使用 `state.client_token` / `state.worker_token`
4. **手动更新心跳**：仅 `WorkerManager.handle_heartbeat()` 应更新
5. **绕过StateStore**：持久化操作必须使用 `state.store`
6. **忽略事件顺序**：事件有序列号，增量更新需尊重 `after_seq`
7. **直接修改Task.status**：必须通过 `mark_succeeded/mark_failed/schedule_retry` 等方法
