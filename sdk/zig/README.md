# lunaris-zig

Zig guest SDK for Lunaris WASM modules.

The SDK exposes:

- `lunaris.context` for environment-backed task metadata
- `lunaris.TaskContext` for owned context loading
- `lunaris.simd` for typed host imports

## Files

- `lunaris.zig`: SDK module
- `examples/context.zig`: example guest entrypoint
- `build.zig`: minimal Zig project integration

## Quick Start

```zig
const std = @import("std");
const lunaris = @import("lunaris");

export fn wmain(a: i32, b: i32) i32 {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    var ctx = lunaris.TaskContext.load(arena.allocator()) catch return a + b;
    defer ctx.deinit(arena.allocator());

    if (lunaris.simd.available()) {
        return lunaris.simd.addChecked(a, b) catch a + b;
    }
    return a + b;
}
```
