# 客户端模块 - WASM任务提交SDK

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

用户SDK：异步 `LunarisClient` + 同步 `SyncLunarisClient`，WebSocket任务提交，多语言源码编译助手。新增请求ID匹配和幂等性支持。

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| 异步客户端 | `client.py:27` | `LunarisClient.connect`, `submit_task` |
| 同步封装 | `sync.py:12` | `SyncLunarisClient`（线程 + asyncio循环） |
| 回调提交 | `client.py:53` | `submit_task(callback=...)` |
| 等待结果 | `client.py:421` | `wait_for_task(task_id, timeout)` |
| 源码编译 | `utils.py` | `compile_source`, `compile_c/rust/go/zig` |
| 编译器检测 | `utils.py` | `check_wasi_sdk`, `check_rustc`, `HAS_*` 全局变量 |
| REST回退 | `client.py:333` | `_get_rest_data` 状态查询 |
| **请求ID匹配** | `client.py` | `request_id`, `_create_futures` 字典 |
| **幂等性** | `client.py` | `idempotency_key` 参数 |

## 开发约定

### 双客户端模式
- `LunarisClient`：异步WebSocket客户端，基于回调的结果处理
- `SyncLunarisClient`：使用 `asyncio.run_coroutine_threadsafe` 封装异步客户端
- API完全一致：`submit_task`, `wait_for_task`, `get_task_result`

### 回调机制
- 回调可以是同步或异步函数
- 在 `_receive_messages()` 收到 `TaskResult` 时调用
- 调用后自动移除（一次性）

### 请求ID匹配（新功能）
- 每次 `submit_task()` 通过 `secrets.token_hex(16)` 生成唯一 `request_id`
- `_create_futures` 字典映射 `request_id` → `Future[TaskCreateResponse]`
- 主节点响应包含匹配的 `request_id`，确保可靠的任务创建跟踪
- 替代旧的队列方式，支持更好的并发请求处理

### 幂等性支持（新功能）
- 可选的 `idempotency_key` 参数防止重复提交
- 主节点基于幂等键在时间窗口内去重
- 适用于重试场景，避免创建重复任务

### 源码编译
- `submit_c/cxx/zig/rust/go`：`submit_source(language, code)` 的简写
- 本地编译，WASM字节码发送到主节点
- 全局 `HAS_*` 标志缓存编译器可用性

### 上下文管理器
- `async with LunarisClient(...)` - 自动连接/关闭
- `with SyncLunarisClient(...)` - 自动连接/关闭（同步版本）

## 反模式（本模块）

1. **提交前连接**：必须先调用 `connect()` 或使用上下文管理器
2. **超时无清理**：使用 `wait_for_task(timeout)` + 处理 `TimeoutError`
3. **硬编码编译器路径**：使用 `check_*` 函数验证工具链
4. **跳过回调注册**：异步结果需要注册回调或使用 `wait_for_task`
5. **REST用于任务提交**：WebSocket是主要通道，REST仅用于状态查询
6. **忽略request_id**：必须处理 `TaskCreateResponse.request_id` 确保并发安全
