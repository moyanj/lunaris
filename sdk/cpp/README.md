# lunaris-cpp

Header-only C++ guest SDK for Lunaris WASM modules.

The C++ layer builds on top of `sdk/c/lunaris.h` and adds:

- `std::optional`-based context helpers
- a `TaskContext` value object
- `lunaris::simd` wrappers

## Files

- `lunaris.hpp`: single-header C++ wrapper
- `examples/context.cpp`: minimal example
- `CMakeLists.txt`: interface target

## Quick Start

```cpp
#include "lunaris.hpp"
#include <iostream>

extern "C" int wmain(int a, int b) {
    if (auto ctx = lunaris::TaskContext::current()) {
        std::cout << "task=" << ctx->task_id
                  << " worker=" << ctx->worker_version << "\n";
    }

    if (auto value = lunaris::simd::addChecked(a, b)) {
        return *value;
    }
    return a + b;
}
```
