//! SIMD Capability
//!
//! Mock capability for testing the capability system.
//! Provides `lunaris:simd/ping` function.

use anyhow::Result;
use wasmtime::Linker;

use super::{register_capability_functions, Capability, CapabilityHostState};

/// SIMD capability implementation
pub struct SimdCapability;

impl Capability for SimdCapability {
    const NAME: &'static str = "simd";

    fn register<T: CapabilityHostState + Send + 'static>(linker: &mut Linker<T>) -> Result<()> {
        register_capability_functions! {
            linker,
            "simd";
            "ping"(caller: Caller<'_, T>) -> i32 {
                Ok(1)
            };
            "add"(caller: Caller<'_, T>, a: i32, b: i32) -> i32 {
                Ok(a.wrapping_add(b))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;
    use wasmtime::Engine;

    struct TestState {
        enabled: HashSet<String>,
    }

    impl CapabilityHostState for TestState {
        fn enabled_capabilities(&self) -> &HashSet<String> {
            &self.enabled
        }
    }

    #[test]
    fn test_simd_registration() {
        let engine = Engine::default();
        let mut linker = Linker::<TestState>::new(&engine);

        SimdCapability::register(&mut linker).unwrap();
    }

    #[test]
    fn test_name() {
        assert_eq!(SimdCapability::NAME, "simd");
    }
}
