#ifndef LUNARIS_MCU_ENGINE_H
#define LUNARIS_MCU_ENGINE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "m3_env.h"
#include "m3_exception.h"
#include "config.h"
#include "proto.h"

typedef struct lunaris_mcu_engine {
    bool initialized;
    lunaris_mcu_limits_t default_limits;
    lunaris_mcu_limits_t max_limits;
    IM3Environment environment;
    IM3Runtime runtime;
    uint8_t wasm_heap[LUNARIS_MCU_WASM_HEAP_SIZE];
    uint8_t wasm_stack[LUNARIS_MCU_WASM_STACK_SIZE];
} lunaris_mcu_engine_t;

typedef struct lunaris_mcu_engine_result {
    bool succeeded;
    double duration_ms;
    char result[LUNARIS_MCU_RESULT_MAX];
    uint8_t stdout_data[LUNARIS_MCU_STDIO_MAX];
    size_t stdout_len;
    uint8_t stderr_data[LUNARIS_MCU_STDIO_MAX];
    size_t stderr_len;
} lunaris_mcu_engine_result_t;

bool lunaris_mcu_engine_init(
    lunaris_mcu_engine_t *engine,
    lunaris_mcu_limits_t default_limits,
    lunaris_mcu_limits_t max_limits
);

bool lunaris_mcu_engine_exec(
    lunaris_mcu_engine_t *engine,
    const lunaris_mcu_task_t *task,
    lunaris_mcu_engine_result_t *result
);

void lunaris_mcu_engine_shutdown(lunaris_mcu_engine_t *engine);

#endif
