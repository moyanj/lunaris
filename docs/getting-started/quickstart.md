# 快速上手

本指南将帮助您快速启动并运行 Lunaris 分布式 WASM 执行器。

## 第一步：启动主节点

主节点负责任务调度和工作节点管理。

```bash
# 使用 uv
uv run python -m lunaris master --host 127.0.0.1 --port 8000

# 或使用 pip 安装后
lunaris master --host 127.0.0.1 --port 8000
```

主节点启动后，您将看到类似以下输出：

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## 第二步：启动工作节点

工作节点负责执行 WASM 任务。您可以启动 Python 工作节点或 Rust 工作节点。

### Python 工作节点

```bash
# 设置认证令牌
export WORKER_TOKEN="your-secret-token"

# 启动工作节点
uv run python -m lunaris worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --concurrency 4
```

### Rust 工作节点（可选，更高性能）

```bash
# 编译 Rust 工作节点
cd rust-worker && cargo build --release && cd ..

# 启动 Rust 工作节点
./rust-worker/target/release/lunaris-worker \
  --master ws://127.0.0.1:8000 \
  --token $WORKER_TOKEN \
  --concurrency 4
```

## 第三步：提交任务

### 使用 Python SDK

创建一个 Python 脚本来提交 WASM 任务：

```python
import asyncio
from lunaris.client import LunarisClient

async def main():
    # 连接到主节点
    async with LunarisClient("ws://127.0.0.1:8000", "your-secret-token") as client:
        # 提交 WASM 模块
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        task_id = await client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1", "arg2"],
            entry="wmain"
        )
        
        print(f"任务已提交，ID: {task_id}")
        
        # 等待任务完成
        result = await client.wait_for_task(task_id, timeout=30)
        
        print(f"任务完成!")
        print(f"结果: {result.result}")
        print(f"标准输出: {result.stdout.decode('utf-8')}")
        print(f"执行时间: {result.time:.2f}ms")

if __name__ == "__main__":
    asyncio.run(main())
```

### 使用同步 SDK

如果您更喜欢同步 API：

```python
from lunaris.client import SyncLunarisClient

def main():
    # 连接到主节点
    with SyncLunarisClient("ws://127.0.0.1:8000", "your-secret-token") as client:
        # 提交 WASM 模块
        with open("test.wasm", "rb") as f:
            wasm_bytes = f.read()
        
        task_id = client.submit_task(
            wasm_module=wasm_bytes,
            args=["arg1", "arg2"],
            entry="wmain"
        )
        
        print(f"任务已提交，ID: {task_id}")
        
        # 等待任务完成
        result = client.wait_for_task(task_id, timeout=30)
        
        print(f"任务完成!")
        print(f"结果: {result.result}")
        print(f"标准输出: {result.stdout.decode('utf-8')}")
        print(f"执行时间: {result.time:.2f}ms")

if __name__ == "__main__":
    main()
```

## 第四步：监控任务

### 查看任务状态

```python
# 获取任务状态
status = await client.get_task_status(task_id)
print(f"任务状态: {status['status']}")

# 获取任务结果
result = await client.get_task_result(task_id)
print(f"任务结果: {result}")
```

### 查看系统统计

```python
# 获取系统统计信息
stats = await client.get_stats()
print(f"工作节点数量: {stats['workers']['total']}")
print(f"运行中的任务: {stats['running_tasks']}")
print(f"队列大小: {stats['queue_size']}")
```

## 示例：编译并执行 C 代码

Lunaris 支持直接从源代码编译并执行：

```python
import asyncio
from lunaris.client import LunarisClient

async def main():
    async with LunarisClient("ws://127.0.0.1:8000", "your-secret-token") as client:
        # C 源代码
        c_code = '''
        #include <stdio.h>
        
        int wmain(int argc, char** argv) {
            printf("Hello from WASM!\\n");
            printf("Arguments: %d\\n", argc);
            for (int i = 0; i < argc; i++) {
                printf("  arg[%d]: %s\\n", i, argv[i]);
            }
            return 0;
        }
        '''
        
        # 直接提交 C 源代码
        task_id = await client.submit_c(
            source_code=c_code,
            args=["hello", "world"]
        )
        
        # 等待结果
        result = await client.wait_for_task(task_id, timeout=30)
        print(result.stdout.decode('utf-8'))

asyncio.run(main())
```

## 下一步

- 了解 [架构设计](../architecture/overview.md) 以理解系统工作原理
- 查看 [Python SDK 文档](../sdk/overview.md) 获取完整 API 参考
- 阅读 [部署指南](../deployment/guide.md) 了解生产环境配置
