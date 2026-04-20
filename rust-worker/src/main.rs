use clap::Parser;
use tracing::{error, info};

mod capabilities;
mod cli;
mod core;
mod engine;
mod proto;

use cli::Cli;
use core::Worker;
use proto::common::ExecutionLimits;

#[global_allocator]
static ALLOC: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 初始化日志
    tracing_subscriber::fmt::init();

    let args = Cli::parse();

    let name = args
        .name
        .map(|s| s.to_string())
        .unwrap_or_else(|| format!("worker-{}", hex::encode(rand::random::<[u8; 8]>())));
    let concurrency = args.concurrency.unwrap_or(num_cpus::get());

    info!("Starting Lunaris worker...");
    info!("Connecting to master: {}", args.master);
    info!("Worker name: {}", name);
    info!("Max concurrency: {}", concurrency);

    // 创建worker
    let mut worker = Worker::new(
        &args.master,
        &args.token,
        name,
        concurrency,
        ExecutionLimits {
            max_fuel: args.default_max_fuel,
            max_memory_bytes: args.default_max_memory_bytes as u64,
            max_module_bytes: args.default_max_module_bytes as u64,
        },
        ExecutionLimits {
            max_fuel: args.max_fuel,
            max_memory_bytes: args.max_memory_bytes as u64,
            max_module_bytes: args.max_module_bytes as u64,
        },
    )
    .await?;

    // 运行worker
    if let Err(e) = worker.run().await {
        error!("Worker shutdown failed: {}", e);
    }

    info!("Worker shutdown complete");
    Ok(())
}
