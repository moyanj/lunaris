/**
 * Worker 核心模块
 *
 * 实现 Rust 工作节点的核心逻辑，包括：
 *   - WebSocket 连接管理
 *   - 节点注册和心跳
 *   - 任务接收和分发
 *   - 任务取消和 drain 模式
 *
 * 主要组件：
 *   - Worker: 工作节点结构体，管理整个生命周期
 *   - 心跳机制：每 10 秒发送心跳到 Master
 *   - 任务处理：接收任务并分发到 WASM 执行引擎
 *
 * 状态管理：
 *   - running: 运行状态标志
 *   - num_running: 当前运行任务数
 *   - drain_enabled: drain 模式标志
 *   - cancelled_tasks: 已取消任务集合
 */
use anyhow::Result;
use futures_util::{SinkExt, StreamExt};
use prost::Message as _;
use serde_json::Value;
use std::collections::HashSet;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{mpsc, Mutex};
use tokio::time::interval;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{error, info};

use crate::capabilities::CapabilityRegistry;
use crate::engine::{Runner, WasmResult};
use crate::proto::common::envelope::MessageType;
use crate::proto::{self, common, worker};

/// Worker 结构体
///
/// 表示一个工作节点，管理与 Master 的连接、任务执行和状态。
///
/// 字段说明：
///   - master_uri: Master 节点的 WebSocket 地址
///   - name: Worker 名称（用于日志和监控）
///   - token: 认证令牌
///   - max_concurrency: 最大并发数
///   - node_id: 节点 ID（注册后由 Master 分配）
///   - running: 运行状态（线程安全）
///   - num_running: 当前运行任务数（线程安全）
///   - drain_enabled: drain 模式标志（线程安全）
///   - cancelled_tasks: 已取消任务集合（线程安全）
///   - runner: WASM 执行引擎
///   - default_execution_limits: 默认资源限制
///   - max_execution_limits: 最大资源限制
pub struct Worker {
    master_uri: String,
    name: String,
    token: String,
    max_concurrency: usize,
    use_compress: bool,
    node_id: String,
    running: Arc<Mutex<bool>>,
    num_running: Arc<Mutex<usize>>,
    drain_enabled: Arc<Mutex<bool>>,
    cancelled_tasks: Arc<Mutex<HashSet<u64>>>,
    runner: Option<Runner>,
    default_execution_limits: common::ExecutionLimits,
    max_execution_limits: common::ExecutionLimits,
}

impl Worker {
    pub async fn new(
        master_uri: &str,
        token: &str,
        name: String,
        max_concurrency: usize,
        use_compress: bool,
        default_execution_limits: common::ExecutionLimits,
        max_execution_limits: common::ExecutionLimits,
    ) -> Result<Self> {
        Ok(Self {
            master_uri: master_uri.to_string(),
            name: name,
            token: token.to_string(),
            max_concurrency,
            use_compress,
            node_id: String::new(),
            running: Arc::new(Mutex::new(false)),
            num_running: Arc::new(Mutex::new(0)),
            drain_enabled: Arc::new(Mutex::new(false)),
            cancelled_tasks: Arc::new(Mutex::new(HashSet::new())),
            runner: None,
            default_execution_limits,
            max_execution_limits,
        })
    }

    async fn connect(
        &self,
    ) -> Result<(
        futures_util::stream::SplitSink<
            tokio_tungstenite::WebSocketStream<
                tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
            >,
            Message,
        >,
        futures_util::stream::SplitStream<
            tokio_tungstenite::WebSocketStream<
                tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
            >,
        >,
    )> {
        //let url = Url::parse(&self.master_uri)?;
        let (ws_stream, _) = connect_async(self.master_uri.clone()).await?;
        let (write, read) = ws_stream.split();
        Ok((write, read))
    }

    async fn register(
        &mut self,
        write: &mut futures_util::stream::SplitSink<
            tokio_tungstenite::WebSocketStream<
                tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
            >,
            Message,
        >,
    ) -> Result<()> {
        let worker_type = if self.use_compress {
            worker::node_registration::WorkerType::Standard
        } else {
            worker::node_registration::WorkerType::Mcu
        };

        let registration = worker::NodeRegistration {
            name: self.name.clone(),
            arch: std::env::consts::ARCH.to_string(),
            max_concurrency: self.max_concurrency as u32,
            memory_size: (sysinfo::System::new_all().total_memory() / 1024 / 1024) as u64,
            token: self.token.clone(),
            provided_capabilities: Some(common::HostCapabilities {
                items: CapabilityRegistry::new()
                    .available_names()
                    .iter()
                    .map(|s| s.to_string())
                    .collect(),
            }),
            r#type: worker_type as i32,
        };

        let bytes = proto::to_bytes(&registration.encode_to_vec(), MessageType::NodeRegistration, self.use_compress)?;
        write.send(Message::Binary(bytes.into())).await?;

        Ok(())
    }

