#ifndef LUNARIS_GUEST_SDK_H
#define LUNARIS_GUEST_SDK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define LUNARIS_TASK_ID_ENV "LUNARIS_TASK_ID"
#define LUNARIS_WORKER_VERSION_ENV "LUNARIS_WORKER_VERSION"
#define LUNARIS_HOST_CAPABILITIES_ENV "LUNARIS_HOST_CAPABILITIES"

typedef enum lunaris_status {
    LUNARIS_STATUS_OK = 0,
    LUNARIS_STATUS_MISSING_ENV = 1,
    LUNARIS_STATUS_INVALID_ARGUMENT = 2,
    LUNARIS_STATUS_BUFFER_TOO_SMALL = 3,
    LUNARIS_STATUS_PARSE_ERROR = 4,
    LUNARIS_STATUS_MISSING_CAPABILITY = 5,
} lunaris_status_t;

static inline lunaris_status_t lunaris_copy_env(
    const char *name,
    char *buf,
    size_t buf_len,
    size_t *out_len
) {
    const char *value = getenv(name);
    size_t value_len;

    if (!value) {
        return LUNARIS_STATUS_MISSING_ENV;
    }

    value_len = strlen(value);
    if (out_len) {
        *out_len = value_len;
    }

    if (!buf) {
        return LUNARIS_STATUS_OK;
    }
    if (buf_len <= value_len) {
        return LUNARIS_STATUS_BUFFER_TOO_SMALL;
    }

    memcpy(buf, value, value_len + 1);
    return LUNARIS_STATUS_OK;
}

static inline lunaris_status_t lunaris_task_id(uint64_t *out_task_id) {
    const char *value = getenv(LUNARIS_TASK_ID_ENV);
    char *end = NULL;
    unsigned long long parsed;

    if (!out_task_id) {
        return LUNARIS_STATUS_INVALID_ARGUMENT;
    }
    if (!value) {
        return LUNARIS_STATUS_MISSING_ENV;
    }

    parsed = strtoull(value, &end, 10);
    if (end == value || (end && *end != '\0')) {
        return LUNARIS_STATUS_PARSE_ERROR;
    }

    *out_task_id = (uint64_t)parsed;
    return LUNARIS_STATUS_OK;
}

static inline lunaris_status_t lunaris_worker_version(
    char *buf,
    size_t buf_len,
    size_t *out_len
) {
    return lunaris_copy_env(LUNARIS_WORKER_VERSION_ENV, buf, buf_len, out_len);
}

static inline lunaris_status_t lunaris_host_capabilities_json(
    char *buf,
    size_t buf_len,
    size_t *out_len
) {
    return lunaris_copy_env(LUNARIS_HOST_CAPABILITIES_ENV, buf, buf_len, out_len);
}

static inline bool lunaris_has_capability(const char *name) {
    const char *json = getenv(LUNARIS_HOST_CAPABILITIES_ENV);
    size_t name_len;
    const char *cursor;

    if (!json || !name || !name[0]) {
        return false;
    }

    name_len = strlen(name);
    cursor = json;
    while ((cursor = strchr(cursor, '"')) != NULL) {
        const char *end = strchr(cursor + 1, '"');
        if (!end) {
            return false;
        }
        if ((size_t)(end - (cursor + 1)) == name_len &&
            strncmp(cursor + 1, name, name_len) == 0) {
            return true;
        }
        cursor = end + 1;
    }

    return false;
}

#if defined(__clang__) || defined(__GNUC__)
#define LUNARIS_WASM_IMPORT(module_name, symbol_name) \
    __attribute__((import_module(module_name), import_name(symbol_name)))
#else
#define LUNARIS_WASM_IMPORT(module_name, symbol_name)
#endif

extern int32_t lunaris_simd_ping(void)
    LUNARIS_WASM_IMPORT("lunaris:simd", "ping");

extern int32_t lunaris_simd_add(int32_t a, int32_t b)
    LUNARIS_WASM_IMPORT("lunaris:simd", "add");

static inline int32_t lunaris_simd_ping_checked(lunaris_status_t *status) {
    if (!lunaris_has_capability("simd")) {
        if (status) {
            *status = LUNARIS_STATUS_MISSING_CAPABILITY;
        }
        return 0;
    }
    if (status) {
        *status = LUNARIS_STATUS_OK;
    }
    return lunaris_simd_ping();
}

static inline int32_t lunaris_simd_add_checked(
    int32_t a,
    int32_t b,
    lunaris_status_t *status
) {
    if (!lunaris_has_capability("simd")) {
        if (status) {
            *status = LUNARIS_STATUS_MISSING_CAPABILITY;
        }
        return 0;
    }
    if (status) {
        *status = LUNARIS_STATUS_OK;
    }
    return lunaris_simd_add(a, b);
}

#endif
