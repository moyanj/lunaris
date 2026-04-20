use anyhow::{Result, anyhow};
use std::collections::HashSet;
use wasmtime::{Caller, Linker};

pub const MOCK_SIMD_CAPABILITY: &str = "simd";
pub const DEFAULT_PROVIDED_CAPABILITIES: &[&str] = &[MOCK_SIMD_CAPABILITY];

pub trait CapabilityHostState {
    fn enabled_capabilities(&self) -> &HashSet<String>;
}

pub fn register_capabilities<T>(
    linker: &mut Linker<T>,
    enabled_capabilities: &[String],
) -> Result<()>
where
    T: CapabilityHostState + Send + 'static,
{
    if enabled_capabilities
        .iter()
        .any(|capability| capability == MOCK_SIMD_CAPABILITY)
    {
        register_mock_simd(linker)?;
    }
    Ok(())
}

fn register_mock_simd<T>(linker: &mut Linker<T>) -> Result<()>
where
    T: CapabilityHostState + Send + 'static,
{
    linker.func_wrap(
        "lunaris:simd",
        "ping",
        |caller: Caller<'_, T>| -> Result<i32> {
            require_capability(&caller, MOCK_SIMD_CAPABILITY)?;
            Ok(1)
        },
    )?;
    Ok(())
}

fn require_capability<T>(caller: &Caller<'_, T>, capability: &str) -> Result<()>
where
    T: CapabilityHostState,
{
    if caller.data().enabled_capabilities().contains(capability) {
        Ok(())
    } else {
        Err(anyhow!("missing host capability group: {capability}"))
    }
}
