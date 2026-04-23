pub const TASK_ID_ENV: &str = "LUNARIS_TASK_ID";
pub const WORKER_VERSION_ENV: &str = "LUNARIS_WORKER_VERSION";
pub const HOST_CAPABILITIES_ENV: &str = "LUNARIS_HOST_CAPABILITIES";

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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskContext {
    pub task_id: u64,
    pub worker_version: String,
    pub host_capabilities: Vec<String>,
}

impl TaskContext {
    pub fn current() -> Result<Self, ContextError> {
        Ok(Self {
            task_id: context::task_id()?,
            worker_version: context::worker_version()?,
            host_capabilities: context::host_capabilities()?,
        })
    }
}

pub mod context {
    use super::{ContextError, HOST_CAPABILITIES_ENV, TASK_ID_ENV, WORKER_VERSION_ENV};

    fn env_required(name: &'static str) -> Result<String, ContextError> {
        std::env::var(name).map_err(|_| ContextError::MissingEnv(name))
    }

    pub fn task_id() -> Result<u64, ContextError> {
        env_required(TASK_ID_ENV)?
            .parse::<u64>()
            .map_err(ContextError::InvalidTaskId)
    }

    pub fn worker_version() -> Result<String, ContextError> {
        env_required(WORKER_VERSION_ENV)
    }

    pub fn host_capabilities() -> Result<Vec<String>, ContextError> {
        serde_json::from_str(&env_required(HOST_CAPABILITIES_ENV)?)
            .map_err(ContextError::InvalidCapabilities)
    }

    pub fn has_capability(name: &str) -> Result<bool, ContextError> {
        Ok(host_capabilities()?
            .iter()
            .any(|capability| capability == name))
    }
}

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

pub mod simd {
    use super::{context, CapabilityError};

    #[link(wasm_import_module = "lunaris:simd")]
    extern "C" {
        #[link_name = "ping"]
        fn lunaris_simd_ping_import() -> i32;

        #[link_name = "add"]
        fn lunaris_simd_add_import(a: i32, b: i32) -> i32;
    }

    pub fn is_available() -> bool {
        context::has_capability("simd").unwrap_or(false)
    }

    pub unsafe fn ping_unchecked() -> i32 {
        lunaris_simd_ping_import()
    }

    pub unsafe fn add_unchecked(a: i32, b: i32) -> i32 {
        lunaris_simd_add_import(a, b)
    }

    pub fn ping_checked() -> Result<i32, CapabilityError> {
        if !is_available() {
            return Err(CapabilityError::MissingCapability("simd"));
        }
        Ok(unsafe { ping_unchecked() })
    }

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
