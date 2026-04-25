#ifndef LUNARIS_MCU_CONFIG_H
#define LUNARIS_MCU_CONFIG_H

#include <stddef.h>
#include <stdint.h>

#ifdef ESP_PLATFORM
#include "sdkconfig.h"
#endif

#define LUNARIS_MCU_NAME_MAX 64U
#define LUNARIS_MCU_ARCH_MAX 32U
#define LUNARIS_MCU_NODE_ID_MAX 64U
#define LUNARIS_MCU_TOKEN_MAX 128U
#define LUNARIS_MCU_ENTRY_MAX 64U
#define LUNARIS_MCU_ARGS_MAX 256U
#define LUNARIS_MCU_RESULT_MAX 256U
#define LUNARIS_MCU_STDIO_MAX 512U
#define LUNARIS_MCU_ERROR_MAX 256U
#define LUNARIS_MCU_CAPABILITIES_MAX 8U
#define LUNARIS_MCU_CAPABILITY_ITEM_MAX 32U

#define LUNARIS_MCU_WASM_HEAP_SIZE (32U * 1024U)
#define LUNARIS_MCU_WASM_STACK_SIZE (8U * 1024U)
#define LUNARIS_MCU_WS_BUFFER_SIZE (4U * 1024U)
#define LUNARIS_MCU_PROTO_BUFFER_SIZE (2U * 1024U)
#define LUNARIS_MCU_TASK_QUEUE_SIZE 1U

#define LUNARIS_MCU_DEFAULT_MAX_FUEL 0ULL
#define LUNARIS_MCU_DEFAULT_MAX_MEMORY (32ULL * 1024ULL)
#define LUNARIS_MCU_DEFAULT_MAX_MODULE (64ULL * 1024ULL)

#define LUNARIS_MCU_MAX_FUEL 1000000ULL
#define LUNARIS_MCU_MAX_MEMORY (64ULL * 1024ULL)
#define LUNARIS_MCU_MAX_MODULE (128ULL * 1024ULL)

#define LUNARIS_MCU_HEARTBEAT_INTERVAL_MS 10000U

#ifndef LUNARIS_MCU_WS_RECV_POLL_MS
#define LUNARIS_MCU_WS_RECV_POLL_MS 100U
#endif

#ifndef LUNARIS_MCU_MASTER_URI
#ifdef ESP_PLATFORM
#define LUNARIS_MCU_MASTER_URI CONFIG_LUNARIS_MASTER_URI
#else
#define LUNARIS_MCU_MASTER_URI "ws://127.0.0.1:8000/worker"
#endif
#endif

#ifndef LUNARIS_MCU_WORKER_TOKEN
#ifdef ESP_PLATFORM
#define LUNARIS_MCU_WORKER_TOKEN CONFIG_LUNARIS_WORKER_TOKEN
#else
#define LUNARIS_MCU_WORKER_TOKEN ""
#endif
#endif

#ifndef LUNARIS_MCU_WORKER_NAME
#ifdef ESP_PLATFORM
#define LUNARIS_MCU_WORKER_NAME CONFIG_LUNARIS_WORKER_NAME
#else
#define LUNARIS_MCU_WORKER_NAME "lunaris-mcu"
#endif
#endif

#ifndef LUNARIS_MCU_WORKER_ARCH
#define LUNARIS_MCU_WORKER_ARCH "generic-mcu"
#endif

#ifndef LUNARIS_MCU_MEMORY_SIZE_MB
#define LUNARIS_MCU_MEMORY_SIZE_MB 1U
#endif

typedef struct lunaris_mcu_limits {
    uint64_t max_fuel;
    uint64_t max_memory_bytes;
    uint64_t max_module_bytes;
} lunaris_mcu_limits_t;

static inline lunaris_mcu_limits_t lunaris_mcu_default_limits(void) {
    lunaris_mcu_limits_t limits = {
        .max_fuel = LUNARIS_MCU_DEFAULT_MAX_FUEL,
        .max_memory_bytes = LUNARIS_MCU_DEFAULT_MAX_MEMORY,
        .max_module_bytes = LUNARIS_MCU_DEFAULT_MAX_MODULE,
    };
    return limits;
}

static inline lunaris_mcu_limits_t lunaris_mcu_max_limits(void) {
    lunaris_mcu_limits_t limits = {
        .max_fuel = LUNARIS_MCU_MAX_FUEL,
        .max_memory_bytes = LUNARIS_MCU_MAX_MEMORY,
        .max_module_bytes = LUNARIS_MCU_MAX_MODULE,
    };
    return limits;
}

#endif
