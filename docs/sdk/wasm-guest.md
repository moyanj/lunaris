# WASM Guest SDK

Lunaris 的 WASM Guest SDK 运行在被执行的 WASM 模块内部，面向 Rust、C/C++、Zig、Go 等会被编译到 `wasm32-wasip1` 的语言。

它与 Python 客户端 SDK 不同：

- Python SDK 负责提交任务
- Guest SDK 负责在任务内部读取 Lunaris 运行时上下文、调用宿主能力

当前仓库已经提供首批 Guest SDK：

- Rust: `sdk/rust/lunaris-wasm`
- C: `sdk/c/lunaris.h`
- C++: `sdk/cpp/lunaris.hpp`
- Zig: `sdk/zig/lunaris.zig`
- Go: `sdk/go/lunaris.go`（experimental）

## 运行时约定

### 固定注入的环境变量

Rust worker 会在每次任务执行时固定注入以下环境变量：

- `LUNARIS_TASK_ID`
- `LUNARIS_WORKER_VERSION`
- `LUNARIS_HOST_CAPABILITIES`

说明：

- `LUNARIS_TASK_ID`：十进制 `u64` 字符串
- `LUNARIS_WORKER_VERSION`：worker 的版本字符串，目前来自 `Cargo.toml` 中的 `version`
- `LUNARIS_HOST_CAPABILITIES`：JSON 数组字符串，例如 `["simd"]`

这三个键属于 Lunaris 保留键。Guest 代码可以读取，但不应自行覆盖或假设调用方传入同名值。

### 字符串约定

Guest SDK 第一版统一采用以下约定：

- 所有字符串都按 UTF-8 处理
- `LUNARIS_TASK_ID` 必须是十进制 ASCII 数字
- `LUNARIS_HOST_CAPABILITIES` 必须是紧凑 JSON 数组字符串
- capability 名称必须是小写 ASCII 标识符
- 建议使用字符集合：`[a-z0-9_-]`
- capability 名称不允许包含引号、反斜杠、空白和逗号

这样做的目的是让 Rust、C/C++、Zig 都能在不引入复杂运行时依赖的情况下稳定解析。

### 宿主能力命名

Lunaris 扩展能力使用独立命名空间：

- module: `lunaris:<capability>`
- function: 组内函数名

当前已提供的最小能力组：

- `simd`

其导入符号为：

- module: `lunaris:simd`
- function: `ping`
- function: `add`

## Rust

```toml
[dependencies]
lunaris-wasm = { path = "../../../sdk/rust/lunaris-wasm" }
```

```rust
use lunaris_wasm::{context, simd};

#[unsafe(no_mangle)]
pub extern "C" fn wmain(a: i32, b: i32) -> i32 {
    let task_id = context::task_id().unwrap_or(0);
    let has_simd = context::has_capability("simd").unwrap_or(false);
    println!("task_id={task_id} has_simd={has_simd}");
    simd::add_checked(a, b).unwrap_or(a + b)
}
```

## C

```c
#include "lunaris.h"

int wmain(int a, int b) {
    uint64_t task_id = 0;
    lunaris_task_id(&task_id);
    if (lunaris_has_capability("simd")) {
        return lunaris_simd_add_checked(a, b, NULL);
    }
    return a + b;
}
```

## C++

```cpp
#include "lunaris.hpp"

extern "C" int wmain(int a, int b) {
    if (lunaris::hasCapability("simd")) {
        return lunaris::simd::addChecked(a, b);
    }
    return a + b;
}
```

## Zig

```zig
const std = @import("std");
const lunaris = @import("lunaris.zig");

export fn wmain(a: i32, b: i32) i32 {
    if (lunaris.context.hasCapability("simd")) {
        return lunaris.simd.addChecked(a, b) catch a + b;
    }
    return a + b;
}
```

## Go

```go
package main

import (
    "fmt"

    lunaris "github.com/moyan/lunaris/sdk/go/lunaris"
)

//go:wasmexport wmain
func wmain(a, b int32) int32 {
    if ctx, err := lunaris.CurrentContext(); err == nil {
        fmt.Printf("task=%d worker=%s\n", ctx.TaskID, ctx.WorkerVersion)
    }
    if value, err := lunaris.SIMDAddChecked(a, b); err == nil {
        return value
    }
    return a + b
}
```

## API 范围

第一版 Guest SDK 只做两类封装：

- 任务上下文读取
- 宿主能力调用

当前统一提供：

- `task_id`
- `worker_version`
- `host_capabilities`
- `has_capability`
- `simd::ping`
- `simd::add`

后续新增能力组时，应继续遵守相同的字符串和命名约定。
