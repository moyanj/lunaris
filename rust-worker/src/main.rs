use clap::Parser;

mod cli;
mod engine;
mod proto;

#[tokio::main]
async fn main() {
    let args = cli::Cli::parse();
}
