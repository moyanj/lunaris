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

enum class Status {
    ok = LUNARIS_STATUS_OK,
    missing_env = LUNARIS_STATUS_MISSING_ENV,
    invalid_argument = LUNARIS_STATUS_INVALID_ARGUMENT,
    buffer_too_small = LUNARIS_STATUS_BUFFER_TOO_SMALL,
    parse_error = LUNARIS_STATUS_PARSE_ERROR,
    missing_capability = LUNARIS_STATUS_MISSING_CAPABILITY,
};

struct TaskContext {
    std::uint64_t task_id;
    std::string worker_version;
    std::string host_capabilities_json;

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

inline std::optional<std::uint64_t> taskId() {
    std::uint64_t value = 0;
    if (lunaris_task_id(&value) != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }
    return value;
}

inline std::optional<std::string> workerVersion() {
    return copyEnv(LUNARIS_WORKER_VERSION_ENV);
}

inline std::optional<std::string> hostCapabilitiesJson() {
    return copyEnv(LUNARIS_HOST_CAPABILITIES_ENV);
}

inline bool hasCapability(std::string_view name) {
    std::string owned(name);
    return lunaris_has_capability(owned.c_str());
}

namespace simd {

inline bool available() {
    return hasCapability("simd");
}

inline std::optional<std::int32_t> pingChecked() {
    lunaris_status_t status = LUNARIS_STATUS_OK;
    auto value = lunaris_simd_ping_checked(&status);
    if (status != LUNARIS_STATUS_OK) {
        return std::nullopt;
    }
    return value;
}

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
