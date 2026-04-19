# 主节点架构

主节点是 Lunaris 系统的控制中心，基于 FastAPI 构建，负责任务调度、工作节点管理和状态持久化。

## 核心模块

### 1. API 端点 (`api.py`)

#### REST 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/worker` | GET | 获取所有工作节点 |
| `/task/{task_id}` | GET | 获取任务结果 |
| `/task/{task_id}/status` | GET | 获取任务状态 |
| `/task/{task_id}/events` | GET | 获取任务事件历史 |
| `/task/{task_id}/cancel` | POST | 取消任务 |
| `/tasks` | GET | 获取所有任务 |
| `/tasks/status/{status}` | GET | 按状态筛选任务 |
| `/tasks/worker/{worker_id}` | GET | 获取工作节点的任务 |
| `/worker/{worker_id}/drain` | POST | 设置工作节点排空模式 |
| `/stats` | GET | 获取系统统计信息 |

#### WebSocket 端点

| 端点 | 说明 |
|------|------|
| `/task?token=<token>` | 客户端任务提交和结果接收 |
| `/task/{task_id}/subscribe?token=<token>` | 订阅特定任务结果 |
| `/worker?token=<token>` | 工作节点连接 |

#### 认证

所有端点需要通过以下方式之一提供令牌：

1. **查询参数**：`?token=<token>`
2. **HTTP 头**：`X-Client-Token: <token>`

令牌验证使用 `secrets.compare_digest()` 进行安全比较。

### 2. 任务管理器 (`manager.py`)

#### TaskManager 类

负责任务的创建、调度和状态管理：

```python
class TaskManager:
    def add_task(self, task: Task, ws: WebSocket) -> None
    def get_task(self, task_id: str) -> Optional[Task]
    def get_available_task(self) -> Optional[Task]
    def put_result(self, task_id: str, result: TaskResult) -> None
    def cancel_task(self, task_id: str) -> Optional[Task]
```

**关键特性**：
- **优先级队列**：支持任务优先级调度
- **幂等性**：基于 `idempotency_key` 防止重复提交
- **事件溯源**：通过 `TaskEvent` 记录所有状态变更
- **订阅机制**：客户端可以订阅任务结果

#### WorkerManager 类

负责工作节点的注册、心跳和任务分配：

```python
class WorkerManager:
    def register_worker(self, worker: WorkerRecord, ws: WebSocket) -> None
    def get_available_worker(self) -> Optional[WorkerRecord]
    def handle_heartbeat(self, worker_id: str, state: NodeState) -> None
    def send_control_command(self, worker_id: str, command: CommandType, params: dict) -> None
```

**关键特性**：
- **负载均衡**：基于 `available_slots` 选择工作节点
- **心跳监控**：20 秒超时移除无响应工作节点
- **排空模式**：支持优雅关闭

### 3. 数据模型 (`model.py`)

#### Task 类

```python
@dataclass
class Task:
    task_id: str
    wasm_module: bytes
    args: List[Any]
    entry: str
    priority: int
    status: TaskStatus
    created_at: float
    updated_at: float
    assigned_worker: Optional[str]
    result: Optional[TaskResult]
    idempotency_key: Optional[str]
    execution_limits: Dict[str, int]
```

#### WorkerRecord 类

```python
@dataclass
class WorkerRecord:
    worker_id: str
    name: str
    max_concurrency: int
    current_tasks: int
    status: WorkerStatus
    last_heartbeat: float
    capabilities: Dict[str, Any]
```

#### 状态枚举

```python
class TaskStatus(Enum):
    CREATED = "created"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkerStatus(Enum):
    ACTIVE = "active"
    DRAINING = "draining"
    OFFLINE = "offline"
    LOST = "lost"
```

### 4. 状态持久化 (`store.py`, `file_store.py`)

#### StateStore 抽象基类

```python
class StateStore(ABC):
    @abstractmethod
    def save_snapshot(self, data: Dict[str, Any]) -> None
    
    @abstractmethod
    def load_snapshot(self) -> Optional[Dict[str, Any]]
    
    @abstractmethod
    def append_event(self, event: TaskEvent) -> None
    
    @abstractmethod
    def get_events(self, after_seq: int = 0) -> List[TaskEvent]
```

#### FileStateStore 实现

基于文件的持久化后端：

- **快照**：定期保存完整状态到 `snapshot.json`
- **事件日志**：追加写入 `events.log`
- **恢复**：启动时加载快照 + 重放事件

## 任务调度流程

```
客户端提交任务
      │
      ▼
┌─────────────────┐
│  验证令牌       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  检查幂等性     │◄─── 如果已存在，返回已有任务 ID
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建 Task      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  入队列         │◄─── 优先级队列
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  分配工作节点   │◄─── 选择 available_slots > 0 的工作节点
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  发送任务       │◄─── 通过 WebSocket 发送 Protobuf 消息
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  等待结果       │◄─── 工作节点返回 TaskResult
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  通知客户端     │◄─── 通过 WebSocket 推送结果
└─────────────────┘
```

## 心跳监控

主节点定期检查工作节点心跳：

1. **心跳间隔**：工作节点每 10 秒发送心跳
2. **超时检测**：20 秒未收到心跳标记为 LOST
3. **任务重分配**：LOST 工作节点的任务重新入队

```python
async def check_heartbeat():
    while True:
        await asyncio.sleep(5)  # 每 5 秒检查一次
        for worker in worker_manager.workers:
            if time.time() - worker.last_heartbeat > 20:
                worker_manager.mark_lost(worker.worker_id)
                task_manager.reassign_worker_tasks(worker.worker_id)
```

## 配置选项

### 执行限制

通过命令行参数配置默认和最大执行限制：

```bash
lunaris master \
  --default-max-fuel 1000000 \
  --default-max-memory-bytes 67108864 \
  --max-fuel 10000000 \
  --max-memory-bytes 536870912
```

### 状态持久化

```bash
lunaris master --state-dir /var/lib/lunaris/state
```

## 下一步

- 了解 [Python 工作节点](python-worker.md) 的实现
- 了解 [Rust 工作节点](rust-worker.md) 的高性能特性
- 了解 [通信协议](protocol.md) 的详细规范
