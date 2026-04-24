/**
 * Lunaris Rust Guest SDK
 *
 * 用于编译到 wasm32-wasip1 目标的 WASM 模块。
 * 提供任务上下文读取和宿主能力访问功能。
 *
 * 主要组件：
 *   - TaskContext: 任务上下文（任务 ID、Worker 版本、宿主能力）
 *   - context 模块: 环境变量读取函数
 *   - simd 模块: SIMD 能力的宿主函数导入
 *
 * 使用示例：
 *   ```rust
 *   use lunaris_wasm::{TaskContext, context, simd};
 *
 *   fn wmain(a: i32, b: i32) -> i32 {
 *       if let Ok(ctx) = TaskContext::current() {
 *           println!("task={}", ctx.task_id);
 *       }
 *
 *       if simd::is_available() {
 *           return simd::add_checked(a, b).unwrap_or(a + b);
 *       }
 *       a + b
 *   }
 *   ```
 */
pub const TASK_ID_ENV: &str = "LUNARIS_TASK_ID";
pub const WORKER_VERSION_ENV: &str = "LUNARIS_WORKER_VERSION";
pub const HOST_CAPABILITIES_ENV: &str = "LUNARIS_HOST_CAPABILITIES";

/// 上下文错误类型
///
/// 表示读取任务上下文时可能发生的错误。
///
/// 变体：
///   - MissingEnv: 缺少环境变量
///   - InvalidTaskId: 任务 ID 解析失败
///   - InvalidCapabilities: 能力 JSON 解析失败
#[derive(Debug)]
pub enum ContextError {
    MissingEnv(&'static str),
    InvalidTaskId(std::num::ParseIntError),
    InvalidCapabilities(serde_json::Error),
}

impl core::fmt::Display for ContextError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            Self::MissingEnv(name) => write!(f, "missing Lunaris env: {name}"),
            Self::InvalidTaskId(err) => write!(f, "invalid task id: {err}"),
            Self::InvalidCapabilities(err) => write!(f, "invalid host capabilities json: {err}"),
        }
    }
}

impl std::error::Error for ContextError {}

/// 任务上下文
///
/// 包含当前任务的元数据，从环境变量读取。
///
/// 字段：
///   - task_id: 任务 ID
///   - worker_version: Worker 版本号
///   - host_capabilities: 已启用的宿主能力列表
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskContext {
    pub task_id: u64,
    pub worker_version: String,
    pub host_capabilities: Vec<String>,
}

impl TaskContext {
    /// 获取当前任务上下文
    ///
    /// 从环境变量读取任务上下文信息。
    ///
    /// Returns:
    ///   - 成功：TaskContext
    ///   - 失败：ContextError
    pub fn current() -> Result<Self, ContextError> {
        Ok(Self {
            task_id: context::task_id()?,
            worker_version: context::worker_version()?,
            host_capabilities: context::host_capabilities()?,
        })
    }
}

/// 上下文读取函数模块
///
/// 提供从环境变量读取任务上下文的函数。
pub mod context {
    use super::{ContextError, HOST_CAPABILITIES_ENV, TASK_ID_ENV, WORKER_VERSION_ENV};

    /// 读取必需的环境变量
    ///
    /// 如果环境变量不存在，返回 MissingEnv 错误。
    fn env_required(name: &'static str) -> Result<String, ContextError> {
        std::env::var(name).map_err(|_| ContextError::MissingEnv(name))
    }

    /// 读取任务 ID
    ///
    /// 从 LUNARIS_TASK_ID 环境变量读取并解析为 u64。
    pub fn task_id() -> Result<u64, ContextError> {
        env_required(TASK_ID_ENV)?
            .parse::<u64>()
            .map_err(ContextError::InvalidTaskId)
    }

    /// 读取 Worker 版本
    ///
    /// 从 LUNARIS_WORKER_VERSION 环境变量读取。
    pub fn worker_version() -> Result<String, ContextError> {
        env_required(WORKER_VERSION_ENV)
    }

