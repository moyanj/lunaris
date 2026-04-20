# WASI P1 扩展宿主能力设计

## 概述

Lunaris 当前已经支持 WASI Preview 1：

- Python 执行器通过 `linker.define_wasi()` 注入 WASI P1
- Rust 执行器通过 `wasmtime_wasi::p1::add_to_linker_sync()` 注入 WASI P1

本设计不替换 WASI P1，也不尝试实现 WASI Preview 2。目标是在保留 WASI P1 兼容性的前提下，为 Lunaris 增加一套可授权、可调度、可扩展的宿主能力系统。

简而言之：

- `WASI P1` 继续作为基础系统接口
- `Lunaris Host Extensions` 作为额外扩展接口
- 任务在提交时传入一个宿主能力组数组
- 主节点按能力组调度到合适的工作节点
- 执行器按组注入扩展接口；一旦授权某个组，就注入该组下整套已实现函数

## 设计目标

- 兼容现有 WASI P1 模块，不破坏已有执行路径
- 支持任务级能力组声明，而不是全局无差别暴露所有宿主函数
- 同时兼容 Python worker 和 Rust worker
- 为编译到 WASM 的语言提供 guest SDK，而不是要求用户直接手写导入 ABI
- 让主节点在调度前就知道任务需要哪些能力
- 支持渐进扩展，先落地简单标量接口，再扩展到复杂缓冲区接口

## 非目标

- 不引入 WASI Preview 2 组件模型
- 不在第一阶段支持通用文件系统读写能力扩展
- 不把能力组数组设计成资源级授权系统
- 不要求所有宿主函数在第一版就支持字符串或字节缓冲区返回

## 核心原则

### 1. WASI P1 是基础，不是能力系统

WASI P1 负责标准输入输出、环境变量、参数等通用运行时能力。Lunaris 扩展能力不应复用 `wasi_env` 承载，也不应伪装成环境变量。

### 2. 扩展组不得与 WASI P1 重合

Lunaris 扩展组只能承载 WASI P1 未覆盖的宿主能力，不能重复定义以下已经属于 WASI P1 的接口职责：

- 标准输入输出
- 环境变量
- 进程参数
- 预打开目录和标准文件描述符语义
- 其他已经由 `wasi_snapshot_preview1` 提供的系统接口

因此：

- 不允许设计 `stdio`、`env`、`args` 这类与 WASI P1 重合的扩展组
- 不允许在 `lunaris:*` 下重新包装一套与 WASI P1 等价的文件或进程接口
- 扩展组应聚焦 `http`、`socket`、`kv` 这类 WASI P1 没有标准化提供的能力

### 3. capability group 是授权单位，import 是 ABI 单位

任务声明的是能力组，例如：

- `http`
- `socket`
- `log`
- `kv`

WASM 实际导入的是组内扩展函数，例如：

- `lunaris:http/request`
- `lunaris:http/response_read`
- `lunaris:socket/open`
- `lunaris:socket/send`

一个能力组可以映射到一个或多个导入函数。

### 4. 调度层和运行时层都要做校验

只在 runtime 做能力校验是不够的。主节点必须在派发前确认目标 worker 支持所需能力；运行时仍需再次校验，避免因注册错误导致越权。

### 5. 先稳定分组，再细化组内 ABI

第一阶段先确定能力组边界和授权链路，再逐步设计组内函数 ABI。涉及字符串、JSON、字节流的组内接口应统一 guest memory 约定，避免每个能力组各自定义。

## 能力模型

### 任务请求能力组

客户端提交任务时显式传入能力组数组：

```json
["http", "socket"]
```

这表示该任务希望启用的宿主能力组集合。

建议字段名：

- `host_capabilities`

语义：

- 为空数组：仅允许使用 WASI P1，不注入任何 Lunaris 扩展能力
- 非空数组：只允许注入数组中列出的能力组

### 工作节点提供能力组

工作节点在注册时上报自身支持的能力组集合，例如：

```json
["http", "socket", "log"]
```

