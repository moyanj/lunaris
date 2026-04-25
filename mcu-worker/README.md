# Lunaris ESP32 Worker

Lunaris 的 ESP32 Worker 固件工程，目标是在 ESP32 上以资源受限 Worker 形态接入现有 Master。

当前状态：

- 已建立独立 `mcu-worker/` 固件工程
- 协议层已接入根目录 `proto/*.proto` + nanopb
- Worker 状态机已支持注册、注册回包解析、心跳、消息轮询、控制命令和任务执行回传
- 目标平台收敛为 ESP32
- WASM 运行时固定为 `wasm3`
- 仍保留 `platform` / `websocket` / `engine` 抽象接口，便于后续替换具体实现

## 构建

```bash
./mcu-worker/scripts/fetch_deps.sh
./mcu-worker/scripts/generate_proto.sh
cmake -S mcu-worker -B build/mcu-worker
cmake --build build/mcu-worker
ctest --test-dir build/mcu-worker --output-on-failure
```

当前顶层 CMake 构建仅用于主机侧验证。正式固件构建入口是 `ESP-IDF` 配置。

## 设计约束

- 唯一目标平台为 ESP32
- 依赖项通过脚本拉取：`nanopb` 和 `wasm3`
- 默认注册为 `MCU` worker，禁用压缩
- 当前并发模型固定为单任务
- 协议源直接复用仓库根目录 `proto/*.proto`，`mcu-worker/proto/` 只存放 `nanopb.options` 等 MCU 专属生成配置
- 所有 C 代码统一放在 `src/`
- ESP-IDF 工程配置集中放在 `esp32/`
- 配置优先走编译期宏和平台静态配置，不依赖环境变量
- `main` 面向固件入口，避免宿主机进程式参数注入假设
- 主机侧 `src/platform_default.c` 只用于测试，不代表目标固件平台

## 当前入口行为

- 启动时先走 `platform` 初始化
- 默认从编译期宏填充 `master_uri` / `token` / `name` / `arch` / `memory_size_mb`
- ESP32 平台层可覆写 `name` / `arch` / `memory_size_mb`
- `main` 进入真实 worker 主循环

## 抽象边界

- `src/platform.h`：平台初始化、时间源、设备信息
- `src/websocket.h`：WebSocket 传输抽象，ESP32 版实现应落在同一接口后面
- `src/engine.h`：WASM 执行抽象，当前强制绑定 `wasm3`
