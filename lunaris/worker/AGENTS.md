# 工作节点模块 - Python WASM执行器

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

Python工作节点：多进程WASM执行，WebSocket连接主节点，心跳循环。支持任务重试追踪，进程池隔离，资源限制钳制。

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| 工作节点生命周期 | `main.py:36` | `Worker.run`, `Worker.shutdown` |
| WebSocket连接 | `main.py` | `connect()`, `register()`, 每10秒心跳 |
| 任务执行 | `core.py:107` | `Runner.submit`, `ProcessPoolExecutor` |
| 子进程WASM运行 | `core.py:33` | `_execute_task`（独立函数，pickle要求） |
| 结果报告 | `main.py` | `report_result()`, 回调到主节点 |
| 资源限制钳制 | `core.py:129` | `ExecutionLimits.from_proto().clamp()` |
| 任务尝试追踪 | `main.py` | `attempt` 参数，`(result, task_id, attempt)` 三元组 |

## 开发约定

### 多进程架构
- `ProcessPoolExecutor` 执行WASM（绕过Python GIL）
- `multiprocessing.Queue` 结果传递：子进程 → 主进程
- `_execute_task` 是独立函数（pickle要求）

### 异步 + 进程池混合
- `_listen_results()` asyncio任务轮询 `result_queue`
- `Runner.start()` 创建监听任务
- `Runner.close()` 等待执行器关闭 + 监听器完成

### 资源限制流程
```
proto limits → ExecutionLimits.from_proto() → clamp(defaults, maximums) → WasmSandbox
```

### 心跳模式
- 间隔：10秒
- 状态：`NodeStatus.IDLE` 或 `NodeStatus.BUSY`
- 主节点超时：20秒（见主节点模块）

## 反模式（本模块）

1. **跳过结果监听器**：提交任务前必须调用 `Runner.start()`
2. **直接访问队列**：仅 `_listen_results()` 应读取 `result_queue`
3. **手动修改num_running**：不要修改 - 仅 `Runner.submit()` 更新
4. **关闭前未停止**：WebSocket断开前调用 `runner.close()`
5. **忽略ExecutionLimits钳制**：必须对 `defaults` 和 `maximums` 进行钳制
6. **丢失attempt信息**：结果报告必须包含attempt参数
