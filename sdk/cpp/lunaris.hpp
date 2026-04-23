#ifndef LUNARIS_GUEST_SDK_HPP
#define LUNARIS_GUEST_SDK_HPP

#include "../c/lunaris.h"

#include <optional>
#include <string>
#include <string_view>

namespace lunaris {

enum class Status {
    ok = LUNARIS_STATUS_OK,
    missing_env = LUNARIS_STATUS_MISSING_ENV,
    invalid_argument = LUNARIS_STATUS_INVALID_ARGUMENT,
    buffer_too_small = LUNARIS_STATUS_BUFFER_TOO_SMALL,
    parse_error = LUNARIS_STATUS_PARSE_ERROR,
    missing_capability = LUNARIS_STATUS_MISSING_CAPABILITY,
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
