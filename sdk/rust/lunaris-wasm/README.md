# lunaris-wasm

Rust guest SDK for Lunaris WASM tasks.

This crate is meant to be compiled into `wasm32-wasip1` modules that run inside Lunaris workers.

It provides:

- task context helpers backed by Lunaris-injected environment variables
- capability wrappers for Lunaris host imports
