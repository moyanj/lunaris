# lunaris-assemblyscript

AssemblyScript guest SDK for Lunaris WASM modules.

This SDK provides:

- task context reads from Lunaris environment variables
- capability checks
- typed `simd` host import wrappers

## Files

- `lunaris.ts`: SDK module

## Quick Start

```ts
import { TaskContext, context, simd } from "./lunaris";

export function wmain(a: i32, b: i32): i32 {
  let taskId: u64 = 0;
  const ctx = TaskContext.current();
  if (ctx != null) {
    taskId = ctx.taskId;
  } else {
    const fallback = context.taskId();
    if (fallback != null) taskId = fallback;
  }

  if (simd.available()) {
    const value = simd.addChecked(a, b);
    if (value != null) return value;
  }

  return a + b + <i32>(taskId % 2);
}
```

## Build

```bash
asc guest.ts sdk/assemblyscript/lunaris.ts \
  --outFile guest.wasm \
  -O2 \
  --runtime stub \
  --use abort=
```

The SDK relies on the AssemblyScript `process.env` API for environment access and
`@external(module, name)` for host imports.

