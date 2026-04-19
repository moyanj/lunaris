# SDK 示例

本页提供 Lunaris SDK 的实际应用示例。

## 基础示例

### 提交 WASM 模块

```python
import asyncio
from lunaris.client import LunarisClient

async def basic_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 提交任务
        task_id = await client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1", "arg2"],
            entry="wmain"
        )
        
        print(f"任务已提交，ID: {task_id}")
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        
        print(f"执行时间: {result.time:.2f}ms")
        print(f"标准输出: {result.stdout.decode('utf-8')}")
        print(f"结果: {result.result}")

asyncio.run(basic_example())
```

### 使用同步客户端

```python
from lunaris.client import SyncLunarisClient

def sync_example():
    with SyncLunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 提交任务
        task_id = client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1", "arg2"]
        )
        
        print(f"任务已提交，ID: {task_id}")
        
        # 等待结果
        result = client.wait_for_task(task_id, timeout=30)
        
        print(f"执行时间: {result.time:.2f}ms")
        print(f"标准输出: {result.stdout.decode('utf-8')}")

if __name__ == "__main__":
    sync_example()
```

## 源代码编译

### C 代码示例

```python
import asyncio
from lunaris.client import LunarisClient

async def c_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # C 源代码
        c_code = '''
        #include <stdio.h>
        #include <stdlib.h>
        
        int wmain(int argc, char** argv) {
            printf("Hello from C!\\n");
            printf("Arguments: %d\\n", argc);
            
            for (int i = 0; i < argc; i++) {
                printf("  arg[%d]: %s\\n", i, argv[i]);
            }
            
            // 计算斐波那契数列
            int n = 10;
            int a = 0, b = 1;
            printf("Fibonacci sequence:\\n");
            for (int i = 0; i < n; i++) {
                printf("%d ", a);
                int temp = a + b;
                a = b;
                b = temp;
            }
            printf("\\n");
            
            return 0;
        }
        '''
        
        # 提交 C 代码
        task_id = await client.submit_c(
            source_code=c_code,
            args=["hello", "world"]
        )
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        
        print(result.stdout.decode('utf-8'))

asyncio.run(c_example())
```

### Rust 代码示例

```python
import asyncio
from lunaris.client import LunarisClient

async def rust_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # Rust 源代码
        rust_code = '''
        #[no_mangle]
        pub extern "C" fn wmain() {
            println!("Hello from Rust!");
            
            // 计算斐波那契数列
            let n = 10;
            let mut a = 0;
            let mut b = 1;
            println!("Fibonacci sequence:");
            for _ in 0..n {
                print!("{} ", a);
                let temp = a + b;
                a = b;
                b = temp;
            }
            println!();
        }
        '''
        
        # 提交 Rust 代码
        task_id = await client.submit_rust(source_code=rust_code)
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        
        print(result.stdout.decode('utf-8'))

asyncio.run(rust_example())
```

## 高级特性

### 批量提交

```python
import asyncio
from lunaris.client import LunarisClient

async def batch_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 准备多组参数
        args_list = [
            ["task1", "arg1"],
            ["task2", "arg2"],
            ["task3", "arg3"],
        ]
        
        # 批量提交
        results = await client.submit_task_many(
            wasm_module=wasm_bytes,
            args_list=args_list,
            timeout=60
        )
        
        # 处理结果
        for i, result in enumerate(results):
            print(f"任务 {i}:")
            print(f"  执行时间: {result.time:.2f}ms")
            print(f"  标准输出: {result.stdout.decode('utf-8')[:100]}")

asyncio.run(batch_example())
```

### 使用回调

```python
import asyncio
from lunaris.client import LunarisClient

async def callback_example():
    # 定义回调函数
    async def on_task_complete(result):
        print(f"任务 {result.task_id} 完成")
        print(f"执行时间: {result.time:.2f}ms")
        print(f"标准输出: {result.stdout.decode('utf-8')}")
    
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 提交任务并注册回调
        task_id = await client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1", "arg2"],
            callback=on_task_complete
        )
        
        print(f"任务已提交，ID: {task_id}")
        
        # 等待一段时间让回调执行
        await asyncio.sleep(5)

asyncio.run(callback_example())
```