建议字段名：

- `provided_capabilities`

语义：

- 表示该 worker 进程和其所在宿主环境真正实现了哪些扩展能力组
- 该集合用于主节点调度决策

### 调度匹配规则

主节点只允许将任务派发给满足以下条件的 worker：

```text
set(task.host_capabilities) ⊆ set(worker.provided_capabilities)
```

如果没有可用 worker：

- 任务保持排队
- 调度器等待支持这些能力组的 worker 上线或释放容量

### 能力组与组内函数

能力组是注入和授权边界，不是最终 API 名称。

例如：

- `http` 能力组下可包含 `lunaris:http/request`、`lunaris:http/response_read`
- `socket` 能力组下可包含 `lunaris:socket/open`、`lunaris:socket/send`、`lunaris:socket/recv`
- `log` 能力组下可包含 `lunaris:log/write`

这意味着：

- 协议和调度层只关心组，例如 `http`
- 运行时注入层把组映射到一整批导入函数
- WASM 模块依赖的是组内函数，而不是能力组字符串本身

一旦任务声明了某个组，例如 `http`：

- runtime 注入 `http` 组下整套已实现接口
- 不再要求任务继续声明 `http.request`、`http.response_read` 这类细粒度名称
- 组内函数的可用范围由当前 worker 的实现版本决定

## 扩展命名空间

Lunaris 扩展函数不应放在 `wasi_snapshot_preview1` 下，而应使用独立命名空间，避免与标准 WASI 语义混淆。

这是一个硬约束：

- `wasi_snapshot_preview1` 只承载标准 WASI P1
- `lunaris:*` 只承载 Lunaris 扩展组
- 两者在职责上不重合，在符号名上也不重合

推荐命名格式：

```text
module = "lunaris:clock", function = "now_ms"
module = "lunaris:random", function = "u32"
module = "lunaris:log", function = "write"
module = "lunaris:kv", function = "get"
```

优点：

- 与标准 WASI P1 明确隔离
- 避免扩展接口与 WASI P1 发生语义重复
- 能表达能力所属域
- 便于 Python 和 Rust 两端保持一致 ABI

## 协议设计

### Client -> Master

在 `CreateTask` 中新增能力组数组：

```protobuf
message HostCapabilities {
  repeated string items = 1;
}

message CreateTask {
  bytes wasm_module = 1;
  string args = 2;
  string entry = 3;
  uint32 priority = 4;
  common.WasiEnv wasi_env = 6;
  common.ExecutionLimits execution_limits = 7;
  string request_id = 8;
  string idempotency_key = 9;
  common.HostCapabilities host_capabilities = 10;
}
```

### Master -> Worker

在下发给 worker 的 `Task` 中保留同样字段：

```protobuf
message Task {
  string task_id = 1;
  bytes wasm_module = 2;
  string args = 3;
  string entry = 4;
  uint32 priority = 5;
  common.WasiEnv wasi_env = 6;
  common.ExecutionLimits execution_limits = 7;
  uint32 attempt = 8;
  common.HostCapabilities host_capabilities = 9;
}
```

### Worker Registration

工作节点注册时上报自己支持的能力组集合：

```protobuf
message NodeRegistration {
  string name = 1;
  string arch = 2;
  uint32 max_concurrency = 3;
  uint64 memory_size = 4;
  string token = 5;
  common.HostCapabilities provided_capabilities = 6;
}
```

## Guest SDK 设计

能力组只解决授权、调度和运行时注入问题，但这还不够。对于编译到 WASM 的语言，Lunaris 还需要提供 guest SDK，负责把底层导入 ABI 封装成语言友好的 API。

这里的 SDK 不是 Python 客户端 SDK，而是运行在 WASM 模块内部、由业务代码直接调用的语言 SDK。

### 为什么必须提供 guest SDK

如果没有 guest SDK，使用者需要自己处理以下问题：

- 手写 `extern` / `import` 声明
- 自己维护 `ptr + len` 内存约定
- 自己定义错误码和返回值解码
- 自己适配不同语言的字符串和字节切片模型

