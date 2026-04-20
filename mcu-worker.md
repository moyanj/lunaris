# MCU Worker 设计文档

**版本：** 1.0  
**日期：** 2026-04-19  
**状态：** 设计阶段

## 概述

MCU Worker 是 Lunaris 分布式 WASM 执行器的微控制器扩展组件，允许资源受限的嵌入式设备（如 ESP32、STM32）作为 Worker 节点连接到 Master 节点，执行轻量级 WASM 模块。

### 设计目标

1. **轻量级**：核心代码 < 100KB，最小 RAM 需求 64KB
2. **跨平台**：支持 ESP32、STM32、Arduino 等主流 MCU 平台
3. **兼容性**：使用相同的 WebSocket + Protobuf 协议，无缝集成现有 Master
4. **可扩展**：模块化设计，支持自定义主机函数（GPIO、传感器等）

---

## WASM 运行时选型

### 推荐方案：双运行时支持

| 运行时 | 核心大小 | 最小 RAM | 适用场景 | 优先级 |
|--------|----------|----------|----------|--------|
| **wasm3** | ~64KB | 8KB | 极低资源 MCU（ESP8266、Arduino） | 默认 |
| **WAMR** | ~50-100KB | 256KB | 资源较丰富的 MCU（ESP32-S3、STM32F4） | 可选 |

### wasm3（默认选择）

**优势：**
- 最轻量级的 WASM 运行时
- 纯解释器，使用 Threaded Interpreter 技术
- 支持几乎所有 MCU 平台
- 极低的启动延迟

**性能参考（ESP32 fib(24)）：**
- wasm3: ~297ms
- 原生 C: ~20ms
- 开销：约 15x

**GitHub:** https://github.com/wasm3/wasm3

### WAMR（WebAssembly Micro Runtime）

**优势：**
- Bytecode Alliance 官方项目
- 多种执行模式：Interpreter、Fast Interpreter、AOT
- ESP-IDF 官方支持
- AOT 模式性能接近原生 80-90%

**ESP-IDF 集成：**
```bash
idf.py add-dependency "espressif/wasm-micro-runtime^2.4.0~1"
```

**GitHub:** https://github.com/bytecodealliance/wasm-micro-runtime

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Master Node                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ TaskManager │  │WorkerManager│  │  API Server │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket + Protobuf
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                      MCU Worker                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  WebSocket Client                    │   │
│  │  - 连接管理  - 心跳  - 消息序列化/反序列化          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Worker Core                         │   │
│  │  - 任务接收  - 状态管理  - 结果报告                 │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  WASM Engine                         │   │
│  │  - wasm3 / WAMR 运行时  - 资源限制  - 执行隔离     │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Platform HAL                        │   │
│  │  - 网络接口  - 定时器  - GPIO  - 存储               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 组件职责

| 组件 | 职责 | 关键接口 |
|------|------|----------|
| **WebSocket Client** | 连接 Master、心跳维护、消息收发 | `ws_connect()`, `ws_send()`, `ws_recv()` |
| **Worker Core** | 任务调度、状态管理、结果报告 | `worker_init()`, `worker_run()`, `worker_shutdown()` |
| **WASM Engine** | WASM 模块加载、执行、资源限制 | `engine_load()`, `engine_exec()`, `engine_unload()` |
| **Platform HAL** | 硬件抽象，平台特定实现 | `platform_net_*()`, `platform_timer_*()`, `platform_gpio_*()` |

---

## 目录结构

```
mcu-worker/
├── CMakeLists.txt                  # 顶层 CMake 配置
├── README.md                       # 用户文档
├── AGENTS.md                       # AI 知识库
├── DESIGN.md                       # 本文档
│
├── src/                            # 核心源码
│   ├── main.c                      # 入口点
│   ├── worker.c                    # Worker 核心逻辑
│   ├── worker.h
│   ├── engine.c                    # WASM 执行引擎
│   ├── engine.h
│   ├── websocket.c                 # WebSocket 客户端
│   ├── websocket.h
│   ├── proto.c                     # Protobuf 序列化（nanopb）
│   ├── proto.h
│   └── config.h                    # 编译配置
│
├── platform/                       # 平台抽象层
│   ├── platform.h                  # 平台接口定义
│   ├── esp32/
│   │   ├── platform_esp32.c        # ESP32 实现
│   │   ├── CMakeLists.txt
│   │   └── sdkconfig.defaults
│   ├── stm32/
│   │   ├── platform_stm32.c        # STM32 实现
│   │   ├── CMakeLists.txt
│   │   └── stm32_config.h
│   └── arduino/
│       ├── platform_arduino.c      # Arduino 实现
│       ├── CMakeLists.txt
│       └── platformio.ini
│
├── proto/                          # Protobuf 定义
│   ├── worker.proto                # 从根目录复制或符号链接
│   ├── common.proto
│   └── nanopb.options              # nanopb 配置
│
├── third_party/                    # 第三方依赖
│   ├── wasm3/                      # wasm3 运行时
│   └── wamr/                       # WAMR 运行时（可选）
│
├── examples/                       # 示例代码
│   ├── blink/                      # LED 闪烁示例
│   ├── sensor/                     # 传感器读取示例
│   └── minimal/                    # 最小化示例
│
└── tests/                          # 测试
    ├── test_proto.c
    ├── test_engine.c
    └── test_worker.c
```

