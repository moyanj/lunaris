# lunaris-c

Header-only C guest SDK for Lunaris WASM modules.

It wraps the Lunaris guest runtime contract:

- task context from environment variables
- capability checks
- typed imports for the `simd` capability group

## Files

- `lunaris.h`: single-header SDK
- `examples/context.c`: minimal `wmain` example
- `CMakeLists.txt`: interface target for embedding into a guest project

## Quick Start

```c
#include "lunaris.h"
#include <stdio.h>

int wmain(int a, int b) {
    lunaris_context_t ctx;
    if (lunaris_context_load(&ctx) == LUNARIS_STATUS_OK) {
        printf("task=%llu worker=%s\n",
            (unsigned long long)ctx.task_id,
            ctx.worker_version);
        lunaris_context_free(&ctx);
    }

    if (lunaris_has_capability("simd")) {
        return lunaris_simd_add_checked(a, b, NULL);
    }
    return a + b;
}
```

## CMake

```cmake
add_subdirectory(path/to/sdk/c lunaris-sdk-c)
target_link_libraries(your_guest PRIVATE lunaris_guest_sdk_c)
```
