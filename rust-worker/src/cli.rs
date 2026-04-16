use std::env;

use clap::Parser;

#[derive(Parser)]
#[command(version, about, long_about = None)]
pub struct Cli {
    /// Master address
    #[arg(short, long)]
    pub master: String,

    /// Worker name
    #[arg(short, long)]
    pub name: Option<String>,

    /// Max concurrent tasks
    #[arg(short, long)]
    pub concurrency: Option<usize>,

    /// Worker token
    #[arg(short, long, default_value_t = env::var("WORKER_TOKEN").unwrap_or("1145".to_string()))]
    pub token: String,

    /// Default max fuel per task
    #[arg(long, default_value_t = 0)]
    pub default_max_fuel: u64,

    /// Default max memory in bytes per task
    #[arg(long, default_value_t = 0)]
    pub default_max_memory_bytes: usize,

    /// Default max wasm module bytes per task
    #[arg(long, default_value_t = 0)]
    pub default_max_module_bytes: usize,

    /// Absolute max fuel per task
    #[arg(long, default_value_t = 0)]
    pub max_fuel: u64,

    /// Absolute max memory in bytes per task
    #[arg(long, default_value_t = 0)]
    pub max_memory_bytes: usize,

    /// Absolute max wasm module bytes per task
    #[arg(long, default_value_t = 0)]
    pub max_module_bytes: usize,
}