这会导致：

- ABI 难以稳定
- 多语言体验割裂
- 用户代码直接绑定底层导入名，后续演进困难

因此，推荐架构应为两层：

- 底层：`lunaris:*` 扩展导入 ABI
- 上层：各语言 guest SDK

### SDK 与能力组的关系

能力组是运行时注入单位，SDK 是开发体验单位。

例如：

- 任务声明 `["http"]`
- runtime 整组注入 `lunaris:http/*`
- Rust SDK 在此基础上提供 `lunaris::http::get()`、`lunaris::http::request()`
- C SDK 在此基础上提供 `lunaris_http_get()`、`lunaris_http_request()`

也就是说：

- 调度和授权看组
- WASM import 看组内函数
- 业务代码通过 SDK 使用，不直接依赖裸 ABI

### SDK 交付形态

建议至少提供以下 guest SDK：

- Rust SDK：优先级最高
- C SDK：作为最低公共 ABI 层
- Zig SDK：可基于 C ABI 或直接封装
- Go SDK：谨慎支持，因 `GOOS=wasip1` 下运行时限制较多

建议目录结构：

```text
guest-sdk/
  rust/
  c/
  zig/
  go/
```

或放在仓库内更明确的位置：

```text
guest/
  rust/
  c/
  zig/
  go/
```

### SDK 设计原则

#### 1. 不直接暴露全部底层 import 细节

SDK 应封装：

- 导入函数声明
- 错误码到语言错误类型的转换
- 内存分配与释放
- 请求和响应对象封装

#### 2. 与能力组一一对应组织模块

建议每个能力组对应一个 SDK 模块：

- Rust: `lunaris::http`, `lunaris::socket`
- C: `lunaris_http_*`, `lunaris_socket_*`
- Zig: `lunaris.http`, `lunaris.socket`

这样可以让 SDK 结构与运行时组边界保持一致。

#### 3. SDK 不绕过授权模型

SDK 可以封装组内多个函数，但不能改变能力组粒度。

例如：

- 任务未声明 `socket`
- 即使代码链接了 `socket` SDK，也应在实例化或调用时失败

SDK 只是开发辅助层，不是授权层。

#### 4. 优先稳定语义，再稳定二进制接口

对于 `http`、`socket` 这类复杂能力组，先稳定：

- 请求模型
- 错误模型
- 同步/异步语义

然后再冻结底层 ABI。否则 SDK 会频繁破坏兼容性。

### Rust SDK 方向

Rust 应该是第一优先级，因为当前项目已经支持 Rust 源码编译到 WASM。

建议形态：

```rust
pub mod http;
pub mod socket;
pub mod error;
```

调用示例：

```rust
let resp = lunaris::http::get("https://example.com")?;
```

Rust SDK 内部负责：

- `extern "C"` 或等效导入绑定
- `String` / `Vec<u8>` 与 guest memory ABI 的转换
- `Result<T, Error>` 封装

### C SDK 方向

C SDK 应作为最基础的跨语言 ABI 包装层，便于 Zig 等语言复用。

建议形态：

```c
int32_t lunaris_http_get(struct lunaris_string url, struct lunaris_http_response* out);
int32_t lunaris_socket_open(struct lunaris_string addr, int32_t* handle);
```

C SDK 需要定义稳定的：

- `lunaris_string`
- `lunaris_bytes`
- `lunaris_error_code`
- 各能力组的数据结构

### Zig / Go SDK 方向

Zig 可优先复用 C SDK，降低维护成本。

Go 需要更谨慎：

- 如果 Go 的 `wasip1` 目标下运行时约束过强，可只提供实验性支持
- 不应为了 Go 改写整个底层 ABI 设计

### 版本策略

guest SDK 需要独立版本化，不能只跟随服务端版本模糊演进。

建议：

- 能力组级别标记稳定性，例如 `http` 为 experimental
- SDK 暴露 semver
- ABI 破坏性变更时提升主版本

