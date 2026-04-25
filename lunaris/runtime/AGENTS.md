# 运行时模块 - WASM执行层

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

WASM执行沙箱：wasmtime封装，WASI环境，执行限制（燃料、内存、模块大小），临时文件管理。

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| WASM执行 | `engine.py:74` | `WasmSandbox.run`, wasmtime Store/Module/Linker |
| 资源限制 | `limits.py:18` | `ExecutionLimits`, `clamp()` |
| 限制解析 | `limits.py:76` | `_resolve_limit(requested, default, maximum)` |
| WASI配置 | `engine.py:59` | `WasiConfig`, env/argv/stdout_file |
| 结果格式 | `engine.py:49` | `WasmResult` 数据类 |
| 临时文件 | `engine.py` | `tempfile.mkstemp` stdout/stderr捕获 |

## 开发约定

### WASM执行流程
```
WasmSandbox(limits) → run(code, args, entry) → Module → Linker → Store → Instance → main_func()
```

### 限制语义
- **0 = 无限制**：非零值强制限制
- **三层解析**：`requested → default → maximum`
  - 如果 requested ≤ 0，使用 default
  - 如果 maximum > 0 且 (requested > maximum)，使用 maximum

### WASI配置
- `WasiConfig.env` - 环境变量字典
- `WasiConfig.argv` - 命令行参数列表
- 标准输出/错误通过临时文件（`tempfile.mkstemp`）

### 燃料计量执行
- `Config.consume_fuel = True` 如果 `max_fuel > 0`
- `store.set_fuel(max_fuel)` 在实例化前设置
- 燃料耗尽会中断执行

### 临时文件管理
- 自动创建和删除临时stdout/stderr文件
- 文件路径传递给WASM模块访问
- 不要依赖临时文件持久化

## 反模式（本模块）

1. **跳过限制钳制**：必须对用户限制进行默认值和最大值钳制
2. **大模块**：实例化前检查 `max_module_bytes`
3. **重用Store**：每次 `run()` 创建新Store - 不要重用
4. **忽略燃料陷阱**：低燃料可能导致执行不完整
5. **手动清理临时文件**：使用 `with` 语句或函数内自动清理