    async fn heartbeat(
        &self,
        write: Arc<
            Mutex<
                futures_util::stream::SplitSink<
                    tokio_tungstenite::WebSocketStream<
                        tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
                    >,
                    Message,
                >,
            >,
        >,
    ) -> Result<()> {
        let mut interval = interval(Duration::from_secs(10));
        let node_id = self.node_id.clone();
        let num_running = Arc::clone(&self.num_running);
        let running = Arc::clone(&self.running);
        let max_concurrency = self.max_concurrency;
        let use_compress = self.use_compress;

        tokio::spawn(async move {
            while *running.lock().await {
                interval.tick().await;

                let current_tasks = *num_running.lock().await;
                let state = if current_tasks == max_concurrency {
                    worker::node_status::NodeState::Busy
                } else {
                    worker::node_status::NodeState::Idle
                };

                let status = worker::NodeStatus {
                    node_id: node_id.clone(),
                    status: state as i32,
                    current_task: current_tasks as u32,
                };

                if let Ok(bytes) = proto::to_bytes(&status.encode_to_vec(), MessageType::NodeStatus, use_compress)
                {
                    if let Ok(mut write_guard) = write.try_lock() {
                        let _ = write_guard.send(Message::Binary(bytes.into())).await;
                    }
                }
            }
        });

        Ok(())
    }

    #[allow(unused)]
    async fn report_result(
        &self,
        write: &mut futures_util::stream::SplitSink<
            tokio_tungstenite::WebSocketStream<
                tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
            >,
            Message,
        >,
        result: WasmResult,
        task_id: u64,
        attempt: u32,
    ) -> Result<()> {
        let task_result = common::TaskResult {
            task_id,
            result: result.result,
            stdout: result.stdout,
            stderr: result.stderr,
            time: result.time,
            succeeded: result.succeeded,
            attempt,
        };

        let bytes = proto::to_bytes(&task_result.encode_to_vec(), MessageType::TaskResult, self.use_compress)?;
        write.send(Message::Binary(bytes.into())).await?;

        Ok(())
    }

    async fn handle_task(
        &self,
        task: worker::Task,
        write: Arc<
            Mutex<
                futures_util::stream::SplitSink<
                    tokio_tungstenite::WebSocketStream<
                        tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
                    >,
                    Message,
                >,
            >,
        >,
    ) -> Result<()> {
        // drain 模式或已收到取消请求时，不再接受新任务，直接返回取消结果。
        if *self.drain_enabled.lock().await
            || self.cancelled_tasks.lock().await.contains(&task.task_id)
        {
            let result = WasmResult {
                result: String::new(),
                stdout: vec![],
                stderr: b"task cancelled".to_vec(),
                time: 0.0,
                succeeded: false,
            };
            let mut write_guard = write.lock().await;
            Self::report_result_static(&mut write_guard, result, task.task_id, task.attempt, self.use_compress)
                .await?;
            return Ok(());
        }

        let mut write_guard = write.lock().await;
        Self::report_task_accepted_static(
            &mut write_guard,
            task.task_id,
            self.node_id.clone(),
            task.attempt,
            self.use_compress,
        )
        .await?;
        drop(write_guard);

        if let Some(runner) = &self.runner {
            {
                let mut num_running = self.num_running.lock().await;
                *num_running += 1;
            }

            runner.submit(task).await?;
        }

        Ok(())
    }

    async fn handle_control_command(&self, command: worker::ControlCommand) -> Result<()> {
        match worker::control_command::CommandType::try_from(command.r#type) {
            Ok(worker::control_command::CommandType::Shutdown) => {
                *self.running.lock().await = false;
            }
            Ok(worker::control_command::CommandType::SetDrain) => {
                let enabled = parse_bool_flag(&command.data, "enabled");
                *self.drain_enabled.lock().await = enabled;
                info!("Drain mode set to {}", enabled);
            }
            Ok(worker::control_command::CommandType::CancelTask) => {
                if let Some(task_id) = parse_u64_flag(&command.data, "task_id") {
                    self.cancelled_tasks.lock().await.insert(task_id);
                    info!("Received cancel request for task {}", task_id);
                }
            }
            _ => {}
        }
        Ok(())
    }

    pub async fn run(&mut self) -> Result<()> {
        let (mut write, mut read) = self.connect().await?;
        *self.running.lock().await = true;
        // 注册节点
        info!("Registering node...");
        self.register(&mut write).await?;

        // 创建Runner
        let (result_tx, mut result_rx) = mpsc::channel(100);
        let runner = Runner::new_with_channel(
            self.max_concurrency,
            result_tx,
            self.default_execution_limits.clone(),
            self.max_execution_limits.clone(),
        );
        self.runner = Some(runner);

        // 等待注册响应
        if let Some(message) = read.next().await {
            let message = message?;
            if let Message::Binary(data) = message {
                let (proto_message, tp) = proto::from_bytes(&data)?;

                if let MessageType::ControlCommand = tp {
                    if let Ok(command) = worker::ControlCommand::decode(proto_message.as_ref()) {
                        if command.r#type == worker::control_command::CommandType::Shutdown as i32 {
                            error!("Cannot connect to master. Reason: {}", command.data);
                            return Ok(());
                        }
                    }
                } else if let MessageType::NodeRegistrationReply = tp {
                    if let Ok(registration_reply) =
                        worker::NodeRegistrationReply::decode(proto_message.as_ref())
                    {
                        self.node_id = registration_reply.node_id.clone();
                        info!("Registered with node_id: {}", self.node_id);
                    }
                }
            }
        }