### 文档与示例

每个能力组都应同时提供两类文档：

- 宿主设计文档：给 Lunaris 实现者看
- guest SDK 示例：给 WASM 模块作者看

例如 `http` 组至少应附带：

- Rust 示例
- C 示例
- 对应需要声明的 `host_capabilities=["http"]`

## 主节点设计

### 任务模型

`Task` 增加字段：

- `host_capabilities: list[str]`

要求：

- 持久化到 snapshot
- 出现在事件负载和 REST 返回中
- 与 `wasi_env`、`execution_limits` 平行存在

### 工作节点模型

`WorkerRecord` 增加字段：

- `provided_capabilities: list[str]`

要求：

- 注册时保存
- 在 worker 查询接口中可见
- 用于调度选择

### API 层校验

主节点在接收 `CreateTask` 时应完成以下工作：

- 对能力组数组去重
- 规范化排序，降低快照噪声
- 校验格式是否合法
- 拒绝未知格式，例如空字符串、包含空白前后缀、过长名称

推荐能力组命名规则：

```text
<group>
```

例如：

- `http`
- `socket`
- `log`
- `kv`

### 调度器行为

调度器在选择 worker 时应增加能力过滤：

1. 先筛掉已断开、drain 中、无空闲槽位的 worker
2. 再筛掉不满足能力子集要求的 worker
3. 最后在候选 worker 中按当前空闲容量或既有策略选择

如果一个任务能力组要求比较特殊，调度器不应把它错误派发到不支持该组的 worker，再依赖运行时报错回收。

## 执行器设计

### 总体思路

执行器需要同时注入两类接口：

- 标准 `WASI P1`
- 当前任务被授权的 `Lunaris Host Extensions`

伪代码：

```text
create linker
add wasi p1
register lunaris host extensions by task.host_capabilities
instantiate module
call entry
```

### Python 执行器

建议在 `lunaris/runtime/` 下新增能力注册模块，例如：

- `capabilities.py`
- `host_context.py`

其中：

- `CapabilityRegistry` 负责能力组到导入函数集合的映射
- `HostContext` 负责承载当前任务的授权集合和宿主实现依赖
- `WasmSandbox.run()` 在实例化前按 `host_capabilities` 注册对应能力组的扩展函数

建议接口形态：

```python
registry.register_all(linker, store, host_context, enabled_capabilities)
```

### Rust 执行器

建议在 `rust-worker/src/` 下新增：

- `capabilities.rs`

其中：

- `register_capabilities(linker, enabled_caps)` 负责按能力组注入函数
- `HostState` 新增当前任务授权的 capability 集合
- 每个宿主函数内部可以访问 `HostState` 做二次鉴权

## ABI 设计

### 第一阶段：先定义组，再挑最小函数集

第一阶段建议先落 2 个能力组：

- `log`
- `http`

其中：

- `log` 可以先提供少量函数验证“组授权 -> 组内函数注册”这条链路
- `http` 可以作为后续复杂 ABI 的代表组，但不要求第一版就完整实现

### 第二阶段：输入参数与缓冲区

涉及字符串、JSON、日志文本、KV 值时，需要统一 guest memory ABI。推荐采用典型的线性内存指针方案：

- guest 传入 `ptr + len`
- host 从 memory 读取输入
- 返回值通过 caller 提供缓冲区或二次调用接口获取

但这部分应单独设计，不建议和第一阶段一起上线。

## 二次鉴权

运行时除了“按能力组注册函数”之外，宿主函数内部仍应检查当前任务是否真的持有该组。

原因：

- 防止注册表错误导致多余函数被注入
- 防止未来某些动态分发路径绕过注册层
- 让错误语义更明确

错误建议统一为：

- `missing host capability group: <group>`

而不是直接向用户暴露底层 wasmtime 导入错误。

## 能力组分类

为避免未来能力体系失控，建议把能力分成三类：

### 1. 纯宿主辅助组

