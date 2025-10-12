use anyhow::Result;
use futures_util::{SinkExt, StreamExt};
use prost::Message as _;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{Mutex, mpsc};
use tokio::time::interval;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{error, info};

use crate::engine::{Runner, WasmResult};
use crate::proto::common::envelope::MessageType;
use crate::proto::{self, common, worker};

pub struct Worker {
    master_uri: String,
    name: String,
    token: String,
    max_concurrency: usize,
    node_id: String,
    running: Arc<Mutex<bool>>,
    num_running: Arc<Mutex<usize>>,
    runner: Option<Runner>,
}

impl Worker {
    pub async fn new(
        master_uri: &str,
        token: &str,
        name: String,
        max_concurrency: usize,
    ) -> Result<Self> {
        Ok(Self {
            master_uri: master_uri.to_string(),
            name: name,
            token: token.to_string(),
            max_concurrency,
            node_id: String::new(),
            running: Arc::new(Mutex::new(false)),
            num_running: Arc::new(Mutex::new(0)),
            runner: None,
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
        let registration = worker::NodeRegistration {
            name: self.name.clone(),
            arch: std::env::consts::ARCH.to_string(),
            max_concurrency: self.max_concurrency as u32,
            memory_size: (sysinfo::System::new_all().total_memory() / 1024 / 1024) as u64,
            token: self.token.clone(),
        };

        let bytes = proto::to_bytes(&registration.encode_to_vec(), MessageType::NodeRegistration)?;
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

        tokio::spawn(async move {
            while *running.lock().await {
                interval.tick().await;

                let current_tasks = *num_running.lock().await;
                let state = if current_tasks == 0 {
                    worker::node_status::NodeState::Idle
                } else {
                    worker::node_status::NodeState::Busy
                };

                let status = worker::NodeStatus {
                    node_id: node_id.clone(),
                    status: state as i32,
                    current_task: current_tasks as u32,
                };

                if let Ok(bytes) = proto::to_bytes(&status.encode_to_vec(), MessageType::NodeStatus)
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
        task_id: String,
    ) -> Result<()> {
        let task_result = common::TaskResult {
            task_id,
            result: result.result,
            stdout: result.stdout,
            stderr: result.stderr,
            time: result.time,
            succeeded: result.succeeded,
        };

        let bytes = proto::to_bytes(&task_result.encode_to_vec(), MessageType::TaskResult)?;
        write.send(Message::Binary(bytes.into())).await?;

        Ok(())
    }

    async fn handle_task(&self, task: worker::Task) -> Result<()> {
        if let Some(runner) = &self.runner {
            {
                let mut num_running = self.num_running.lock().await;
                *num_running += 1;
            }

            runner.submit(task).await?;
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
        let (result_tx, mut result_rx) = mpsc::channel(1024);
        let runner = Runner::new_with_channel(self.max_concurrency, result_tx);
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
        tokio::spawn(async move {
            while *running_clone.lock().await {
                if let Some((result, task_id)) = result_rx.recv().await {
                    if let Ok(mut write_guard) = write_arc_clone.try_lock() {
                        if let Err(e) =
                            Self::report_result_static(&mut write_guard, result, task_id).await
                        {
                            error!("Failed to report result: {}", e);
                        }
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
                            if let MessageType::Task = tp {
                                if let Ok(task) = worker::Task::decode(proto_message.as_ref()) {
                                    if let Err(e) = self.handle_task(task).await {
                                        error!("Failed to handle task: {}", e);
                                    }
                                }
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
        task_id: String,
    ) -> Result<()> {
        let task_result = common::TaskResult {
            task_id,
            result: result.result,
            stdout: result.stdout,
            stderr: result.stderr,
            time: result.time,
            succeeded: result.succeeded,
        };

        let bytes = proto::to_bytes(&task_result.encode_to_vec(), MessageType::TaskResult)?;
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