---

## 通信协议

### 协议概览

MCU Worker 使用与现有 Worker 相同的 WebSocket + Protobuf 协议，确保与 Master 节点完全兼容。

### 消息类型

| 消息 | 方向 | 用途 |
|------|------|------|
| `NodeRegistration` | Worker → Master | 节点注册 |
| `NodeRegistrationReply` | Master → Worker | 注册回复 |
| `NodeStatus` | Worker → Master | 心跳状态 |
| `Task` | Master → Worker | 任务分发 |
| `TaskAccepted` | Worker → Master | 任务接受确认 |
| `TaskResult` | Worker → Master | 任务结果 |
| `ControlCommand` | Master → Worker | 控制命令 |

### Protobuf 处理

使用 **nanopb** 库进行 Protobuf 序列化/反序列化：

- **优势**：纯 C 实现，无动态内存分配，适合 MCU
- **GitHub:** https://github.com/nanopb/nanopb

### 通信流程

```
Master                                    MCU Worker
   │                                           │
   │◄──── WebSocket 连接 ─────────────────────│
   │                                           │
   │◄──── NodeRegistration ───────────────────│
   │                                           │
   │───── NodeRegistrationReply ──────────────►│
   │                                           │
   │◄──── NodeStatus (心跳，每10秒) ──────────│
   │                                           │
   │───── Task ───────────────────────────────►│
   │                                           │
   │◄──── TaskAccepted ───────────────────────│
   │                                           │
   │         [WASM 执行中...]                  │
   │                                           │
   │◄──── TaskResult ─────────────────────────│
   │                                           │
```

---

## 平台支持

### ESP32 系列

**支持芯片：** ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-C6

**网络接口：** WiFi（内置）

**WASM 运行时：** wasm3（默认）, WAMR（官方支持）

**开发框架：** ESP-IDF

**特性：**
- 官方 WAMR 组件支持
- 丰富的外设 API（GPIO, I2C, SPI, ADC）
- OTA 更新支持

### STM32 系列

**支持芯片：** STM32F4, STM32F7, STM32H7

**网络接口：** 
- 以太网（内置 MAC + 外部 PHY）
- WiFi（外部模块，如 ESP8266）

**WASM 运行时：** wasm3

**开发框架：** STM32CubeMX + HAL

**注意事项：**
- 需要足够的 RAM（推荐 256KB+）
- F4 系列性能有限，建议简单任务

### Arduino

**支持板卡：** Arduino Mega, Arduino Due, Arduino Nano 33 IoT

**网络接口：**
- WiFi（WiFiNINA, WiFi101）
- 以太网（Ethernet Shield）

**WASM 运行时：** wasm3

**开发框架：** Arduino IDE / PlatformIO

**注意事项：**
- RAM 非常有限（8-96KB），仅支持极简单任务
- 建议仅用于学习和原型开发

---

## 内存管理

### 静态内存分配策略

```c
// config.h
#define WASM_HEAP_SIZE      (32 * 1024)   // 32KB WASM 堆
#define WASM_STACK_SIZE     (8 * 1024)    // 8KB WASM 栈
#define WS_BUFFER_SIZE      (4 * 1024)    // 4KB WebSocket 缓冲区
#define TASK_QUEUE_SIZE     4             // 最多排队 4 个任务
```

### 内存布局

```
┌─────────────────────────────────────┐
│         系统栈 (8-16KB)             │
├─────────────────────────────────────┤
│         WebSocket 缓冲区 (4KB)      │
├─────────────────────────────────────┤
│         WASM 堆 (32KB)              │
├─────────────────────────────────────┤
│         WASM 栈 (8KB)               │
├─────────────────────────────────────┤
│         Protobuf 缓冲区 (2KB)       │
├─────────────────────────────────────┤
│         任务队列 (1KB)              │
└─────────────────────────────────────┘
总计：~56KB（最小配置）
```

### 资源限制

