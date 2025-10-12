use anyhow::{Result, anyhow};
use serde_json::{Value, from_str, json};
use std::{collections::HashMap, sync::Arc};
use tokio::sync::{Semaphore, mpsc};
use wasmtime::*;
use wasmtime_wasi::{WasiCtx, p2::pipe::MemoryOutputPipe};

use crate::proto::worker;

pub struct WasmResult {
    pub result: String,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub time: f64,
    pub succeeded: bool,
}

pub struct Runner {
    wasm_engine: Engine,
    result_tx: mpsc::Sender<(WasmResult, String)>,
    concurrency: Arc<Semaphore>, // 用信号量控制最大并发数
}

impl Runner {
    #[allow(unused)]
    pub fn new<F>(max_workers: usize, report_callback: F) -> Self
    where
        F: Fn(WasmResult, String) + Send + Sync + 'static,
    {
        let (tx, mut rx) = mpsc::channel(100);
        let report_callback = Arc::new(report_callback);
        let semaphore = Arc::new(Semaphore::new(max_workers)); // 控制最多并行任务数

        // Listener task: 异步监听结果并调用回调
        let callback = Arc::clone(&report_callback);
        tokio::spawn(async move {
            while let Some((result, task_id)) = rx.recv().await {
                callback(result, task_id);
            }
        });

        Self {
            wasm_engine: Engine::default(),
            result_tx: tx,
            concurrency: semaphore,
        }
    }

    pub fn new_with_channel(
        max_workers: usize,
        result_tx: mpsc::Sender<(WasmResult, String)>,
    ) -> Self {
        let semaphore = Arc::new(Semaphore::new(max_workers));

        Self {
            wasm_engine: Engine::default(),
            result_tx,
            concurrency: semaphore,
        }
    }

    pub async fn submit(&self, task: worker::Task) -> Result<()> {
        let code = task.wasm_module;
        let args_json = task.args;
        let entry = task.entry;
        let task_id = task.task_id.clone();
        let mut wasi_env: HashMap<String, String> = HashMap::new();
        let mut wasi_args: Vec<String> = vec![];
        if let Some(wasi_env_cfg) = task.wasi_env {
            wasi_env = wasi_env_cfg.env;
            wasi_args = wasi_env_cfg.args;
        }
        let engine = self.wasm_engine.clone();
        let tx = self.result_tx.clone();
        let _permit = self.concurrency.clone().acquire_owned().await?; // 获取信号量许可

        // 提交到阻塞线程池执行
        tokio::task::spawn_blocking(move || {
            match run_wasm(&engine, &code, &args_json, &entry, &wasi_env, &wasi_args) {
                Ok(result) => {
                    // 使用当前运行时发送结果
                    if let Err(e) = tx.blocking_send((result, task_id)) {
                        eprintln!("Failed to send result: {}", e);
                    }
                }
                Err(e) => {
                    let err_result = WasmResult {
                        result: String::new(),
                        stdout: vec![],
                        stderr: e.to_string().as_bytes().to_vec(),
                        time: 0.0,
                        succeeded: false,
                    };
                    if let Err(e) = tx.blocking_send((err_result, task_id)) {
                        eprintln!("Failed to send error result: {}", e);
                    }
                }
            }
        });

        Ok(())
    }
}

fn run_wasm(
    wasm_engine: &Engine,
    code: &[u8],
    args_json: &str,
    entry: &str,
    env: &HashMap<String, String>,
    args: &Vec<String>,
) -> Result<WasmResult> {
    let module = Module::new(wasm_engine, code)?;
    let mut linker = Linker::new(wasm_engine);
    wasmtime_wasi::p1::add_to_linker_sync(&mut linker, |s| s)?;

    let stdout = MemoryOutputPipe::new(512);
    let stderr = MemoryOutputPipe::new(512);

    let wasi = WasiCtx::builder()
        .stdout(stdout.clone())
        .stderr(stderr.clone())
        .envs(
            &env.iter()
                .map(|(k, v)| (k.as_str(), v.as_str()))
                .collect::<Vec<_>>(),
        )
        .args(args)
        .build_p1();
    let mut store = Store::new(wasm_engine, wasi);

    let instance = linker.instantiate(&mut store, &module)?;

    // Parse JSON arguments
    let json_value: Value = from_str(args_json)?;
    let args_array = json_value
        .as_array()
        .ok_or_else(|| anyhow!("Args must be a JSON array"))?;

    // Convert JSON values to Wasm Val types
    let wasm_args: Result<Vec<Val>> = args_array
        .iter()
        .map(|value| {
            match value {
                Value::Number(n) => {
                    if let Some(i) = n.as_i64() {
                        if i >= i32::MIN as i64 && i <= i32::MAX as i64 {
                            Ok(Val::I32(i as i32))
                        } else {
                            Ok(Val::I64(i))
                        }
                    } else if let Some(f) = n.as_f64() {
                        // You might want to use F32 or F64 based on your needs
                        Ok(Val::F64(f.to_bits()))
                    } else {
                        Err(anyhow!("Unsupported number format"))
                    }
                }
                Value::Bool(b) => Ok(Val::I32(if *b { 1 } else { 0 })),
                Value::Null => Ok(Val::I32(0)),
                _ => Err(anyhow!("Unsupported JSON type in args")),
            }
        })
        .collect();
    let wasm_args = wasm_args?;

    let func = instance
        .get_func(&mut store, entry)
        .ok_or_else(|| anyhow!("Function '{}' not found", entry))?;

    let mut results = vec![Val::I32(0)]; // Adjust based on expected return type

    let start = std::time::Instant::now();
    func.call(&mut store, &wasm_args, &mut results)?;
    let time = start.elapsed().as_secs_f64() * 1000.0;

    // Convert result to string
    let result_str = serde_json::to_string(&wasm_results_to_json(&results))?;
    Ok(WasmResult {
        result: result_str,
        stdout: stdout.contents().to_vec(),
        stderr: stderr.contents().to_vec(),
        time,
        succeeded: true,
    })
}

fn wasm_results_to_json(results: &[Val]) -> Value {
    match results.len() {
        0 => Value::Null,
        1 => {
            // 单返回值
            match &results[0] {
                Val::I32(i) => json!(*i),
                Val::I64(i) => json!(*i),
                Val::F32(f) => json!(f64::from(*f)),
                Val::F64(f) => json!(*f),
                Val::V128(v) => json!(v.as_u128()),
                _ => json!("unsupported_type"),
            }
        }
        _ => {
            // 多返回值 - 转换为数组
            let values: Vec<Value> = results
                .iter()
                .map(|val| match val {
                    Val::I32(i) => json!(*i),
                    Val::I64(i) => json!(*i),
                    Val::F32(f) => json!(f64::from(*f)),
                    Val::F64(f) => json!(*f),
                    Val::V128(v) => json!(v.as_u128()),
                    _ => json!("unsupported_type"),
                })
                .collect();
            Value::Array(values)
        }
    }
}