        // 启动心跳
        let write_arc = Arc::new(Mutex::new(write));
        self.heartbeat(Arc::clone(&write_arc)).await?;

        // 启动结果报告任务
        let write_arc_clone = Arc::clone(&write_arc);
        let running_clone = Arc::clone(&self.running);
        let num_running_clone = Arc::clone(&self.num_running);
        let cancelled_tasks_clone = Arc::clone(&self.cancelled_tasks);
        let use_compress = self.use_compress;
        tokio::spawn(async move {
            while *running_clone.lock().await {
                if let Some((result, task_id, attempt)) = result_rx.recv().await {
                    // Rust worker 当前也采用 best-effort cancel：结果回传前再收敛一次终态。
                    let result = if cancelled_tasks_clone.lock().await.remove(&task_id) {
                        WasmResult {
                            result: String::new(),
                            stdout: result.stdout,
                            stderr: b"task cancelled".to_vec(),
                            time: result.time,
                            succeeded: false,
                        }
                    } else {
                        result
                    };
                    let mut write_guard = write_arc_clone.lock().await;
                    if let Err(e) =
                        Self::report_result_static(&mut write_guard, result, task_id, attempt, use_compress).await
                    {
                        error!("Failed to report result: {}", e);
                    }

                    // 减少运行任务计数
                    if let Ok(mut num_running) = num_running_clone.try_lock() {
                        *num_running = num_running.saturating_sub(1);
                    }
                }
            }
        });

        // 主消息处理循环
        while *self.running.lock().await {
            if let Some(message) = read.next().await {
                match message {
                    Ok(Message::Binary(data)) => {
                        if let Ok((proto_message, tp)) = proto::from_bytes(&data) {
                            match tp {
                                MessageType::Task => {
                                    if let Ok(task) = worker::Task::decode(proto_message.as_ref()) {
                                        if let Err(e) =
                                            self.handle_task(task, Arc::clone(&write_arc)).await
                                        {
                                            error!("Failed to handle task: {}", e);
                                        }
                                    }
                                }
                                MessageType::ControlCommand => {
                                    if let Ok(command) =
                                        worker::ControlCommand::decode(proto_message.as_ref())
                                    {
                                        if let Err(e) = self.handle_control_command(command).await {
                                            error!("Failed to handle control command: {}", e);
                                        }
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                    Ok(Message::Close(_)) => {
                        error!("Connection closed by master");
                        break;
                    }
                    Err(e) => {
                        error!("WebSocket error: {}", e);
                        break;
                    }
                    _ => {}
                }
            }
        }

        self.shutdown().await;
        Ok(())
    }

    async fn report_result_static(
        write: &mut futures_util::stream::SplitSink<
            tokio_tungstenite::WebSocketStream<
                tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
            >,
            Message,
        >,
        result: WasmResult,
        task_id: u64,
        attempt: u32,
        use_compress: bool,
    ) -> Result<()> {
        let task_result = common::TaskResult {
            task_id,
            result: result.result,
            stdout: result.stdout,
            stderr: result.stderr,
            time: result.time,
            succeeded: result.succeeded,
            attempt,
        };

        let bytes = proto::to_bytes(&task_result.encode_to_vec(), MessageType::TaskResult, use_compress)?;
        write.send(Message::Binary(bytes.into())).await?;
        Ok(())
    }

    async fn report_task_accepted_static(
        write: &mut futures_util::stream::SplitSink<
            tokio_tungstenite::WebSocketStream<
                tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
            >,
            Message,
        >,
        task_id: u64,
        node_id: String,
        attempt: u32,
        use_compress: bool,
    ) -> Result<()> {
        let accepted = worker::TaskAccepted {
            task_id,
            node_id,
            attempt,
        };
        let bytes = proto::to_bytes(&accepted.encode_to_vec(), MessageType::TaskAccepted, use_compress)?;
        write.send(Message::Binary(bytes.into())).await?;
        Ok(())
    }

    async fn shutdown(&mut self) {
        *self.running.lock().await = false;

        // 发送注销消息
        if let Some(_runner) = self.runner.take() {
            // 等待runner关闭
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
}

fn parse_bool_flag(data: &str, key: &str) -> bool {
    serde_json::from_str::<Value>(data)
        .ok()
        .and_then(|value| value.get(key).and_then(|item| item.as_bool()))
        .unwrap_or(false)
}

fn parse_u64_flag(data: &str, key: &str) -> Option<u64> {
    serde_json::from_str::<Value>(data).ok().and_then(|value| {
        value
            .get(key)
            .and_then(|item| item.as_u64().or_else(|| item.as_str()?.parse().ok()))
    })
}
