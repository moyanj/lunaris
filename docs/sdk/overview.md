# Python SDK 概述

Lunaris 提供了两种 Python SDK：异步客户端 `LunarisClient` 和同步客户端 `SyncLunarisClient`。两者 API 完全一致，您可以根据应用需求选择。

## 安装

```bash
# 使用 uv
uv add lunaris

# 或使用 pip
pip install lunaris
```

## 快速示例

### 异步客户端

```python
import asyncio
from lunaris.client import LunarisClient

async def main():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 提交 WASM 任务
        with open("test.wasm", "rb") as f:
            task_id = await client.submit_task(
                wasm_module=f.read(),
                args=["arg1", "arg2"]
            )
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        print(f"结果: {result.result}")

asyncio.run(main())
```

### 同步客户端

```python
from lunaris.client import SyncLunarisClient

def main():
    with SyncLunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 提交 WASM 任务
        with open("test.wasm", "rb") as f:
            task_id = client.submit_task(
                wasm_module=f.read(),
                args=["arg1", "arg2"]
            )
        
        # 等待结果
        result = client.wait_for_task(task_id, timeout=30)
        print(f"结果: {result.result}")

if __name__ == "__main__":
    main()
```

## 核心概念

### 任务（Task）

任务是 Lunaris 的基本执行单元：

- **WASM 模块**：要执行的 WebAssembly 代码
- **参数**：传递给 WASM 函数的参数
- **入口函数**：要调用的函数名（默认 `wmain`）
- **优先级**：任务调度优先级
- **执行限制**：燃料、内存、模块大小限制

### 任务生命周期

1. **提交**：客户端提交任务，获得任务 ID
2. **排队**：任务进入调度队列
3. **分配**：任务分配给工作节点
4. **执行**：工作节点执行 WASM
5. **完成**：返回执行结果

### 结果（TaskResult）

任务执行结果包含：

- **result**：执行结果（JSON 字符串）
- **stdout**：标准输出（字节）
- **stderr**：标准错误（字节）
- **time**：执行时间（毫秒）
- **succeeded**：是否成功

## SDK 选择

### 异步客户端 (LunarisClient)

**适用场景**：
- 异步应用（FastAPI、aiohttp）
- 需要高并发
- 需要回调机制

**优势**：
- 非阻塞 I/O
- 更好的并发性能
- 支持上下文管理器

**示例**：

```python
import asyncio
from lunaris.client import LunarisClient

async def process_batch(tasks):
    async with LunarisClient("ws://127.0.0.1:8000", "token") as client:
        # 并发提交多个任务
        task_ids = await asyncio.gather(*[
            client.submit_task(wasm_module, args)
            for wasm_module, args in tasks
        ])
        
        # 等待所有结果
        results = await asyncio.gather(*[
            client.wait_for_task(task_id)
            for task_id in task_ids
        ])
        
        return results
```

### 同步客户端 (SyncLunarisClient)

**适用场景**：
- 同步应用（Flask、Django）
- 脚本和命令行工具
- 不需要异步的场景

**优势**：
- 简单易用
- 无需 `async/await`
- 与同步代码无缝集成

**示例**：

```python
from lunaris.client import SyncLunarisClient

def process_tasks(tasks):
    with SyncLunarisClient("ws://127.0.0.1:8000", "token") as client:
        results = []
        for wasm_module, args in tasks:
            task_id = client.submit_task(wasm_module, args)
            result = client.wait_for_task(task_id)
            results.append(result)
        return results
```

## 高级特性

### 源代码编译

SDK 支持直接从源代码编译并执行：

```python
# C 代码
c_code = '''
#include <stdio.h>
int wmain() {
    printf("Hello from C!\\n");
    return 0;
}
'''
task_id = await client.submit_c(c_code)

# Rust 代码
rust_code = '''
#[no_mangle]
pub extern "C" fn wmain() {
    println!("Hello from Rust!");
}
'''
task_id = await client.submit_rust(rust_code)

# Go 代码
go_code = '''
package main
import "fmt"
func wmain() {
    fmt.Println("Hello from Go!")
}
'''
task_id = await client.submit_go(go_code)
```

