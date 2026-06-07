use std::env;

#[unsafe(no_mangle)]
pub extern "C" fn wmain(a: i32, b: i32) -> i32 {
    return a + b;
}
