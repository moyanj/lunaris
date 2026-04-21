//! SIMD Capability
//!
//! Mock capability for testing the capability system.
//! Provides `lunaris:simd/ping` function.

use anyhow::Result;
use wasmtime::{Caller, Linker};

use super::{require_capability, Capability, CapabilityHostState};

/// Capability name
pub const NAME: &str = "simd";

/// SIMD capability implementation
pub struct SimdCapability;

impl Capability for SimdCapability {
    const NAME: &'static str = NAME;

    fn register<T: CapabilityHostState + Send + 'static>(linker: &mut Linker<T>) -> Result<()> {
        // lunaris:simd/ping() -> i32
        // Returns 1 if capability is available
        linker.func_wrap(
            "lunaris:simd",
            "ping",
            |caller: Caller<'_, T>| -> Result<i32> {
                require_capability(&caller, NAME)?;
                Ok(1)
            },
        )?;

        // lunaris:simd/add(a: i32, b: i32) -> i32
        // Simple addition for testing
        linker.func_wrap(
            "lunaris:simd",
            "add",
            |caller: Caller<'_, T>, a: i32, b: i32| -> Result<i32> {
                require_capability(&caller, NAME)?;
                Ok(a.wrapping_add(b))
            },
        )?;

        Ok(())
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
