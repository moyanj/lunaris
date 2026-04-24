/**
 * SIMD 能力模块
 *
 * 模拟能力，用于测试能力系统。
 * 提供 `lunaris:simd/ping` 和 `lunaris:simd/add` 函数。
 *
 * 主要功能：
 *   - ping: 测试函数，返回 1
 *   - add: 加法函数，使用 wrapping_add 避免溢出
 *
 * 使用场景：
 *   - 测试能力系统是否正常工作
 *   - 验证能力检查机制
 */
use anyhow::Result;
use wasmtime::Linker;

use super::{register_capability_functions, Capability, CapabilityHostState};

/// SIMD 能力实现
///
/// 提供 SIMD 模拟功能，用于测试。
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
