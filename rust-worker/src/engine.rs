/**
 * WASM 执行引擎模块
 *
 * 基于 wasmtime 的 WASM 执行引擎，提供高并发的 WASM 任务执行能力。
 *
 * 主要组件：
 *   - WasmResult: WASM 执行结果结构体
 *   - Runner: 任务执行器，管理并发和资源限制
 *   - run_wasm: WASM 执行核心函数
 *
 * 特性：
 *   - 异步执行：使用 tokio spawn_blocking 避免阻塞
 *   - 并发控制：基于信号量的最大并发数限制
 *   - 资源限制：燃料、内存、模块大小三重限制
 *   - 宿主能力：支持可扩展的宿主功能
 *
 * 注入的环境变量：
 *   - LUNARIS_TASK_ID: 当前任务 ID
 *   - LUNARIS_WORKER_VERSION: Worker 版本号
 *   - LUNARIS_HOST_CAPABILITIES: 启用的宿主能力（JSON 数组）
 */
use anyhow::{anyhow, Result};
use serde_json::{from_str, json, Value};
use std::{
    collections::{HashMap, HashSet},
    sync::Arc,
};
use tokio::sync::{mpsc, Semaphore};
use wasmtime::*;
use wasmtime_wasi::{p1::WasiP1Ctx, p2::pipe::MemoryOutputPipe, WasiCtx};

use crate::capabilities::{CapabilityHostState, CapabilityRegistry};
use crate::proto::{common::ExecutionLimits, worker};

// 注入到 WASI 环境的变量名
const INJECTED_TASK_ID_ENV: &str = "LUNARIS_TASK_ID";
const INJECTED_WORKER_VERSION_ENV: &str = "LUNARIS_WORKER_VERSION";
const INJECTED_HOST_CAPABILITIES_ENV: &str = "LUNARIS_HOST_CAPABILITIES";
// Worker 版本号（从 Cargo.toml 读取）
const WORKER_VERSION: &str = env!("CARGO_PKG_VERSION");

/// WASM 执行结果
///
/// 包含执行的输出、耗时和状态。
///
/// 字段说明：
///   - result: 函数返回值（JSON 字符串）
///   - stdout: 标准输出内容
///   - stderr: 标准错误输出内容
///   - time: 执行耗时（毫秒）
///   - succeeded: 是否执行成功
#[derive(Debug, Clone)]
pub struct WasmResult {
    pub result: String,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub time: f64,
    pub succeeded: bool,
}

/// 任务执行器
///
/// 管理 WASM 任务的并发执行，提供资源限制和能力系统支持。
///
/// 字段说明：
///   - wasm_engine: wasmtime 编译引擎
///   - result_tx: 结果发送通道
///   - concurrency: 并发控制信号量
///   - default_limits: 默认资源限制
///   - max_limits: 最大资源限制（安全边界）
pub struct Runner {
    wasm_engine: Engine,
    result_tx: mpsc::Sender<(WasmResult, u64, u32)>,
    concurrency: Arc<Semaphore>, // 用信号量控制最大并发数
    default_limits: ExecutionLimits,
    max_limits: ExecutionLimits,
}

impl Runner {
    #[allow(unused)]
    pub fn new<F>(max_workers: usize, report_callback: F) -> Self
    where
        F: Fn(WasmResult, u64) + Send + Sync + 'static,
    {
        let (tx, mut rx) = mpsc::channel(100);
        let report_callback = Arc::new(report_callback);
        let semaphore = Arc::new(Semaphore::new(max_workers)); // 控制最多并行任务数

        // Listener task: 异步监听结果并调用回调
        let callback = Arc::clone(&report_callback);
        tokio::spawn(async move {
            while let Some((result, task_id, _attempt)) = rx.recv().await {
                callback(result, task_id);
            }
        });
        let mut config = Config::new();
        config.consume_fuel(true);
        let engine = Engine::new(&config).expect("failed to create wasmtime engine");

        Self {
            wasm_engine: engine,
            result_tx: tx,
            concurrency: semaphore,
            default_limits: ExecutionLimits::default(),
            max_limits: ExecutionLimits::default(),
        }
    }

    pub fn new_with_channel(
        max_workers: usize,
        result_tx: mpsc::Sender<(WasmResult, u64, u32)>,
        default_limits: ExecutionLimits,
        max_limits: ExecutionLimits,
    ) -> Self {
        let semaphore = Arc::new(Semaphore::new(max_workers));
        let mut config = Config::new();
        config.consume_fuel(true);

        let engine = Engine::new(&config).expect("failed to create wasmtime engine");

        Self {
            wasm_engine: engine,
            result_tx,
            concurrency: semaphore,
            default_limits,
            max_limits,
        }
    }

