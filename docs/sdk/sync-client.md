# 同步客户端 API

`SyncLunarisClient` 是 Lunaris 的同步客户端，封装了异步客户端 `LunarisClient`。

## 类定义

```python
class SyncLunarisClient:
    def __init__(self, master_uri: str, token: str): ...
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `master_uri` | `str` | 主节点地址，如 `ws://localhost:8000` |
| `token` | `str` | 客户端认证令牌 |

## 连接管理

### connect()

连接到主节点。

```python
def connect(self) -> None: ...
```

### close()

关闭连接。

```python
def close(self) -> None: ...
```

### 上下文管理器

```python
with SyncLunarisClient("ws://localhost:8000", "token") as client:
    # 自动连接和关闭
    ...
```

## 任务提交

### submit_task()

提交 WASM 任务。

```python
def submit_task(
    self,
    wasm_module: bytes,
    args: Optional[List[Any]] = None,
    entry: str = "main",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wasm_module` | `bytes` | - | WASM 模块字节码 |
| `args` | `List[Any]` | `None` | 任务参数列表 |
| `entry` | `str` | `"main"` | 入口函数名 |
| `priority` | `int` | `0` | 任务优先级 |
| `wasi_env` | `WasiEnv` | `None` | WASI 环境配置 |
| `execution_limits` | `ExecutionLimits` | `None` | 执行资源限制 |
| `idempotency_key` | `str` | `None` | 幂等键 |

**返回值**：任务 ID

**示例**：

```python
with SyncLunarisClient("ws://localhost:8000", "token") as client:
    task_id = client.submit_task(
        wasm_module=wasm_bytes,
        args=["arg1", "arg2"]
    )
```

### submit_source()

提交源代码。

```python
def submit_source(
    self,
    language: SourceLanguage,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_c()

提交 C 源代码。

```python
def submit_c(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_cxx()

提交 C++ 源代码。

```python
def submit_cxx(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_rust()

提交 Rust 源代码。

```python
def submit_rust(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_go()

提交 Go 源代码。

```python
def submit_go(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_assemblyscript()

提交 AssemblyScript 源代码。

```python
def submit_assemblyscript(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_grain()

提交 Grain 源代码。

```python
def submit_grain(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

### submit_zig()

提交 Zig 源代码。

```python
def submit_zig(
    self,
    source_code: str,
    args: Optional[List[Any]] = None,
    entry: str = "wmain",
    priority: int = 0,
    wasi_env: Optional[WasiEnv] = None,
    execution_limits: Optional[ExecutionLimits] = None,
    compile_options: Optional[CompileOptions] = None,
    idempotency_key: Optional[str] = None,
) -> str: ...
```

## 任务查询

### wait_for_task()

等待任务完成。

```python
def wait_for_task(
    self,
    task_id: str,
    timeout: Optional[float] = None
) -> TaskResult: ...
```

**参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | `str` | 任务 ID |
| `timeout` | `float` | 超时时间（秒） |

**返回值**：`TaskResult` 对象

**示例**：

```python
result = client.wait_for_task(task_id, timeout=30)
print(f"结果: {result.result}")
print(f"标准输出: {result.stdout.decode('utf-8')}")
```

### get_task_result()

获取任务结果。

```python
def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]: ...
```

### get_task_status()

获取任务状态。

```python
def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]: ...
```

### get_tasks()

获取所有任务。

```python
def get_tasks(self) -> Dict[str, Any]: ...
```

### get_tasks_by_status()

按状态筛选任务。

```python
def get_tasks_by_status(self, status: str) -> Dict[str, Any]: ...
```

### get_tasks_by_worker()

获取工作节点的任务。

```python
def get_tasks_by_worker(self, worker_id: str) -> Dict[str, Any]: ...
```

## 系统查询

### get_workers()

获取所有工作节点。

```python
def get_workers(self) -> Dict[str, Any]: ...
```

### get_stats()

获取系统统计信息。

```python
def get_stats(self) -> Dict[str, Any]: ...
```

## 任务订阅

### unsubscribe_tasks()

取消订阅任务结果。

```python
def unsubscribe_tasks(self, task_ids: List[str]) -> None: ...
```

## 更多信息

- 查看 [概述](overview.md) 了解基本概念
- 查看 [异步客户端](async-client.md) 了解异步 API
- 查看 [示例](examples.md) 了解实际应用
