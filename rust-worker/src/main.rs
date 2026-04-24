/**
 * Lunaris Rust 工作节点入口
 *
 * 高性能 WASM 执行器，基于 wasmtime + tokio + mimalloc。
 * 通过 WebSocket 连接到 Master 节点，接收并执行 WASM 任务。
 *
 * 主要特性：
 *   - 异步执行：使用 tokio 运行时，支持高并发
 *   - 内存优化：使用 mimalloc 作为全局分配器
 *   - 资源限制：支持燃料、内存、模块大小三重限制
 *   - 能力系统：支持可扩展的宿主能力
 *
 * 启动流程：
 *   1. 初始化日志系统
 *   2. 解析命令行参数
 *   3. 创建 Worker 实例
 *   4. 连接到 Master 节点
 *   5. 开始接收和执行任务
 */
use clap::Parser;
use tracing::{error, info};

// 模块声明
mod capabilities;  // 宿主能力注册
mod cli;           // 命令行参数解析
mod core;          // Worker 核心逻辑
mod engine;        // WASM 执行引擎
mod proto;         // Protobuf 消息处理

use cli::Cli;
use core::Worker;
use proto::common::ExecutionLimits;

// 使用 mimalloc 作为全局内存分配器（性能优化）
#[global_allocator]
static ALLOC: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 初始化日志系统
    tracing_subscriber::fmt::init();

    // 解析命令行参数
    let args = Cli::parse();

    // 生成 Worker 名称（如果未指定）
    let name = args
        .name
        .map(|s| s.to_string())
        .unwrap_or_else(|| format!("worker-{}", hex::encode(rand::random::<[u8; 8]>())));
    // 获取并发数（如果未指定，使用 CPU 核心数）
    let concurrency = args.concurrency.unwrap_or(num_cpus::get());

    info!("Starting Lunaris worker...");
    info!("Connecting to master: {}", args.master);
    info!("Worker name: {}", name);
    info!("Max concurrency: {}", concurrency);
    info!("Compression: {}", if args.no_compress { "disabled" } else { "enabled" });

    // 创建 Worker 实例
    let mut worker = Worker::new(
        &args.master,
        &args.token,
        name,
        concurrency,
        !args.no_compress,
        // 默认资源限制
        ExecutionLimits {
            max_fuel: args.default_max_fuel,
            max_memory_bytes: args.default_max_memory_bytes as u64,
            max_module_bytes: args.default_max_module_bytes as u64,
        },
        // 最大资源限制（安全边界）
        ExecutionLimits {
            max_fuel: args.max_fuel,
            max_memory_bytes: args.max_memory_bytes as u64,
            max_module_bytes: args.max_module_bytes as u64,
        },
    )
    .await?;

    // 运行 Worker 主循环
    if let Err(e) = worker.run().await {
        error!("Worker shutdown failed: {}", e);
    }

    info!("Worker shutdown complete");
    Ok(())
}
