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
}
