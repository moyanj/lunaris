//! Capability Registry
//!
//! Collects all available capabilities and registers them based on enabled set.

use std::collections::HashSet;
use wasmtime::Linker;

use super::{Capability, CapabilityHostState};
#[cfg(feature = "simd")]
use crate::capabilities::simd;

/// Registry that manages capability registration.
pub struct CapabilityRegistry;

impl CapabilityRegistry {
    /// Create a new registry.
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self
    }

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
        #[cfg(feature = "simd")]
        if enabled_capabilities.contains(<simd::SimdCapability as Capability>::NAME) {
            simd::SimdCapability::register(linker)?;
        }
        Ok(())
    }

    /// Get list of all available capability names (for worker registration).
    pub fn available_names(&self) -> Vec<&'static str> {
        let mut names = Vec::new();
        #[cfg(feature = "simd")]
        names.push(<simd::SimdCapability as Capability>::NAME);
        names
    }
}

impl Default for CapabilityRegistry {
    fn default() -> Self {
        Self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_registry_contains_simd() {
        let registry = CapabilityRegistry::new();
        let names = registry.available_names();
        assert!(names.contains(&"simd"));
    }

    #[test]
    fn test_register_only_enabled() {
        use std::collections::HashSet;
        use wasmtime::{Engine, Linker};

        struct TestState {
            enabled: HashSet<String>,
        }

        impl CapabilityHostState for TestState {
            fn enabled_capabilities(&self) -> &HashSet<String> {
                &self.enabled
            }
        }

        let engine = Engine::default();
        let mut linker = Linker::<TestState>::new(&engine);
        let registry = CapabilityRegistry::new();
        let mut enabled = HashSet::new();
        #[cfg(feature = "simd")]
        enabled.insert("simd".to_string());

        registry
            .register_capabilities(&mut linker, &enabled)
            .unwrap();
    }
}
