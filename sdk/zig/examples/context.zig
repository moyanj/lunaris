const std = @import("std");
const lunaris = @import("lunaris");

export fn wmain(a: i32, b: i32) i32 {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    var ctx = lunaris.TaskContext.load(arena.allocator()) catch return a + b;
    defer ctx.deinit(arena.allocator());

    std.debug.print(
        "task={d} worker={s} caps={s}\n",
        .{ ctx.task_id, ctx.worker_version, ctx.host_capabilities_json },
    );

    return lunaris.simd.addChecked(a, b) catch a + b;
}
