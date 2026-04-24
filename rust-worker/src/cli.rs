/**
 * 命令行参数解析模块
 *
 * 使用 clap 解析命令行参数，配置 Worker 的运行参数。
 *
 * 主要参数：
 *   - master: Master 节点地址
 *   - token: 认证令牌
 *   - name: Worker 名称
 *   - concurrency: 最大并发数
 *   - 资源限制：fuel、memory、module（默认值和最大值）
 *
 * 环境变量：
 *   - WORKER_TOKEN: 认证令牌（可选，默认 "1145"）
 */
use std::env;

use clap::Parser;

/// CLI 参数结构体
///
/// 定义 Worker 的所有命令行参数。
///
/// 字段说明：
///   - master: Master 节点的 WebSocket 地址（必填）
///   - name: Worker 名称（可选，默认自动生成）
///   - concurrency: 最大并发数（可选，默认 CPU 核心数）
///   - token: 认证令牌（可选，默认从环境变量 WORKER_TOKEN 读取）
///   - default_max_fuel: 默认燃料限制（0 表示无限制）
///   - default_max_memory_bytes: 默认内存限制（0 表示无限制）
///   - default_max_module_bytes: 默认模块大小限制（0 表示无限制）
///   - max_fuel: 最大燃料限制（0 表示无限制）
///   - max_memory_bytes: 最大内存限制（0 表示无限制）
///   - max_module_bytes: 最大模块大小限制（0 表示无限制）
#[derive(Parser)]
#[command(version, about, long_about = None)]
pub struct Cli {
    /// Master 节点地址
    #[arg(short, long)]
    pub master: String,

    /// Worker 名称
    #[arg(short, long)]
    pub name: Option<String>,

    /// 最大并发数
    #[arg(short, long)]
    pub concurrency: Option<usize>,

    /// 认证令牌
    #[arg(short, long, default_value_t = env::var("WORKER_TOKEN").unwrap_or("1145".to_string()))]
    pub token: String,

    /// 默认燃料限制（0 表示无限制）
    #[arg(long, default_value_t = 0)]
    pub default_max_fuel: u64,

    /// 默认内存限制（字节，0 表示无限制）
    #[arg(long, default_value_t = 0)]
    pub default_max_memory_bytes: usize,

    /// 默认模块大小限制（字节，0 表示无限制）
    #[arg(long, default_value_t = 0)]
    pub default_max_module_bytes: usize,

    /// 最大燃料限制（0 表示无限制）
    #[arg(long, default_value_t = 0)]
    pub max_fuel: u64,

    /// 最大内存限制（字节，0 表示无限制）
    #[arg(long, default_value_t = 0)]
    pub max_memory_bytes: usize,

    /// 最大模块大小限制（字节，0 表示无限制）
    #[arg(long, default_value_t = 0)]
    pub max_module_bytes: usize,
}
