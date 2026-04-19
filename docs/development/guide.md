# 开发指南

本指南介绍如何为 Lunaris 项目贡献代码。

## 开发环境

### 系统要求

- Python >= 3.9
- Rust 工具链（可选）
- `protoc`（protobuf 编译器）
- Git

### 安装开发依赖

```bash
# 克隆仓库
git clone https://github.com/moyanj/Lunaris.git
cd Lunaris

# 创建虚拟环境
uv venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装开发依赖
uv sync

# 安装 Rust 工具链（可选）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## 项目结构

```
lunaris/
├── master/     # 主节点（FastAPI）
│   ├── api.py       # REST/WebSocket 端点
│   ├── manager.py   # 任务/工作节点管理器
│   ├── model.py     # 数据模型
│   ├── store.py     # 状态持久化
│   └── web_app.py   # FastAPI 应用
├── worker/     # Python 工作节点
│   ├── main.py      # WebSocket 客户端
│   └── core.py      # WASM 执行器
├── client/     # SDK
│   ├── client.py    # 异步客户端
│   ├── sync.py      # 同步客户端
│   └── utils.py     # 工具函数
├── runtime/    # WASM 运行时
│   ├── engine.py    # WasmSandbox
│   └── limits.py    # ExecutionLimits
├── proto/      # Protobuf 绑定（自动生成）
└── cli/        # CLI 入口
rust-worker/    # Rust 工作节点
├── src/
│   ├── main.rs      # 入口
│   ├── core.rs      # Worker 结构体
│   ├── engine.rs    # Runner
│   └── proto.rs     # Protobuf 绑定
proto/          # Protobuf 源文件
├── client.proto
├── common.proto
└── worker.proto
```

## 开发工作流

### 1. 创建分支

```bash
# 创建功能分支
git checkout -b feature/my-feature

# 创建修复分支
git checkout -b fix/my-fix
```

### 2. 编写代码

#### Python 代码规范

- **类型注解**：公共 API 必须提供类型注解
- **命名**：snake_case（函数/变量），PascalCase（类）
- **导入**：优先使用绝对路径

```python
# 好的示例
from lunaris.client import LunarisClient
from lunaris.runtime import ExecutionLimits

def submit_task(
    wasm_module: bytes,
    args: List[Any],
    entry: str = "wmain",
    priority: int = 0,
) -> str:
    """提交 WASM 任务"""
    ...
```

#### Rust 代码规范

- **格式化**：提交前运行 `cargo fmt`
- **版本**：Cargo.toml 中 `edition = "2021"`
- **内存**：使用 `mimalloc` 全局分配器

```rust
// 好的示例
#[global_allocator]
static ALLOC: mimalloc::MiMalloc = mimalloc::MiMalloc;

pub async fn run(&self, task: Task) -> Result<TaskResult> {
    // 获取信号量许可
    let _permit = self.semaphore.acquire().await?;
    
    // 执行任务
    tokio::task::spawn_blocking(move || {
        run_wasm(&task.wasm_module, ...)
    }).await?
}
```

### 3. 修改 Protobuf

如果需要修改通信协议：

```bash
# 编辑源文件
vim proto/client.proto
vim proto/common.proto
vim proto/worker.proto