```c
// 默认执行限制
#define DEFAULT_MAX_FUEL        0           // 无限制
#define DEFAULT_MAX_MEMORY      (32 * 1024) // 32KB
#define DEFAULT_MAX_MODULE      (64 * 1024) // 64KB

// 最大执行限制
#define MAX_FUEL                1000000
#define MAX_MEMORY              (64 * 1024) // 64KB
#define MAX_MODULE              (128 * 1024) // 128KB
```

---

## 主机函数 API

MCU Worker 提供一组主机函数，允许 WASM 模块访问硬件资源。

### GPIO

```c
// digital_write(pin, value)
void host_gpio_digital_write(uint32_t pin, uint32_t value);

// digital_read(pin) -> uint32_t
uint32_t host_gpio_digital_read(uint32_t pin);

// pin_mode(pin, mode)  // 0=INPUT, 1=OUTPUT
void host_gpio_pin_mode(uint32_t pin, uint32_t mode);
```

### 模拟输入

```c
// analog_read(pin) -> uint32_t
uint32_t host_analog_read(uint32_t pin);

// analog_write(pin, value)  // PWM
void host_analog_write(uint32_t pin, uint32_t value);
```

### 定时器

```c
// delay_ms(ms)
void host_delay_ms(uint32_t ms);

// millis() -> uint32_t
uint32_t host_millis(void);
```

### 串口

```c
// serial_print(str)
void host_serial_print(const char* str);

// serial_println(str)
void host_serial_println(const char* str);
```

### 注册示例（wasm3）

```c
// 将主机函数注册到 WASM 运行时
IM3Function f;
m3_LinkRawFunction(module, "env", "digital_write", "v(ii)", &host_gpio_digital_write);
m3_LinkRawFunction(module, "env", "digital_read", "i(i)", &host_gpio_digital_read);
m3_LinkRawFunction(module, "env", "delay_ms", "v(i)", &host_delay_ms);
m3_LinkRawFunction(module, "env", "millis", "i()", &host_millis);
```

---

## 实现阶段

### 阶段 1：核心框架（2 周）

- [ ] 项目结构搭建（CMake）
- [ ] Protobuf 集成（nanopb）
- [ ] WebSocket 客户端实现
- [ ] Worker 核心逻辑
- [ ] 简单的回显测试

### 阶段 2：WASM 引擎（2 周）

- [ ] wasm3 集成
- [ ] 任务执行流程
- [ ] 资源限制实现
- [ ] 主机函数基础 API

### 阶段 3：平台适配（3 周）

- [ ] ESP32 平台 HAL
- [ ] STM32 平台 HAL
- [ ] Arduino 平台 HAL
- [ ] 平台特定示例

### 阶段 4：完善与测试（2 周）

- [ ] 错误处理完善
- [ ] 单元测试
- [ ] 集成测试
- [ ] 文档完善

### 阶段 5：高级特性（可选）

- [ ] WAMR 支持
- [ ] AOT 编译支持
- [ ] OTA 更新
- [ ] 安全增强（WASM 沙箱）

---

## 与现有 Worker 的对比

| 特性 | Python Worker | Rust Worker | MCU Worker |
|------|---------------|-------------|------------|
| 语言 | Python | Rust | C |
| WASM 运行时 | wasmtime | wasmtime | wasm3 / WAMR |
| 并发模型 | ProcessPool | tokio async | 单任务/协作式 |
| 最小内存 | ~50MB | ~20MB | ~64KB |
| 适用场景 | 通用服务器 | 高性能服务器 | 嵌入式设备 |
| 平台 | x86_64, ARM64 | x86_64, ARM64 | ESP32, STM32, Arduino |

---

## 参考资料

### WASM 运行时

- [wasm3](https://github.com/wasm3/wasm3) - 最轻量级 WASM 运行时
- [WAMR](https://github.com/bytecodealliance/wasm-micro-runtime) - Bytecode Alliance 官方项目
- [ESP-WASMachine](https://github.com/espressif/esp-wasmachine) - Espressif 官方方案
- [AkiraOS](https://github.com/ArturR0k3r/AkiraOS) - Zephyr + WAMR 嵌入式 OS

### Protobuf

- [nanopb](https://github.com/nanopb/nanopb) - 适合 MCU 的 Protobuf 实现

### WebSocket

- [libwebsockets](https://libwebsockets.org/) - 轻量级 WebSocket 库
- [esp_websocket_client](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/protocols/esp_websocket_client.html) - ESP-IDF 内置

---

## 待讨论问题

1. **任务队列策略**：MCU 资源有限，是否支持任务排队？
2. **安全考虑**：WASM 模块验证、签名验证？
3. **固件更新**：是否需要 OTA 支持？
4. **监控与调试**：如何远程调试 MCU Worker？
5. **认证机制**：MCU 上如何安全存储 Token？
