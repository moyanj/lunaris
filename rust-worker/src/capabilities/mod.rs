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
