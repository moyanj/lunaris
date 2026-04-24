/**
 * 能力注册表模块
 *
 * 收集所有可用的能力，并根据启用集合注册到 Linker。
 *
 * 主要功能：
 *   - register_capabilities: 注册启用的能力
 *   - available_names: 获取所有可用能力名称
 *
 * 使用示例：
 *   ```ignore
 *   let registry = CapabilityRegistry::new();
 *   registry.register_capabilities(&mut linker, &enabled)?;
 *   ```
 */
use std::collections::HashSet;
use wasmtime::Linker;

use super::{define_capability_registry, Capability, CapabilityHostState};
#[cfg(feature = "simd")]
use crate::capabilities::simd;

/// 能力注册表
///
/// 管理能力的注册，支持条件编译。
///
/// 当前支持的能力：
///   - simd: SIMD 模拟能力（测试用）
pub struct CapabilityRegistry;

impl CapabilityRegistry {
    /// 创建新的注册表
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
