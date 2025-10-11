use clap::Parser;
use tracing::info;

mod cli;
mod core;
mod engine;
mod proto;

use cli::Cli;
use core::Worker;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 初始化日志
    tracing_subscriber::fmt::init();

    let args = Cli::parse();

    info!("Starting Lunaris worker...");
    info!("Connecting to master: {}", args.master);
    info!("Worker name: {}", args.name.as_deref().unwrap_or("unknown"));
    info!("Max concurrency: {}", args.concurrency.unwrap_or(1));

    // 创建worker
    let mut worker = Worker::new(
        &args.master,
        &args.token,
        args.name.as_deref(),
        args.concurrency,
    )
    .await?;

    // 运行worker
    worker.run().await.unwrap();

    info!("Worker shutdown complete");
    Ok(())
}
