const std = @import("std");

pub const task_id_env = "LUNARIS_TASK_ID";
pub const worker_version_env = "LUNARIS_WORKER_VERSION";
pub const host_capabilities_env = "LUNARIS_HOST_CAPABILITIES";

pub const Error = error{
    MissingEnv,
    InvalidTaskId,
    InvalidCapabilities,
    MissingCapability,
};

fn envOwned(allocator: std.mem.Allocator, name: []const u8) Error![]u8 {
    return std.process.getEnvVarOwned(allocator, name) catch |err| switch (err) {
        error.EnvironmentVariableNotFound => Error.MissingEnv,
        else => Error.InvalidCapabilities,
    };
}

pub const context = struct {
    pub fn taskId(allocator: std.mem.Allocator) Error!u64 {
        const raw = try envOwned(allocator, task_id_env);
        defer allocator.free(raw);
        return std.fmt.parseUnsigned(u64, raw, 10) catch Error.InvalidTaskId;
    }

    pub fn workerVersion(allocator: std.mem.Allocator) Error![]u8 {
        return envOwned(allocator, worker_version_env);
    }

    pub fn hostCapabilitiesJson(allocator: std.mem.Allocator) Error![]u8 {
        return envOwned(allocator, host_capabilities_env);
    }

    pub fn hasCapability(name: []const u8) bool {
        const raw = std.process.getEnvVarOwned(std.heap.page_allocator, host_capabilities_env) catch return false;
        defer std.heap.page_allocator.free(raw);
        return containsQuotedToken(raw, name);
    }
};

fn containsQuotedToken(raw: []const u8, needle: []const u8) bool {
    var index: usize = 0;
    while (index < raw.len) : (index += 1) {
        if (raw[index] != '"') continue;
        const start = index + 1;
        const end = std.mem.indexOfScalarPos(u8, raw, start, '"') orelse return false;
        if (std.mem.eql(u8, raw[start..end], needle)) return true;
        index = end;
    }
    return false;
}

pub const simd = struct {
    extern "lunaris:simd" fn ping_import() i32;
    extern "lunaris:simd" fn add_import(a: i32, b: i32) i32;

    pub fn available() bool {
        return context.hasCapability("simd");
    }

    pub fn pingChecked() Error!i32 {
        if (!available()) return Error.MissingCapability;
        return ping_import();
    }

    pub fn addChecked(a: i32, b: i32) Error!i32 {
        if (!available()) return Error.MissingCapability;
        return add_import(a, b);
    }
};
