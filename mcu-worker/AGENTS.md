# MCU Worker 模块 - ESP32固件

**父级：** 参见根目录AGENTS.md了解项目概览

## 概述

ESP32 Worker固件实现：wasm3运行时 + nanopb协议，目标在资源受限环境以单任务并发模型接入Lunaris Master。

## 项目结构

```
mcu-worker/
├── src/          # C源码（worker.c主循环，engine.* WASM抽象，websocket.* 传输抽象，platform.h HAL）
├── esp32/        # ESP-IDF工程与目标板配置
├── proto/        # nanopb.options（MCU专属生成配置）
├── generated/    # nanopb生成的C协议文件
├── tests/        # 主机侧验证测试
├── scripts/      # 依赖拉取与proto生成脚本
└── third_party/  # nanopb + wasm3（脚本拉取）
```

## 代码导航

| 任务 | 文件 | 关键符号 |
|------|------|----------|
| Worker主循环 | `src/worker.c` | 注册/心跳/消息轮询/任务执行 |
| WASM引擎抽象 | `src/engine.h` | wasm3运行时接口 |
| 传输抽象 | `src/websocket.h` | WebSocket接口（主机侧stub） |
| 平台HAL | `src/platform.h` | 初始化、时间源、设备信息 |
| 静态配置 | `src/config.h` | 所有静态缓冲区尺寸定义 |

## 开发约定

- 新增功能优先落在接口层（engine.h/websocket.h/platform.h），避免把ESP32特定逻辑写进 `worker.c`
- 协议源只能引用根目录 `proto/*.proto`，`mcu-worker/proto/` 只存nanopb生成配置
- 依赖项不手工提交快照，统一通过 `scripts/fetch_deps.sh` 拉取
- 默认保持无动态分配友好设计，静态缓冲区尺寸统一在 `src/config.h`
- 编译期宏填充连接参数（master_uri/token/name/arch），不依赖环境变量
- 主机侧 `src/platform_default.c` 仅用于测试，不代表目标固件平台

## 反模式（本模块）

1. **直接修改worker.c**：新功能先加抽象接口，再在平台层实现
2. **复制proto源文件**：必须引用根目录 `proto/*.proto`
3. **手动提交third_party**：使用 `scripts/fetch_deps.sh` 拉取
4. **动态内存分配**：使用 `config.h` 中的静态缓冲区
5. **假设环境变量可用**：固件环境使用编译期宏
