const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.resolveTargetQuery(.{
        .cpu_arch = .wasm32,
        .os_tag = .wasi,
    });
    const optimize = b.standardOptimizeOption(.{});

    _ = b.addModule("lunaris", .{
        .root_source_file = b.path("lunaris.zig"),
        .target = target,
        .optimize = optimize,
    });

    const example = b.addExecutable(.{
        .name = "lunaris-zig-example",
        .root_module = b.createModule(.{
            .root_source_file = b.path("examples/context.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    example.entry = .disabled;
    example.root_module.addImport("lunaris", b.createModule(.{
        .root_source_file = b.path("lunaris.zig"),
        .target = target,
        .optimize = optimize,
    }));

    b.installArtifact(example);
}