    /// 读取宿主能力列表
    ///
    /// 从 LUNARIS_HOST_CAPABILITIES 环境变量读取并解析 JSON 数组。
    pub fn host_capabilities() -> Result<Vec<String>, ContextError> {
        serde_json::from_str(&env_required(HOST_CAPABILITIES_ENV)?)
            .map_err(ContextError::InvalidCapabilities)
    }

    /// 检查是否具有指定能力
    ///
    /// Args:
    ///   - name: 能力名称
    ///
    /// Returns:
    ///   - 如果具有该能力返回 true
    pub fn has_capability(name: &str) -> Result<bool, ContextError> {
        Ok(host_capabilities()?
            .iter()
            .any(|capability| capability == name))
    }
}

/// 能力错误类型
///
/// 表示访问宿主能力时可能发生的错误。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CapabilityError {
    MissingCapability(&'static str),
}

impl core::fmt::Display for CapabilityError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            Self::MissingCapability(name) => write!(f, "missing Lunaris capability: {name}"),
        }
    }
}

impl std::error::Error for CapabilityError {}

/// SIMD 能力模块
///
/// 提供 SIMD 能力的宿主函数导入。
/// 这些函数通过 WASM 导入机制调用宿主实现。
pub mod simd {
    use super::{context, CapabilityError};

    // 声明 WASM 导入函数
    #[link(wasm_import_module = "lunaris:simd")]
    extern "C" {
        #[link_name = "ping"]
        fn lunaris_simd_ping_import() -> i32;

        #[link_name = "add"]
        fn lunaris_simd_add_import(a: i32, b: i32) -> i32;
    }

    /// 检查 SIMD 能力是否可用
    pub fn is_available() -> bool {
        context::has_capability("simd").unwrap_or(false)
    }

    /// 不安全地调用 ping 函数
    ///
    /// 不检查能力是否可用，调用者需确保能力已启用。
    pub unsafe fn ping_unchecked() -> i32 {
        lunaris_simd_ping_import()
    }

    /// 不安全地调用 add 函数
    ///
    /// 不检查能力是否可用，调用者需确保能力已启用。
    pub unsafe fn add_unchecked(a: i32, b: i32) -> i32 {
        lunaris_simd_add_import(a, b)
    }

    /// 安全地调用 ping 函数
    ///
    /// 检查 SIMD 能力是否可用，如果不可用返回错误。
    pub fn ping_checked() -> Result<i32, CapabilityError> {
        if !is_available() {
            return Err(CapabilityError::MissingCapability("simd"));
        }
        Ok(unsafe { ping_unchecked() })
    }

    /// 安全地调用 add 函数
    ///
    /// 检查 SIMD 能力是否可用，如果不可用返回错误。
    pub fn add_checked(a: i32, b: i32) -> Result<i32, CapabilityError> {
        if !is_available() {
            return Err(CapabilityError::MissingCapability("simd"));
        }
        Ok(unsafe { add_unchecked(a, b) })
    }
}

#[cfg(test)]
mod tests {
    use super::{context, TaskContext, HOST_CAPABILITIES_ENV, TASK_ID_ENV, WORKER_VERSION_ENV};

    #[test]
    fn parses_context_from_env() {
        std::env::set_var(TASK_ID_ENV, "42");
        std::env::set_var(WORKER_VERSION_ENV, "0.1.0");
        std::env::set_var(HOST_CAPABILITIES_ENV, "[\"simd\",\"log\"]");

        let ctx = TaskContext::current().expect("task context should parse");
        assert_eq!(ctx.task_id, 42);
        assert_eq!(ctx.worker_version, "0.1.0");
        assert_eq!(ctx.host_capabilities, vec!["simd", "log"]);
        assert!(context::has_capability("simd").expect("capability lookup should succeed"));
    }
}
