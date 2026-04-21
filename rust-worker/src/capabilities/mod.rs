//! Lunaris Host Capabilities System
//!
//! This module provides a modular capability system for WASM host functions.
//! Each capability group is implemented as a separate module with conditional compilation.
//!
//! ## Architecture
//!
//! - `Capability` trait: Common interface for all capability groups
//! - `CapabilityRegistry`: Registry that collects and registers capabilities
//! - Individual modules: `simd`, etc.
//!
//! ## Usage
//!
//! ```ignore
//! use capabilities::{CapabilityRegistry, CapabilityHostState};
//!
//! let mut registry = CapabilityRegistry::new();
//! registry.register_capabilities(&mut linker, &enabled_capabilities)?;
//! ```

use anyhow::Result;
use std::collections::HashSet;
use wasmtime::Linker;

pub mod registry;
#[cfg(feature = "simd")]
pub mod simd;

pub use registry::CapabilityRegistry;

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

macro_rules! define_capability_registry {
    ($($feature:literal => $capability:path),+ $(,)?) => {
        /// Register all enabled capabilities into the linker.
        ///
        /// # Arguments
        /// * `linker` - Wasmtime linker to register functions into
        /// * `enabled_capabilities` - Set of capabilities the task has requested
        ///
        /// # Returns
        /// Ok(()) if registration succeeded
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

        /// Get list of all available capability names (for worker registration).
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

/// Trait that provides access to enabled capabilities.
/// Implemented by the host state to enable capability checks.
pub trait CapabilityHostState {
    fn enabled_capabilities(&self) -> &HashSet<String>;
}

/// Trait for capability group implementations.
/// Each capability group (simd, http, log, etc.) implements this trait.
pub trait Capability: Send + Sync + 'static {
    /// Unique capability group name (e.g., "simd", "http")
    const NAME: &'static str;

    /// Register this capability's host functions into the linker.
    /// Only called if this capability is in the enabled set.
    fn register<T: CapabilityHostState + Send + 'static>(linker: &mut Linker<T>) -> Result<()>;
}

/// Require a capability or return an error.
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