不访问外部网络或持久化资源，主要提供宿主辅助能力：

- `log`
- `clock`
- `random`

### 2. 通信类能力组

直接暴露对外通信语义：

- `http`
- `socket`

### 3. 外部资源能力组

会访问外部系统或持久状态：

- `kv`
- `blob`
- `queue`

第三类不应只靠组名长期承载。后续若落地，应增加参数化授权或资源范围约束，例如允许访问哪些域名、端口、桶、键空间。

## 兼容性

### 对现有 WASI P1 模块的兼容

完全兼容。

不使用 Lunaris 扩展能力的 WASM 模块：

- 不需要修改
- 不需要传 `host_capabilities`
- 仍按原有 WASI P1 路径执行

### 对现有 worker 的兼容

需要考虑协议滚动升级。

建议策略：

- 新字段使用 protobuf 的向后兼容扩展方式
- 老 worker 未上报 `provided_capabilities` 时，视为只支持空能力集
- 老 client 未传 `host_capabilities` 时，视为空数组

这样可以做到：

- 老任务仍能跑
- 新任务不会被错误派发到旧 worker

## 错误模型

建议区分三类错误：

### 1. 调度前错误

例如能力组名称非法：

- 在 `CreateTask` 阶段直接拒绝

### 2. 调度等待

例如没有 worker 支持该能力组：

- 任务保持排队
- 通过任务状态和事件显示“等待匹配能力组的 worker”

### 3. 运行时错误

例如模块导入了未授权组下的函数，或 host function 二次鉴权失败：

- 任务失败
- stderr 或错误事件中明确标注能力组名称

## 观测与审计

建议在事件和日志中增加以下信息：

- 任务请求能力组数组
- worker 提供能力组数组
- 调度匹配是否因为能力组不足而跳过 worker
- 运行时 capability group 拒绝原因

这有助于排查：

- 为什么任务一直排队
- 为什么某个 worker 从不接某类任务
- 为什么模块实例化失败

## 建议的分阶段落地

### Phase 1：能力组链路打通

- protobuf 增加 `host_capabilities` 和 `provided_capabilities`
- 客户端支持传能力组数组
- 主节点支持持久化和调度过滤
- Python/Rust 执行器支持 capability registry
- 先实现 `log` 组的最小函数集

### Phase 2：通信类能力组

- 增加 `http`
- 视需要增加 `socket`
- 增加统一错误模型与审计日志

### Phase 3：资源类能力组

- 设计线性内存 ABI
- 增加 `kv`、`blob`、`queue`
- 为资源类能力增加参数化授权模型

## 示例

### 任务提交

```python
await client.submit_task(
    wasm_module=wasm_bytes,
    args=[],
    entry="wmain",
    host_capabilities=["http", "socket"],
)
```

### 工作节点注册

```text
provided_capabilities = [
  "http",
  "socket",
  "log",
]
```

### WASM 导入示意

```wat
(import "lunaris:http" "request" (func $http_request (param i32 i32 i32 i32) (result i32)))
(import "lunaris:socket" "open" (func $socket_open (param i32 i32) (result i32)))
```

如果任务只声明了 `["http"]`，则：

- `lunaris:http/*` 下的已实现函数可以注册
- `lunaris:socket/*` 不应被注册
- 模块若静态依赖 `lunaris:socket/open`，实例化应失败，并给出明确错误

## 结论

Lunaris 的正确方向不是放弃 WASI P1，而是在 WASI P1 之上增加一层受能力数组控制的扩展宿主接口。

这套设计的关键点是：

- 保留 `WASI P1` 作为标准基础能力
- 用独立命名空间承载 `Lunaris Host Extensions`
- 用 `host_capabilities` 描述任务请求的能力组
- 用 `provided_capabilities` 描述 worker 提供的能力组
- 让主节点调度和运行时注册同时参与鉴权

这样既能保持对现有 WASI P1 模块的兼容，也能为后续 `http`、`socket`、`kv` 等扩展能力组提供清晰的演进路径。
