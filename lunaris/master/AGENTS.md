# 主节点模块 - FastAPI任务调度器

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

FastAPI主节点：任务调度、工作节点管理、客户端/工作节点通信的WebSocket端点。现包含持久化事件驱动调度与状态机。

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| 添加REST端点 | `api.py` | `@app.get/@app.websocket`, `require_client_token` |
| 修改任务队列 | `manager.py:154` | `TaskManager.add_task`, `PriorityQueue` |
| 工作节点负载均衡 | `manager.py:97` | `WorkerManager.get_available_worker`, `available_slots` |
| 任务重试逻辑 | `manager.py:200` | `TaskManager.put_result`, `failed_count` |
| WebSocket任务分发 | `web_app.py` | `distribute_tasks`, `worker websocket` |
| 心跳监控 | `web_app.py` | `check_heartbeat`, 20秒超时 |
| 令牌认证 | `api.py:17` | `require_client_token`, `secrets.compare_digest` |
| 数据模型 | `model.py` | `Task`, `TaskStatus`, `TaskAttempt`, `TaskEvent`, `WorkerRecord` |
| **状态持久化** | `store_base.py` | `StateStore` 抽象基类 |
| **文件后端** | `file_store.py` | `FileStateStore` 快照 + 事件日志 |

## 开发约定

### FastAPI模式
- **依赖注入**：`AppState = Depends(get_app_state)` 共享状态
- **令牌认证**：所有端点通过 `Depends` 使用 `require_client_token`
- **响应封装**：`Rest(msg, code, data)` 统一JSON响应格式

### 异步后台任务
- `check_heartbeat()` - 20秒无响应移除工作节点
- `distribute_tasks()` - 通过 `asyncio.Condition` 分配任务给可用工作节点

### 状态管理（新功能）
- `StateStore` 抽象基类在 `store_base.py` - 支持后端替换
- `FileStateStore` 在 `file_store.py` - 基于文件的快照 + 事件日志持久化
- 事件驱动架构：`TaskEvent` 记录状态转换
- 幂等性支持：`idempotency_index`

### 状态机
- `TaskStatus` 枚举：CREATED → QUEUED → LEASED → RUNNING → SUCCEEDED/FAILED
- `AttemptStatus` 枚举：DISPATCHED → ACCEPTED → RUNNING → FINISHED/LOST/CANCELLED
- `WorkerStatus` 枚举：ACTIVE → DRAINING → OFFLINE → LOST

## 反模式（本模块）

1. **直接操作Task**：不要修改 `Task` 字段 - 使用 `assign_to_worker()` 等方法
2. **跳过工作节点负载检查**：分配前必须检查 `worker.available_slots`
3. **硬编码令牌**：使用 `state.client_token` / `state.worker_token` 来自AppState
4. **手动更新心跳**：仅 `WorkerManager.handle_heartbeat()` 应更新 `last_heartbeat`
5. **绕过StateStore**：持久化操作必须使用 `state.store`
6. **忽略事件顺序**：事件有序列号，增量更新需尊重 `after_seq`
