lunaris-project/
├── lunaris/                          # 主 Python 包，包含系统核心逻辑
│   ├── __init__.py                   # 标记为 Python 包
│   │
│   ├── core/                         # 核心数据模型、工具和抽象
│   │   ├── __init__.py
│   │   ├── models.py                 # 定义 Job, Task, Worker, Result 等数据模型 (Pydantic 兼容)
│   │   ├── exceptions.py             # 自定义异常
│   │   ├── constants.py              # 全局常量、枚举等
│   │   └── utils.py                  # 通用工具函数 (如日志配置、ID生成、配置加载)
│   │
│   ├── comm/                         # 通信层 (Master-Client HTTP/WS, Master-Worker RPC/WS)
│   │   ├── __init__.py
│   │   ├── http_schemas.py           # 定义 HTTP 请求和响应的数据模型 (例如 Pydantic models)
│   │   ├── ws_protocol.py            # 定义 WebSocket 消息类型和协议 (如消息体结构、事件类型)
│   │   ├── master_worker_rpc/        # Master-Worker 间通信协议 (推荐 gRPC 或 ZeroMQ，更高效稳定)
│   │   │   ├── __init__.py
│   │   │   ├── lunaris_rpc.proto     # gRPC 定义文件 (如果使用 gRPC)
│   │   │   ├── lunaris_rpc_pb2.py    # gRPC 编译生成
│   │   │   └── lunaris_rpc_pb2_grpc.py # gRPC 编译生成
│   │   ├── master_rpc_service.py     # Master 端用于 Worker 通信的 RPC 服务实现
│   │   ├── worker_rpc_client.py      # Worker 端用于 Master 通信的 RPC 客户端
│   │   └── heartbeat.py              # 心跳机制 (Worker向Master发送，可基于WS或RPC)
│   │
│   ├── master/                       # Master 节点的核心逻辑
│   │   ├── __init__.py
│   │   ├── web_app.py                # FastAPI/Flask/Aiohttp 应用入口，定义 HTTP API 和 WebSocket 路由
│   │   ├── coordinator.py            # 核心协调器，管理整个系统生命周期，整合各管理器
│   │   ├── scheduler.py              # 任务调度器，决定任务分配策略 (如负载均衡，亲和性)
│   │   ├── worker_manager.py         # 管理 Worker 的注册、心跳、状态、资源、分配任务
│   │   ├── job_manager.py            # 管理 Job 的创建、提交、状态跟踪、结果收集和推送 (通过WebSocket)
│   │   ├── persistence.py            # Master 状态持久化 (例如数据库连接、ORM操作，如 SQLAlchemy)
│   │   ├── api_routes/               # HTTP API 路由定义
│   │   │   ├── __init__.py
│   │   │   ├── jobs.py               # 任务相关的 API (提交、查询)
│   │   │   └── workers.py            # Worker 相关的 API (查询 Worker 列表)
│   │   └── ws_handlers.py            # WebSocket 事件处理逻辑 (如 Client 连接、Worker 状态更新推送)
│   │
│   ├── worker/                       # Worker 节点的核心逻辑
│   │   ├── __init__.py
│   │   ├── app.py                    # Worker 应用程序的入口点和主循环
│   │   ├── agent.py                  # Worker 代理，负责与 Master RPC 客户端通信 (注册、获取任务、汇报结果)
│   │   ├── task_executor.py          # 任务执行器，负责调用 Lua 运行时执行任务
│   │   └── resource_monitor.py       # 监控 Worker 自身资源使用情况 (CPU, 内存, 磁盘)
│   │
│   ├── client/                       # Client 端的 Python API 接口 (方便其他 Python 应用集成)
│   │   ├── __init__.py
│   │   ├── http_client.py            # 封装 HTTP 请求到 Master API
│   │   ├── ws_client.py              # 封装 WebSocket 连接到 Master (接收实时更新)
│   │   └── api.py                    # 提供给外部调用的统一 Python 客户端 API (提交任务, 查询状态, 监听更新)
│   │
│   ├── lua_runtime/                  # Lua 运行时集成层
│   │   ├── __init__.py
│   │   ├── engine.py                 # Python 与 Lua 交互的核心接口 (例如使用 `lupa` 库)
│   │   ├── lua_api.py                # Python 函数暴露给 Lua 脚本的接口定义 (例如 `lunaris.log()`, `lunaris.get_param()`, `lunaris.emit_progress()`)
│   │   ├── bundled_libs/             # 系统内部使用的 Lua 辅助库 (非用户任务逻辑)
│   │   │   ├── __init__.lua          # Lua 库的入口，用于 require 其他内部模块
│   │   │   ├── logging.lua           # Lua 任务中的日志记录辅助函数
│   │   │   └── sandbox.lua           # Lua 沙箱环境配置 (限制 Lua 脚本权限和可访问资源)
│   │   └── scripts/                  # Worker 在执行用户 Lua 任务前可能需要加载的辅助 Lua 脚本
│   │       └── bootstrap.lua         # 用于初始化 Lua 环境和加载 `lua_api.lua`
│   │
│   ├── cli/                          # 命令行接口 (可同时作为 Client 的一个实现)
│   │   ├── __init__.py
│   │   ├── main.py                   # CLI 入口点 (例如使用 `click` 或 `Typer`)
│   │   └── commands.py               # 定义 CLI 子命令 (如 `lunaris master start`, `lunaris worker start`, `lunaris job submit`, `lunaris job status`)
│   │
│   └── config/                       # 系统默认配置 (代码内部使用)
│       ├── __init__.py
│       ├── default.py                # 默认配置值
│       └── schema.py                 # 配置验证 (例如使用 `Pydantic` 或 `ConfigDict`)
│
├── tasks/                            # 用户自定义的 Lua 任务脚本目录
│   ├── example_task.lua              # 一个示例 Lua 任务脚本
│   ├── data_processing.lua           # 另一个任务脚本
│   └── common_lua_modules/           # 用户自定义的 Lua 模块，可供任务脚本 require
│       └── my_helpers.lua
│
├── config/                           # 部署相关的配置文件（例如，不同环境的配置）
│   ├── master_config.yaml            # Master 节点专有配置 (HTTP/WS 端口, RPC 端口, 数据库连接等)
│   ├── worker_config.yaml            # Worker 节点专有配置 (Master RPC 地址, 并发数等)
│   └── log_config.ini                # 日志配置
│
├── logs/                             # 运行时日志目录
│   ├── master.log
│   ├── worker.log
│   └── client.log
│
├── data/                             # 运行时数据目录 (可选，用于本地持久化或临时文件)
│   └── master_state.db               # 例如 SQLite 数据库文件
│
├── tests/                            # 测试目录
│   ├── unit/
│   │   ├── test_master_web_api.py    # 针对 Master 的 HTTP/WS API 测试
│   │   ├── test_master_core.py       # 针对 Master 核心逻辑的测试
│   │   ├── test_worker.py
│   │   ├── test_client.py
│   │   └── test_lua_runtime.py
│   ├── integration/
│   │   └── test_full_flow.py         # 测试 Client-Master-Worker 完整流程 (包括 HTTP/WS 交互)
│   └── conftest.py
│
├── docs/                             # 文档目录
│   ├── index.md
│   ├── installation.md
│   ├── usage.md
│   ├── architecture.md               # 专门介绍 C-M-W 架构和 Web Master
│   ├── client_api.md                 # 客户端 Python API 文档
│   ├── rest_api_spec.md              # Master 的 RESTful API 规范 (或 OpenAPI/Swagger JSON)
│   ├── websocket_protocol.md         # WebSocket 协议文档
│   └── lua_api.md                    # Lua 任务中可用的 Python 暴露接口文档
│
├── examples/                         # 示例项目和使用案例
│   ├── simple_web_client/            # 演示如何通过 HTTP/WS 与 Master 交互
│   │   ├── submit_script.py          # 使用 `lunaris.client.api` 提交任务的 Python 脚本
│   │   ├── listen_status.py          # 监听 WebSocket 实时状态更新的 Python 脚本
│   │   └── hello_world_task.lua      # 对应的 Lua 任务
│   ├── web_dashboard/                # 简单的 Web 前端示例 (可选)
│   │   ├── index.html
│   │   ├── script.js
│   │   └── style.css
│   └── complex_workflow/
│       ├── workflow_definition.json
│       └── task_step_1.lua
│
├── scripts/                          # 辅助脚本 (部署、启动、监控等)
│   ├── start_master.sh               # 启动 Master Web 服务和 RPC 服务
│   ├── start_worker.sh
│   ├── deploy.py
│   └── health_check.py
│
├── requirements.txt                  # Python 依赖 (例如 FastAPI/uvicorn, websockets, grpcio, Pydantic, SQLAlchemy)
├── setup.py                          # 项目安装配置 (如果作为可安装包)
├── pyproject.toml                    # 现代 Python 项目配置 (替代 setup.py)
├── README.md                         # 项目说明
├── LICENSE                           # 许可证文件
└── .gitignore                        # Git 忽略文件
