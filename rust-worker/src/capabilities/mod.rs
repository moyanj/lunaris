/**
 * 宿主能力（Host Capabilities）系统模块
 *
 * 提供模块化的 WASM 宿主函数能力系统。
 * 每个能力组作为独立模块实现，支持条件编译。
 *
 * 架构：
 *   - Capability trait: 所有能力组的通用接口
 *   - CapabilityRegistry: 收集和注册能力的注册表
 *   - 独立模块: simd 等
 *
 * 使用示例：
 *   ```ignore
 *   use capabilities::{CapabilityRegistry, CapabilityHostState};
 *
 *   let mut registry = CapabilityRegistry::new();
 *   registry.register_capabilities(&mut linker, &enabled_capabilities)?;
 *   ```
 *
 * 扩展新能力：
 *   1. 创建新模块（如 http.rs）
 *   2. 实现 Capability trait
 *   3. 在 registry.rs 中添加到 define_capability_registry! 宏
 */
use anyhow::Result;
use std::collections::HashSet;
use wasmtime::Linker;

pub mod registry;
#[cfg(feature = "simd")]
pub mod simd;

pub use registry::CapabilityRegistry;

/// 注册能力函数的宏
///
/// 将宿主函数注册到 Linker 中，自动添加能力检查。
///
/// 参数：
///   - $linker: Linker 实例
///   - $capability: 能力名称（如 "simd"）
///   - 函数定义列表：name(args) -> ret { body }
///
/// 示例：
///   ```ignore
///   register_capability_functions! {
///       linker,
///       "simd";
///       "ping"(caller: Caller<'_, T>) -> i32 { Ok(1) }
///   }
///   ```
macro_rules! register_capability_functions {
    (
        $linker:expr,
        $capability:literal;
        $(
            $name:literal($caller:ident : Caller<'_, $t:ident> $(, $arg:ident : $arg_ty:ty)*) -> $ret:ty $body:block
        );+ $(;)?
    ) => {{
        $(
            $linker.func_wrap(
                concat!("lunaris:", $capability),
                $name,
                |$caller: wasmtime::Caller<'_, $t>, $($arg: $arg_ty),*| -> anyhow::Result<$ret> {
                    $crate::capabilities::require_capability(&$caller, $capability)?;
                    $body
                },
            )?;
        )+
        anyhow::Result::<()>::Ok(())
    }};
}

pub(crate) use register_capability_functions;

/// 定义能力注册表的宏
///
/// 生成 register_capabilities 和 available_names 方法。
///
/// 参数：
///   - $feature: 条件编译特性（如 "simd"）
///   - $capability: 能力类型（如 simd::SimdCapability）
///
/// 示例：
///   ```ignore
///   define_capability_registry! {
///       "simd" => simd::SimdCapability
///   }
///   ```
macro_rules! define_capability_registry {
    ($($feature:literal => $capability:path),+ $(,)?) => {
        /// 注册所有启用的能力到 Linker
        ///
        /// # 参数
        /// * `linker` - wasmtime Linker
        /// * `enabled_capabilities` - 任务请求的能力集合
        ///
        /// # 返回
        /// 注册成功返回 Ok(())
        pub fn register_capabilities<T: CapabilityHostState + Send + 'static>(
            &self,
            linker: &mut Linker<T>,
            enabled_capabilities: &HashSet<String>,
        ) -> anyhow::Result<()> {
            $(
                #[cfg(feature = $feature)]
                if enabled_capabilities.contains(<$capability as Capability>::NAME) {
                    <$capability as Capability>::register(linker)?;
                }
            )+
            Ok(())
        }

        /// 获取所有可用的能力名称（用于 Worker 注册）
        pub fn available_names(&self) -> Vec<&'static str> {
            let mut names = Vec::new();
            $(
                #[cfg(feature = $feature)]
                names.push(<$capability as Capability>::NAME);
            )+
            names
        }
    };
}

pub(crate) use define_capability_registry;

/// 宿主状态 trait
///
/// 提供对已启用能力的访问。
/// 由宿主状态实现，用于能力检查。
pub trait CapabilityHostState {
    fn enabled_capabilities(&self) -> &HashSet<String>;
}

/// 能力 trait
///
/// 所有能力组的通用接口。
/// 每个能力组（simd、http、log 等）都需要实现此 trait。
pub trait Capability: Send + Sync + 'static {
    /// 唯一的能力组名称（如 "simd", "http"）
    const NAME: &'static str;

    /// 将此能力的宿主函数注册到 Linker
    ///
    /// 仅当此能力在已启用集合中时才调用。
    fn register<T: CapabilityHostState + Send + 'static>(linker: &mut Linker<T>) -> Result<()>;
}

/// 检查能力是否启用
///
/// 如果能力未启用，返回错误。
///
/// Args:
///   - caller: WASM 调用者上下文
///   - capability: 能力名称
///
/// Returns:
///   - 能力已启用返回 Ok(())
///   - 能力未启用返回错误
pub fn require_capability<T: CapabilityHostState>(
    caller: &wasmtime::Caller<'_, T>,
    capability: &str,
) -> Result<()> {
    if caller.data().enabled_capabilities().contains(capability) {
        Ok(())
    } else {
        Err(anyhow::anyhow!(
            "missing host capability group: {capability}"
        ))
    }
}
