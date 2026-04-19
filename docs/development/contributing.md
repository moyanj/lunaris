# 贡献指南

感谢你对 Lunaris 项目的关注！本指南介绍如何为项目贡献代码。

## 贡献流程

### 1. Fork 仓库

1. 访问 [Lunaris GitHub 仓库](https://github.com/moyanj/Lunaris)
2. 点击右上角的 "Fork" 按钮
3. 克隆你的 Fork 到本地

```bash
git clone https://github.com/YOUR-USERNAME/Lunaris.git
cd Lunaris
```

### 2. 创建分支

```bash
# 创建功能分支
git checkout -b feature/my-feature

# 创建修复分支
git checkout -b fix/my-fix
```

### 3. 编写代码

- 遵循项目的代码规范
- 编写测试（如适用）
- 更新文档（如适用）

### 4. 提交更改

```bash
# 添加文件
git add .

# 提交（使用 Conventional Commits 格式）
git commit -m "feat(master): add task cancellation support"

# 推送
git push origin feature/my-feature
```

### 5. 创建 Pull Request

1. 访问你的 Fork 页面
2. 点击 "Compare & pull request"
3. 填写 PR 描述
4. 提交 PR

## 代码规范

### Python 代码

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

### Rust 代码

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

## 提交信息格式

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

## PR 描述模板

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

## 代码审查

- 所有 PR 需要至少一个审查者批准
- 确保代码符合项目规范
- 确保所有测试通过
- 确保文档已更新

## 反模式

### 绝对禁止

1. **硬编码令牌**
2. **编辑生成的 protobuf**
3. **随意修改 ExecutionLimits 默认值**
4. **无服务运行测试**

## 常见问题

### Q: 如何添加新的 REST 端点？

A: 在 `lunaris/master/api.py` 中添加新的路由。

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

## 更多信息

- 查看 [开发指南](guide.md) 了解详细开发流程
- 查看 [架构设计](../architecture/overview.md) 了解系统设计
- 查看 [部署指南](../deployment/guide.md) 了解部署流程
