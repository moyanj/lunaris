/**
 * Lunaris C++ Guest SDK
 *
 * 基于 C SDK 的 C++ 封装，提供更现代的 API。
 * 使用 std::optional 和 std::string_view 提供类型安全的接口。
 *
 * 主要组件：
 *   - Status: 状态枚举
 *   - TaskContext: 任务上下文类
 *   - context 函数: 环境变量读取
 *   - simd 命名空间: SIMD 能力封装
 *
 * 使用示例：
 *   ```cpp
 *   #include "lunaris.hpp"
 *   #include <iostream>
 *
 *   extern "C" int wmain(int a, int b) {
 *       if (auto ctx = lunaris::TaskContext::current()) {
 *           std::cout << "task=" << ctx->task_id
 *                     << " worker=" << ctx->worker_version << "\n";
 *       }
 *
 *       if (auto value = lunaris::simd::addChecked(a, b)) {
 *           return *value;
 *       }
 *       return a + b;
 *   }
 *   ```
 */
#ifndef LUNARIS_GUEST_SDK_HPP
#define LUNARIS_GUEST_SDK_HPP

#include "../c/lunaris.h"

#include <cstdint>
#include <cstring>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace lunaris {

/**
 * 状态枚举
 *
 * 表示操作的执行结果。
 */
enum class Status {
    ok = LUNARIS_STATUS_OK,
    missing_env = LUNARIS_STATUS_MISSING_ENV,
    invalid_argument = LUNARIS_STATUS_INVALID_ARGUMENT,
    buffer_too_small = LUNARIS_STATUS_BUFFER_TOO_SMALL,
    parse_error = LUNARIS_STATUS_PARSE_ERROR,
    missing_capability = LUNARIS_STATUS_MISSING_CAPABILITY,
};

/**
 * 任务上下文
 *
 * 包含当前任务的元数据。
 *
 * 字段：
 *   - task_id: 任务 ID
 *   - worker_version: Worker 版本号
 *   - host_capabilities_json: 宿主能力 JSON 字符串
 */
struct TaskContext {
    std::uint64_t task_id;
    std::string worker_version;
    std::string host_capabilities_json;

    /**
     * 获取当前任务上下文
     *
     * 从环境变量读取任务上下文信息。
     *
     * Returns:
     *   - 成功：TaskContext
     *   - 失败：std::nullopt
     */
    static std::optional<TaskContext> current() {
        lunaris_context_t raw{};
        if (lunaris_context_load(&raw) != LUNARIS_STATUS_OK) {
            return std::nullopt;
        }

        TaskContext context{
            raw.task_id,
            raw.worker_version ? std::string(raw.worker_version) : std::string(),
            raw.host_capabilities_json ? std::string(raw.host_capabilities_json) : std::string(),
        };
        lunaris_context_free(&raw);
        return std::optional<TaskContext>(std::move(context));
    }

    /**
     * 解析宿主能力列表
     *
     * 从 JSON 字符串解析能力名称列表。
     *
     * Returns:
     *   - 能力名称向量
     */
    std::vector<std::string> hostCapabilities() const {
        std::vector<std::string> items;
        const char* cursor = host_capabilities_json.c_str();
        while ((cursor = std::strchr(cursor, '"')) != nullptr) {
            const char* end = std::strchr(cursor + 1, '"');
            if (!end) {
                return items;
            }
            items.emplace_back(cursor + 1, static_cast<std::size_t>(end - (cursor + 1)));
            cursor = end + 1;
        }
        return items;
    }
};

/**
 * 读取环境变量
 *
 * 从环境变量读取字符串值。
 *
 * Args:
 *   - name: 环境变量名称
 *
 * Returns:
 *   - 成功：std::string
 *   - 失败：std::nullopt
 */
inline std::optional<std::string> copyEnv(const char* name) {
    size_t len = 0;
    if (lunaris_copy_env(name, nullptr, 0, &len) != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }

    std::string value(len, '\0');
    if (lunaris_copy_env(name, value.data(), len + 1, nullptr) != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }
    return value;
}

/**
 * 读取任务 ID
 *
 * Returns:
 *   - 成功：std::uint64_t
 *   - 失败：std::nullopt
 */
inline std::optional<std::uint64_t> taskId() {
    std::uint64_t value = 0;
    if (lunaris_task_id(&value) != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }
    return value;
}

/**
 * 读取 Worker 版本
 */
inline std::optional<std::string> workerVersion() {
    return copyEnv(LUNARIS_WORKER_VERSION_ENV);
}

/**
 * 读取宿主能力 JSON
 */
inline std::optional<std::string> hostCapabilitiesJson() {
    return copyEnv(LUNARIS_HOST_CAPABILITIES_ENV);
}

/**
 * 检查是否具有指定能力
 */
inline bool hasCapability(std::string_view name) {
    std::string owned(name);
    return lunaris_has_capability(owned.c_str());
}

namespace simd {

/**
 * 检查 SIMD 能力是否可用
 */
inline bool available() {
    return hasCapability("simd");
}

/**
 * 安全地调用 ping 函数
 */
inline std::optional<std::int32_t> pingChecked() {
    lunaris_status_t status = LUNARIS_STATUS_OK;
    auto value = lunaris_simd_ping_checked(&status);
    if (status != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }
    return value;
}

/**
 * 安全地调用 add 函数
 */
inline std::optional<std::int32_t> addChecked(std::int32_t a, std::int32_t b) {
    lunaris_status_t status = LUNARIS_STATUS_OK;
    auto value = lunaris_simd_add_checked(a, b, &status);
    if (status != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }
    return value;
}

}  // namespace simd
}  // namespace lunaris

#endif