### 使用幂等键

```python
import asyncio
import time
from lunaris.client import LunarisClient

async def idempotency_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 生成唯一的幂等键
        idempotency_key = f"task-{int(time.time())}"
        
        # 第一次提交
        task_id_1 = await client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1"],
            idempotency_key=idempotency_key
        )
        print(f"第一次提交，任务 ID: {task_id_1}")
        
        # 使用相同的幂等键再次提交
        task_id_2 = await client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1"],
            idempotency_key=idempotency_key
        )
        print(f"第二次提交，任务 ID: {task_id_2}")
        
        # 应该是相同的任务 ID
        assert task_id_1 == task_id_2
        print("幂等性验证成功！")

asyncio.run(idempotency_example())
```

### 资源限制

```python
import asyncio
from lunaris.client import LunarisClient
from lunaris.runtime import ExecutionLimits

async def limits_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 配置执行限制
        limits = ExecutionLimits(
            max_fuel=1000000,          # 100 万指令
            max_memory_bytes=67108864, # 64 MB
            max_module_bytes=1048576,  # 1 MB
        )
        
        # 提交任务
        task_id = await client.submit_task(
            wasm_module=wasm_bytes,
            execution_limits=limits
        )
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        
        if result.succeeded:
            print(f"执行成功，时间: {result.time:.2f}ms")
        else:
            print(f"执行失败: {result.stderr.decode('utf-8')}")

asyncio.run(limits_example())
```

### WASI 环境配置

```python
import asyncio
from lunaris.client import LunarisClient, WasiEnv

async def wasi_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 读取 WASM 文件
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        # 配置 WASI 环境
        wasi_env = WasiEnv(
            env={
                "KEY1": "value1",
                "KEY2": "value2"
            },
            args=["arg1", "arg2", "arg3"]
        )
        
        # 提交任务
        task_id = await client.submit_task(
            wasm_module=wasm_bytes,
            wasi_env=wasi_env
        )
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        
        print(result.stdout.decode('utf-8'))

asyncio.run(wasi_example())
```

## 监控示例

### 监控任务状态

```python
import asyncio
from lunaris.client import LunarisClient

async def monitor_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 提交任务
        with open("test.wasm", "rb") as f:
            task_id = await client.submit_task(f.read())
        
        # 监控任务状态
        while True:
            status = await client.get_task_status(task_id)
            print(f"任务状态: {status['status']}")
            
            if status['status'] in ['succeeded', 'failed', 'cancelled']:
                break
            
            await asyncio.sleep(1)
        
        # 获取结果
        result = await client.get_task_result(task_id)
        print(f"结果: {result}")

asyncio.run(monitor_example())
```

### 监控系统统计

```python
import asyncio
from lunaris.client import LunarisClient

async def stats_example():
    async with LunarisClient("ws://127.0.0.1:8000", "your-token") as client:
        # 获取系统统计
        stats = await client.get_stats()
        
        print(f"工作节点总数: {stats['workers']['total']}")
        print(f"活跃工作节点: {stats['workers']['active']}")
        print(f"运行中的任务: {stats['running_tasks']}")
        print(f"队列大小: {stats['queue_size']}")
        
        # 获取工作节点详情
        workers = await client.get_workers()
        print(f"\n工作节点列表:")
        for worker in workers['workers']:
            print(f"  - {worker['name']}: {worker['status']}")

asyncio.run(stats_example())
```

## 更多信息

- 查看 [异步客户端 API](async-client.md) 了解完整 API
- 查看 [同步客户端 API](sync-client.md) 了解同步接口
- 查看 [快速开始](../getting-started/quickstart.md) 了解基本用法