# 重新生成 Python 绑定
./proto/build.sh
```

**注意**：不要直接编辑 `lunaris/proto/*_pb2.py` 文件。

### 4. 运行测试

```bash
# 启动主节点
uv run python -m lunaris master --host 127.0.0.1 --port 8000 &

# 启动工作节点
export WORKER_TOKEN="test-token"
uv run python -m lunaris worker --master ws://127.0.0.1:8000 --token $WORKER_TOKEN &

# 运行测试
python test_localhost_task_lifecycle_ws.py
python test_localhost_limits_ws.py
python test_localhost_rust_ws.py
```

### 5. 提交代码

```bash
# 添加文件
git add .

# 提交（使用祈使句）
git commit -m "feat(master): add task cancellation support"

# 推送
git push origin feature/my-feature
```

## 代码风格

### 提交信息格式

使用 Conventional Commits 格式：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**类型**：
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档
- `style`: 格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**范围**：
- `master`: 主节点
- `worker`: Python 工作节点
- `rust-worker`: Rust 工作节点
- `client`: SDK
- `cli`: CLI
- `proto`: 协议

**示例**：
```
feat(master): add task cancellation API
fix(worker): handle WebSocket disconnection
docs(sdk): update quickstart guide
refactor(runtime): simplify ExecutionLimits
```

## 反模式

### 绝对禁止

1. **硬编码令牌**
   ```python
   # 禁止
   token = "my-secret-value"
   
   # 必须
   token = os.environ.get("WORKER_TOKEN")
   ```

2. **编辑生成的 protobuf**
   ```python
   # 禁止
   vim lunaris/proto/client_pb2.py
   
   # 必须
   vim proto/client.proto
   ./proto/build.sh
   ```

3. **随意修改 ExecutionLimits 默认值**
   ```python
   # 禁止（影响安全）
   max_fuel = 999999999
   
   # 必须（合理的默认值）
   max_fuel = 0  # 无限制，由用户配置
   ```

4. **无服务运行测试**
   ```bash
   # 禁止（集成测试需要服务）
   python test_localhost_task_lifecycle_ws.py  # 主节点未运行
   
   # 必须
   uv run python -m lunaris master &
   python test_localhost_task_lifecycle_ws.py
   ```

## 调试

### Python 调试

```python
# 使用 loguru 日志
from loguru import logger

logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
```

### Rust 调试

```rust
// 使用 tracing 日志
use tracing::{debug, info, warn, error};

debug!("调试信息");
info!("普通信息");
warn!("警告信息");
error!("错误信息");
```

### WebSocket 调试

```bash
# 使用 wscat 测试 WebSocket
npm install -g wscat

# 连接到主节点
wscat -c "ws://localhost:8000/task?token=your-token"

# 发送消息
> {"type": "CreateTask", "wasm_module": "..."}
```

## 性能分析

### Python 性能分析

```python
# 使用 cProfile
import cProfile

def profile_function():
    cProfile.run('my_function()', 'output.prof')

# 使用 py-spy
pip install py-spy
py-spy top --pid <PID>
```

### Rust 性能分析

```bash
# 使用 perf
cargo build --release
perf record ./target/release/lunaris-worker
perf report

# 使用 flamegraph
cargo install flamegraph
cargo flamegraph --bin lunaris-worker
```

## 贡献指南

### 提交 Pull Request

1. Fork 仓库
2. 创建功能分支
3. 编写代码和测试
4. 运行所有测试
5. 提交 Pull Request

### PR 描述模板

```markdown
## 变更描述

简要描述你的变更。

## 变更类型

- [ ] 新功能
- [ ] Bug 修复
- [ ] 文档更新
- [ ] 重构
- [ ] 性能优化

## 测试

描述你如何测试这些变更。

## 相关 Issue

关联的 Issue 编号。

## 截图（如适用）

如果有 UI 变更，提供截图。
```

### 代码审查

- 所有 PR 需要至少一个审查者批准
- 确保代码符合项目规范
- 确保所有测试通过
- 确保文档已更新

## 常见问题

### Q: 如何添加新的 REST 端点？

A: 在 `lunaris/master/api.py` 中添加新的路由：

```python
@app.get("/my-endpoint")
async def my_endpoint(
    state: AppState = Depends(get_app_state),
    _auth: None = Depends(require_client_token),
):
    return Rest(data={"message": "Hello"})
```

### Q: 如何修改任务调度逻辑？

A: 修改 `lunaris/master/manager.py` 中的 `TaskManager` 类。

### Q: 如何添加新的 Protobuf 消息？

A: 编辑 `proto/*.proto` 文件，然后运行 `./proto/build.sh`。

### Q: 如何编译 Rust 工作节点？

A: 使用以下命令：

```bash
cd rust-worker
cargo build --release
```

编译后的可执行文件位于 `target/release/lunaris-worker`。

## 下一步

- 查看 [架构设计](../architecture/overview.md) 了解系统设计
- 查看 [贡献指南](contributing.md) 了解详细的贡献流程
- 查看 [部署指南](../deployment/guide.md) 了解如何部署
