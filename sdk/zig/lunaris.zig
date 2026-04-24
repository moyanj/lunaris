/**
 * Lunaris Zig Guest SDK
 *
 * 用于编译到 wasm32-wasip1 目标的 WASM 模块。
 * 提供任务上下文读取和宿主能力访问功能。
 *
 * 主要组件：
 *   - TaskContext: 任务上下文结构体
 *   - Error: 错误类型
 *   - context 命名空间: 环境变量读取函数
 *   - simd 命名空间: SIMD 能力封装
 *
 * 使用示例：
 *   ```zig
 *   const std = @import("std");
 *   const lunaris = @import("lunaris");
 *
 *   export fn wmain(a: i32, b: i32) i32 {
 *       var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
 *       defer arena.deinit();
 *
 *       var ctx = lunaris.TaskContext.load(arena.allocator()) catch return a + b;
 *       defer ctx.deinit(arena.allocator());
 *
 *       if (lunaris.simd.available()) {
 *           return lunaris.simd.addChecked(a, b) catch a + b;
 *       }
 *       return a + b;
 *   }
 *   ```
 */
const std = @import("std");

pub const task_id_env = "LUNARIS_TASK_ID";
pub const worker_version_env = "LUNARIS_WORKER_VERSION";
pub const host_capabilities_env = "LUNARIS_HOST_CAPABILITIES";

/// 错误类型
///
/// 表示读取任务上下文时可能发生的错误。
pub const Error = error{
    MissingEnv,
    InvalidTaskId,
    InvalidCapabilities,
    MissingCapability,
};

/// 任务上下文
///
/// 包含当前任务的元数据。
///
/// 字段：
///   - task_id: 任务 ID
///   - worker_version: Worker 版本号
///   - host_capabilities_json: 宿主能力 JSON 字符串
pub const TaskContext = struct {
    task_id: u64,
    worker_version: []u8,
    host_capabilities_json: []u8,

    /// 加载当前任务上下文
    ///
    /// 从环境变量读取任务上下文信息。
    ///
    /// Args:
    ///   - allocator: 内存分配器
    ///
    /// Returns:
    ///   - 成功：TaskContext
    ///   - 失败：Error
    pub fn load(allocator: std.mem.Allocator) Error!TaskContext {
        return .{
            .task_id = try context.taskId(allocator),
            .worker_version = try context.workerVersion(allocator),
            .host_capabilities_json = try context.hostCapabilitiesJson(allocator),
        };
    }

    /// 释放上下文资源
    ///
    /// 释放内部分配的字符串。
    pub fn deinit(self: *TaskContext, allocator: std.mem.Allocator) void {
        allocator.free(self.worker_version);
        allocator.free(self.host_capabilities_json);
        self.* = undefined;
    }
};

/// 读取环境变量（拥有所有权）
fn envOwned(allocator: std.mem.Allocator, name: []const u8) Error![]u8 {
    return std.process.getEnvVarOwned(allocator, name) catch |err| switch (err) {
        error.EnvironmentVariableNotFound => Error.MissingEnv,
        else => Error.InvalidCapabilities,
    };
}

/// 上下文读取函数
pub const context = struct {
    /// 读取任务 ID
    pub fn taskId(allocator: std.mem.Allocator) Error!u64 {
        const raw = try envOwned(allocator, task_id_env);
        defer allocator.free(raw);
        return std.fmt.parseUnsigned(u64, raw, 10) catch Error.InvalidTaskId;
    }

    /// 读取 Worker 版本
    pub fn workerVersion(allocator: std.mem.Allocator) Error![]u8 {
        return envOwned(allocator, worker_version_env);
    }

    /// 读取宿主能力 JSON
    pub fn hostCapabilitiesJson(allocator: std.mem.Allocator) Error![]u8 {
        return envOwned(allocator, host_capabilities_env);
    }

    /// 获取当前任务上下文
    pub fn current(allocator: std.mem.Allocator) Error!TaskContext {
        return TaskContext.load(allocator);
    }

    /// 检查是否具有指定能力
    pub fn hasCapability(name: []const u8) bool {
        const raw = std.process.getEnvVarOwned(std.heap.page_allocator, host_capabilities_env) catch return false;
        defer std.heap.page_allocator.free(raw);
        return containsQuotedToken(raw, name);
    }
};

/// 检查字符串是否包含引号包围的标记
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

/// SIMD 能力模块
///
/// 提供 SIMD 能力的宿主函数导入。
pub const simd = struct {
    extern "lunaris:simd" fn ping_import() i32;
    extern "lunaris:simd" fn add_import(a: i32, b: i32) i32;

    /// 检查 SIMD 能力是否可用
    pub fn available() bool {
        return context.hasCapability("simd");
    }

    /// 安全地调用 ping 函数
    pub fn pingChecked() Error!i32 {
        if (!available()) return Error.MissingCapability;
        return ping_import();
    }

    /// 安全地调用 add 函数
    pub fn addChecked(a: i32, b: i32) Error!i32 {
        if (!available()) return Error.MissingCapability;
        return add_import(a, b);
    }
};