    pub async fn submit(&self, task: worker::Task) -> Result<()> {
        let code = task.wasm_module;
        let args_json = task.args;
        let entry = task.entry;
        let task_id = task.task_id;
        let attempt = task.attempt;
        let host_capabilities = task
            .host_capabilities
            .map(|capabilities| capabilities.items)
            .unwrap_or_default();
        let mut wasi_env: HashMap<String, String> = HashMap::new();
        let mut wasi_args: Vec<String> = vec![];
        let limits = clamp_limits(
            task.execution_limits.as_ref(),
            &self.default_limits,
            &self.max_limits,
        );
        if let Some(wasi_env_cfg) = task.wasi_env {
            wasi_env = wasi_env_cfg.env;
            wasi_args = wasi_env_cfg.args;
        }
        let engine = self.wasm_engine.clone();
        let tx = self.result_tx.clone();
        let _permit = self.concurrency.clone().acquire_owned().await?; // 获取信号量许可

        // 提交到阻塞线程池执行
        tokio::task::spawn_blocking(move || {
            match run_wasm(
                &engine,
                &code,
                &args_json,
                &entry,
                task_id,
                &wasi_env,
                &wasi_args,
                &limits,
                &host_capabilities,
            ) {
                Ok(result) => {
                    // 使用当前运行时发送结果
                    if let Err(e) = tx.blocking_send((result, task_id, attempt)) {
                        eprintln!("Failed to send result: {}", e);
                    }
                }
                Err(e) => {
                    let err_result = WasmResult {
                        result: String::new(),
                        stdout: vec![],
                        stderr: format!("{e:?}").as_bytes().to_vec(),
                        time: 0.0,
                        succeeded: false,
                    };
                    if let Err(e) = tx.blocking_send((err_result, task_id, attempt)) {
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
    task_id: u64,
    env: &HashMap<String, String>,
    args: &Vec<String>,
    limits: &ExecutionLimits,
    host_capabilities: &[String],
) -> Result<WasmResult> {
    if limits.max_module_bytes > 0 && code.len() as u64 > limits.max_module_bytes {
        return Err(anyhow!(
            "Wasm module too large: {} > {}",
            code.len(),
            limits.max_module_bytes
        ));
    }

    let module = Module::new(wasm_engine, code)?;
    let mut linker = Linker::new(wasm_engine);
    wasmtime_wasi::p1::add_to_linker_sync(&mut linker, |s: &mut HostState| &mut s.wasi)?;

    // Register enabled capabilities
    let enabled_set: HashSet<String> = host_capabilities.iter().cloned().collect();
    let registry = CapabilityRegistry::new();
    registry.register_capabilities(&mut linker, &enabled_set)?;

    let stdout = MemoryOutputPipe::new(512);
    let stderr = MemoryOutputPipe::new(512);
    let mut wasi_env = env.clone();
    wasi_env.insert(INJECTED_TASK_ID_ENV.to_string(), task_id.to_string());
    wasi_env.insert(
        INJECTED_WORKER_VERSION_ENV.to_string(),
        WORKER_VERSION.to_string(),
    );
    wasi_env.insert(
        INJECTED_HOST_CAPABILITIES_ENV.to_string(),
        serde_json::to_string(host_capabilities)?,
    );

    let wasi = WasiCtx::builder()
        .stdout(stdout.clone())
        .stderr(stderr.clone())
        .envs(
            &wasi_env
                .iter()
                .map(|(k, v)| (k.as_str(), v.as_str()))
                .collect::<Vec<_>>(),
        )
        .args(args)
        .build_p1();
    let mut store = Store::new(
        wasm_engine,
        HostState {
            wasi,
            limits: build_store_limits(limits),
            enabled_capabilities: host_capabilities.iter().cloned().collect(),
        },
    );
    store.limiter(|state| &mut state.limits);
    if limits.max_fuel > 0 {
        store.set_fuel(limits.max_fuel)?;
    } else {
        store.set_fuel(u64::MAX)?;
    }
    define_env_memory_if_imported(&module, &mut linker, &mut store, limits)?;

    let instance = linker.instantiate(&mut store, &module)?;
    initialize_guest_if_present(&instance, &mut store)?;

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

    // 按函数签名动态构造结果槽，避免硬编码返回值类型导致 call 行为不稳定。
    let func_ty = func.ty(&store);
    let mut results: Vec<Val> = func_ty
        .results()
        .map(default_val_for_type)
        .collect::<Result<Vec<_>>>()?;

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

fn initialize_guest_if_present(instance: &Instance, store: &mut Store<HostState>) -> Result<()> {
    let Some(initialize) = instance.get_func(&mut *store, "_initialize") else {
        return Ok(());
    };

    let initialize_ty = initialize.ty(&mut *store);
    if initialize_ty.params().len() != 0 || initialize_ty.results().len() != 0 {
        return Err(anyhow!(
            "Function '_initialize' must have signature () -> ()"
        ));
    }

    let mut results = [];
    initialize.call(store, &[], &mut results)?;
    Ok(())
}

fn define_env_memory_if_imported(
    module: &Module,
    linker: &mut Linker<HostState>,
    store: &mut Store<HostState>,
    limits: &ExecutionLimits,
) -> Result<()> {
    let mut imported_memory = None;
    for import in module.imports() {
        if import.module() == "env" && import.name() == "memory" {
            if let ExternType::Memory(memory_ty) = import.ty() {
                imported_memory = Some(memory_ty);
            }
            break;
        }
    }

    let Some(memory_ty) = imported_memory else {
        return Ok(());
    };

    let minimum_bytes = memory_ty
        .minimum()
        .checked_mul(65_536)
        .ok_or_else(|| anyhow!("imported env::memory minimum is too large"))?;

    if limits.max_memory_bytes > 0 && minimum_bytes > limits.max_memory_bytes {
        return Err(anyhow!(
            "imported env::memory minimum size of {} pages exceeds memory limits",
            memory_ty.minimum()
        ));
    }

    let memory = Memory::new(&mut *store, memory_ty)?;
    linker.define(&mut *store, "env", "memory", memory)?;
    Ok(())
}

struct HostState {
    wasi: WasiP1Ctx,
    limits: StoreLimits,
    enabled_capabilities: HashSet<String>,
}

impl CapabilityHostState for HostState {
    fn enabled_capabilities(&self) -> &HashSet<String> {
        &self.enabled_capabilities
    }
}

fn build_store_limits(limits: &ExecutionLimits) -> StoreLimits {
    let builder = if limits.max_memory_bytes > 0 {
        StoreLimitsBuilder::new().memory_size(limits.max_memory_bytes as usize)
    } else {
        StoreLimitsBuilder::new()
    };
    builder.build()
}

fn clamp_limits(
    requested: Option<&ExecutionLimits>,
    defaults: &ExecutionLimits,
    maximums: &ExecutionLimits,
) -> ExecutionLimits {
    let requested = requested.cloned().unwrap_or_default();
    ExecutionLimits {
        max_fuel: resolve_limit(requested.max_fuel, defaults.max_fuel, maximums.max_fuel),
        max_memory_bytes: resolve_limit(
            requested.max_memory_bytes,
            defaults.max_memory_bytes,
            maximums.max_memory_bytes,
        ),
        max_module_bytes: resolve_limit(
            requested.max_module_bytes,
            defaults.max_module_bytes,
            maximums.max_module_bytes,
        ),
    }
}

fn resolve_limit(requested: u64, default: u64, maximum: u64) -> u64 {
    let effective = if requested > 0 { requested } else { default };
    if maximum > 0 && (effective == 0 || effective > maximum) {
        maximum
    } else {
        effective
    }
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

fn default_val_for_type(val_type: ValType) -> Result<Val> {
    match val_type {
        ValType::I32 => Ok(Val::I32(0)),
        ValType::I64 => Ok(Val::I64(0)),
        ValType::F32 => Ok(Val::F32(0)),
        ValType::F64 => Ok(Val::F64(0)),
        ValType::V128 => Ok(Val::V128(0.into())),
        other => Err(anyhow!("Unsupported result type: {:?}", other)),
    }
}

#[cfg(test)]
mod tests {
    use super::run_wasm;
    use crate::proto::common::ExecutionLimits;
    use std::{
        collections::HashMap,
        fs,
        path::PathBuf,
        process::Command,
        time::{SystemTime, UNIX_EPOCH},
    };
    use wasmtime::{Config, Engine};

    const WASI_P1_STDIO_ENV_ARGS: &str = r#"
#[no_mangle]
pub extern "C" fn wmain() -> i32 {
    let env_value = std::env::var("LUNARIS_WASI_P1").unwrap_or_else(|_| "missing".to_string());
    let arg_value = std::env::args().nth(1).unwrap_or_else(|| "missing".to_string());

    println!("stdout env={env_value} arg={arg_value}");
    eprintln!("stderr env={env_value} arg={arg_value}");

    if env_value == "preview1" && arg_value == "alpha" {
        42
    } else {
        -1
    }
}
"#;

    const WASI_P1_NO_PREOPEN_FS: &str = r#"
#[no_mangle]
pub extern "C" fn wmain() -> i32 {
    match std::fs::read_to_string("/workspace/input.txt") {
        Ok(_) => 1,
        Err(err) => {
            eprintln!("fs_error={err}");
            0
        }
    }
}
"#;

    const WASI_P1_INJECTED_ENV: &str = r#"
#[no_mangle]
pub extern "C" fn wmain() -> i32 {
    let task_id = std::env::var("LUNARIS_TASK_ID").unwrap_or_else(|_| "missing".to_string());
    let worker_version = std::env::var("LUNARIS_WORKER_VERSION").unwrap_or_else(|_| "missing".to_string());
    let host_capabilities = std::env::var("LUNARIS_HOST_CAPABILITIES").unwrap_or_else(|_| "missing".to_string());

    println!("task_id={task_id}");
    println!("worker_version={worker_version}");
    println!("host_capabilities={host_capabilities}");

    if task_id == "42"
        && worker_version == env!("CARGO_PKG_VERSION")
        && host_capabilities == "[\"simd\"]"
    {
        7
    } else {
        -1
    }
}
"#;

    const REACTOR_INITIALIZE_WAT: &str = r#"
(module
  (global $ready (mut i32) (i32.const 0))
  (func (export "_initialize")
    i32.const 1
    global.set $ready)
  (func (export "wmain") (result i32)
    global.get $ready))
"#;

    const IMPORTED_ENV_MEMORY_WAT: &str = r#"
(module
  (import "env" "memory" (memory 1))
  (func (export "wmain") (result i32)
    i32.const 42))
"#;

    const IMPORTED_ENV_MEMORY_TOO_LARGE_WAT: &str = r#"
(module
  (import "env" "memory" (memory 300))
  (func (export "wmain") (result i32)
    i32.const 1))
"#;

    #[test]
    fn supports_stdio_env_and_args() {
        let wasm = compile_wasi_p1_rust(WASI_P1_STDIO_ENV_ARGS);
        let engine = test_engine();
        let mut env = HashMap::new();
        env.insert("LUNARIS_WASI_P1".to_string(), "preview1".to_string());
        let args = vec!["lunaris-test".to_string(), "alpha".to_string()];
        let limits = test_limits();

        let result = run_wasm(&engine, &wasm, "[]", "wmain", 1, &env, &args, &limits, &[])
            .expect("run_wasm should succeed");

        assert!(result.succeeded);
        assert_eq!(result.result, "42");
        assert!(String::from_utf8_lossy(&result.stdout).contains("stdout env=preview1 arg=alpha"));
        assert!(String::from_utf8_lossy(&result.stderr).contains("stderr env=preview1 arg=alpha"));
    }

    #[test]
    fn filesystem_access_is_not_exposed_without_preopens() {
        let wasm = compile_wasi_p1_rust(WASI_P1_NO_PREOPEN_FS);
        let engine = test_engine();
        let limits = test_limits();

        let result = run_wasm(
            &engine,
            &wasm,
            "[]",
            "wmain",
            1,
            &HashMap::new(),
            &vec!["lunaris-test".to_string()],
            &limits,
            &[],
        )
        .expect("run_wasm should succeed");

        assert!(result.succeeded);
        assert_eq!(result.result, "0");
        assert!(String::from_utf8_lossy(&result.stderr).contains("fs_error="));
    }

    #[test]
    fn injects_task_metadata_into_wasi_env() {
        let wasm = compile_wasi_p1_rust(WASI_P1_INJECTED_ENV);
        let engine = test_engine();
        let limits = test_limits();

        let result = run_wasm(
            &engine,
            &wasm,
            "[]",
            "wmain",
            42,
            &HashMap::new(),
            &vec!["lunaris-test".to_string()],
            &limits,
            &["simd".to_string()],
        )
        .expect("run_wasm should succeed");

        assert!(result.succeeded);
        assert_eq!(result.result, "7");
        let stdout = String::from_utf8_lossy(&result.stdout);
        assert!(stdout.contains("task_id=42"));
        assert!(stdout.contains(&format!("worker_version={}", env!("CARGO_PKG_VERSION"))));
        assert!(stdout.contains("host_capabilities=[\"simd\"]"));
    }

    #[test]
    fn calls_initialize_before_entry_when_present() {
        let engine = test_engine();
        let limits = test_limits();

        let result = run_wasm(
            &engine,
            REACTOR_INITIALIZE_WAT.as_bytes(),
            "[]",
            "wmain",
            1,
            &HashMap::new(),
            &vec![],
            &limits,
            &[],
        )
        .expect("run_wasm should succeed");

        assert!(result.succeeded);
        assert_eq!(result.result, "1");
    }

    #[test]
    fn supports_modules_that_import_env_memory() {
        let engine = test_engine();
        let limits = test_limits();

        let result = run_wasm(
            &engine,
            IMPORTED_ENV_MEMORY_WAT.as_bytes(),
            "[]",
            "wmain",
            1,
            &HashMap::new(),
            &vec![],
            &limits,
            &[],
        )
        .expect("run_wasm should succeed");

        assert!(result.succeeded);
        assert_eq!(result.result, "42");
    }

    #[test]
    fn rejects_imported_env_memory_that_exceeds_limits() {
        let engine = test_engine();
        let limits = ExecutionLimits {
            max_fuel: 1_000_000,
            max_memory_bytes: 16 * 1024 * 1024,
            max_module_bytes: 4 * 1024 * 1024,
        };

        let error = run_wasm(
            &engine,
            IMPORTED_ENV_MEMORY_TOO_LARGE_WAT.as_bytes(),
            "[]",
            "wmain",
            1,
            &HashMap::new(),
            &vec![],
            &limits,
            &[],
        )
        .expect_err("run_wasm should reject oversized imported memory");

        assert!(error
            .to_string()
            .contains("imported env::memory minimum size of 300 pages exceeds memory limits"));
    }

    #[test]
    fn unlimited_tasks_still_run_when_fuel_metering_is_enabled() {
        let wasm = compile_wasi_p1_rust(WASI_P1_STDIO_ENV_ARGS);
        let engine = test_engine();
        let mut env = HashMap::new();
        env.insert("LUNARIS_WASI_P1".to_string(), "preview1".to_string());
        let args = vec!["lunaris-test".to_string(), "alpha".to_string()];
        let limits = ExecutionLimits {
            max_fuel: 0,
            max_memory_bytes: 16 * 1024 * 1024,
            max_module_bytes: 4 * 1024 * 1024,
        };

        let result = run_wasm(&engine, &wasm, "[]", "wmain", 1, &env, &args, &limits, &[])
            .expect("run_wasm should succeed without an explicit fuel limit");

        assert!(result.succeeded);
        assert_eq!(result.result, "42");
    }

    fn test_engine() -> Engine {
        let mut config = Config::new();
        config.consume_fuel(true);
        Engine::new(&config).expect("failed to create wasmtime engine")
    }

    fn test_limits() -> ExecutionLimits {
        ExecutionLimits {
            max_fuel: 1_000_000,
            max_memory_bytes: 16 * 1024 * 1024,
            max_module_bytes: 4 * 1024 * 1024,
        }
    }

    fn compile_wasi_p1_rust(source: &str) -> Vec<u8> {
        let rustc = std::env::var("RUSTC").unwrap_or_else(|_| "rustc".to_string());
        let mut root = std::env::temp_dir();
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        root.push(format!("lunaris-rust-worker-wasi-p1-{unique}"));
        fs::create_dir_all(&root).expect("failed to create temp dir");

        let source_path = root.join("module.rs");
        let wasm_path = root.join("module.wasm");
        fs::write(&source_path, source).expect("failed to write rust source");

        let output = Command::new(&rustc)
            .args([
                source_path
                    .to_str()
                    .expect("temp source path should be valid utf-8"),
                "--crate-type",
                "cdylib",
                "--target",
                "wasm32-wasip1",
                "-O",
                "-o",
                wasm_path
                    .to_str()
                    .expect("temp wasm path should be valid utf-8"),
            ])
            .output()
            .expect("failed to invoke rustc");

        if !output.status.success() {
            panic!(
                "failed to compile wasi p1 module: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        let wasm = fs::read(&wasm_path).expect("failed to read compiled wasm module");
        cleanup_temp_dir(root);
        wasm
    }

    fn cleanup_temp_dir(path: PathBuf) {
        if let Err(err) = fs::remove_dir_all(&path) {
            eprintln!("failed to remove temp dir {}: {err}", path.display());
        }
    }
}
