//! Capability Registry
//!
//! Collects all available capabilities and registers them based on enabled set.

use std::collections::HashSet;
use wasmtime::Linker;

use super::{define_capability_registry, Capability, CapabilityHostState};
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
    define_capability_registry! {
        "simd" => simd::SimdCapability
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
