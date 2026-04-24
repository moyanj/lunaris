# lunaris-grain

Grain guest SDK for Lunaris WASM modules.

This SDK currently provides:

- task context reads from Lunaris environment variables
- capability checks against `LUNARIS_HOST_CAPABILITIES`

## Files

- `lunaris.gr`: SDK module

## Quick Start

```grain
from "./lunaris" include *
from "result" include Result

export let wmain = (a: Number, b: Number): Number =>
  Result.mapWithDefault(
    (ctx) => hasCapability("simd") ? a + b + (ctx.taskId % 2) : a + b,
    a + b,
    currentContext(),
  )
```

## Build

```bash
grain compile guest.gr -o guest.wasm
```

## Notes

The Grain SDK currently focuses on context access and capability discovery.
Unlike the Rust/C/C++/Zig/Go/AssemblyScript SDKs, it does not yet wrap Lunaris host
imports such as `lunaris:simd`. Grain's host-import surface is evolving and should be
implemented against the compiler/runtime version you standardize on.

