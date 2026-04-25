# Guest SDK - 多语言WASM开发套件

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

多语言WASM Guest SDK：Rust/C/C++/Zig/Go/AssemblyScript/Grain，支持读取运行时上下文、调用宿主能力、访问任务元数据。

## 项目结构

```
sdk/
├── rust/               # Rust SDK (`lunaris-wasm` crate)
├── c/                 # C SDK (`lunaris.h` 头文件)
├── cpp/               # C++ SDK (`lunaris.hpp` 头文件)
├── zig/               # Zig SDK (`lunaris.zig`)
├── go/                # Go SDK (`lunaris.go`)
├── assemblyscript/    # AssemblyScript SDK (`lunaris.ts`)
└── grain/             # Grain SDK (`lunaris.gr`)
```

## 代码导航

| 语言 | 入口 | 接口 | 用途 |
|------|------|------|------|
| Rust | `lunaris-wasm/src/lib.rs` | `RuntimeInfo`, `RuntimeContext` | 类型安全的上下文访问 |
| C | `c/lunaris.h` | `lunaris_get_*()` 函数 | 低级环境访问 |
| C++ | `cpp/lunaris.hpp` | `Runtime` 类 | 面向对象包装 |
| Zig | `zig/lunaris.zig` | `Runtime` 模块 | 原生Zig类型 |
| Go | `go/lunaris.go` | `Runtime` 结构 | Go idiomatic接口 |
| AssemblyScript | `assemblyscript/lunaris.ts` | `Runtime` 接口 | TypeScript兼容 |
| Grain | `grain/lunaris.gr` | `Runtime` 对象 | Grain Actor模式 |

## 开发约定

### 统一接口设计
每个SDK提供相同的宿主能力访问：
- **任务元数据**：获取任务ID、Worker信息、版本号
- **环境变量**：访问WASI环境变量 + 宿主注入变量
- **宿主能力**：检测和调用宿主提供的扩展功能
- **错误处理**：一致的错误报告机制

### 环境变量注入
```env
LUNARIS_TASK_ID          # 当前任务ID
LUNARIS_WORKER_VERSION  # Worker版本号
LUNARIS_ARCH            # Worker架构
LUNARIS_HOST_CAPABILITIES # JSON格式的宿主能力列表
```

### 编译时配置
- Rust: Cargo.toml `path = "../.."` 依赖根目录
- C/C++: 编译时指定 `-I../../sdk/c`
- Zig: 在`build.zig`添加路径依赖
- Go: 使用go module导入本地路径
- AssemblyScript: TypeScript配置文件引用
- Grain: Grain.toml依赖路径配置

## 反模式（本模块）

1. **硬编码任务ID**：使用SDK提供的 `get_task_id()` 获取
2. **忽略宿主能力**：先检测 `has_capability()` 再调用
3. **直接访问环境变量**：使用SDK提供的 `get_env()` 方法
4. **跨语言代码复制**：每个SDK独立实现，不要复制代码
5. **跳过编译时配置**：正确设置构建依赖路径