### 幂等性

使用幂等键防止重复提交：

```python
# 相同的幂等键返回相同的任务 ID
task_id_1 = await client.submit_task(
    wasm_module,
    idempotency_key="unique-request-123"
)

task_id_2 = await client.submit_task(
    wasm_module,
    idempotency_key="unique-request-123"
)

assert task_id_1 == task_id_2  # 相同的任务 ID
```

### 批量提交

批量提交多个任务：

```python
# 准备多组参数
args_list = [
    ["arg1", "arg2"],
    ["arg3", "arg4"],
    ["arg5", "arg6"],
]

# 批量提交
results = await client.submit_task_many(
    wasm_module=wasm_module,
    args_list=args_list,
    timeout=60  # 60 秒超时
)

# results 与 args_list 顺序一致
for i, result in enumerate(results):
    print(f"任务 {i}: {result.result}")
```

### 回调机制

异步客户端支持回调：

```python
async def on_task_complete(result):
    print(f"任务 {result.task_id} 完成")
    print(f"结果: {result.result}")

task_id = await client.submit_task(
    wasm_module=wasm_module,
    callback=on_task_complete
)
```

### 执行限制

精确控制 WASM 执行资源：

```python
from lunaris.runtime import ExecutionLimits

limits = ExecutionLimits(
    max_fuel=1000000,          # 100 万指令
    max_memory_bytes=67108864, # 64 MB
    max_module_bytes=1048576,  # 1 MB
)

task_id = await client.submit_task(
    wasm_module=wasm_module,
    execution_limits=limits
)
```

### WASI 环境

配置 WASI 环境变量和参数：

```python
from lunaris.client import WasiEnv

wasi_env = WasiEnv(
    env={"KEY": "value"},
    args=["arg1", "arg2"]
)

task_id = await client.submit_task(
    wasm_module=wasm_module,
    wasi_env=wasi_env
)
```

## REST API

除了 WebSocket，SDK 也提供 REST API 查询：

```python
# 获取任务状态
status = await client.get_task_status(task_id)
print(f"状态: {status['status']}")

# 获取任务结果
result = await client.get_task_result(task_id)
print(f"结果: {result}")

# 获取所有任务
tasks = await client.get_tasks()
print(f"任务数量: {tasks['count']}")

# 获取工作节点
workers = await client.get_workers()
print(f"工作节点数量: {workers['count']}")

# 获取统计信息
stats = await client.get_stats()
print(f"运行中的任务: {stats['running_tasks']}")
```

## 错误处理

### 连接错误

```python
try:
    async with LunarisClient("ws://invalid:8000", "token") as client:
        ...
except Exception as e:
    print(f"连接失败: {e}")
```

### 任务错误

```python
try:
    result = await client.wait_for_task(task_id, timeout=5)
except asyncio.TimeoutError:
    print("任务超时")
except RuntimeError as e:
    print(f"任务失败: {e}")
```

## 最佳实践

### 1. 使用上下文管理器

```python
# 推荐
async with LunarisClient(...) as client:
    ...

# 不推荐
client = LunarisClient(...)
await client.connect()
...
await client.close()
```

### 2. 设置超时

```python
# 为长时间运行的任务设置超时
try:
    result = await client.wait_for_task(task_id, timeout=60)
except asyncio.TimeoutError:
    print("任务超时，请检查工作节点状态")
```

### 3. 处理错误

```python
# 总是检查任务是否成功
result = await client.wait_for_task(task_id)
if result.succeeded:
    print(f"成功: {result.result}")
else:
    print(f"失败: {result.stderr.decode('utf-8')}")
```

### 4. 使用幂等键

```python
# 对于重要的任务，使用幂等键防止重复提交
task_id = await client.submit_task(
    wasm_module=wasm_module,
    idempotency_key=f"important-task-{timestamp}"
)
```

## 下一步

- 查看 [异步客户端文档](async-client.md) 了解完整 API
- 查看 [同步客户端文档](sync-client.md) 了解同步 API
- 查看 [示例](examples.md) 了解实际应用
