#include "engine.h"

#include <stdio.h>
#include <string.h>

static lunaris_mcu_limits_t lunaris_mcu_clamp_limits(
    lunaris_mcu_limits_t requested,
    lunaris_mcu_limits_t defaults,
    lunaris_mcu_limits_t maximums
) {
    lunaris_mcu_limits_t resolved = requested;

    if (resolved.max_fuel == 0ULL) {
        resolved.max_fuel = defaults.max_fuel;
    }
    if (resolved.max_memory_bytes == 0ULL) {
        resolved.max_memory_bytes = defaults.max_memory_bytes;
    }
    if (resolved.max_module_bytes == 0ULL) {
        resolved.max_module_bytes = defaults.max_module_bytes;
    }

    if (maximums.max_fuel > 0ULL && resolved.max_fuel > maximums.max_fuel) {
        resolved.max_fuel = maximums.max_fuel;
    }
    if (maximums.max_memory_bytes > 0ULL && resolved.max_memory_bytes > maximums.max_memory_bytes) {
        resolved.max_memory_bytes = maximums.max_memory_bytes;
    }
    if (maximums.max_module_bytes > 0ULL && resolved.max_module_bytes > maximums.max_module_bytes) {
        resolved.max_module_bytes = maximums.max_module_bytes;
    }

    return resolved;
}

bool lunaris_mcu_engine_init(
    lunaris_mcu_engine_t *engine,
    lunaris_mcu_limits_t default_limits,
    lunaris_mcu_limits_t max_limits
) {
    if (engine == NULL) {
        return false;
    }

    memset(engine, 0, sizeof(*engine));
    engine->environment = m3_NewEnvironment();
    if (engine->environment == NULL) {
        return false;
    }
    engine->runtime = m3_NewRuntime(engine->environment, LUNARIS_MCU_WASM_STACK_SIZE, NULL);
    if (engine->runtime == NULL) {
        m3_FreeEnvironment(engine->environment);
        engine->environment = NULL;
        return false;
    }
    engine->initialized = true;
    engine->default_limits = default_limits;
    engine->max_limits = max_limits;
    return true;
}

bool lunaris_mcu_engine_exec(
    lunaris_mcu_engine_t *engine,
    const lunaris_mcu_task_t *task,
    lunaris_mcu_engine_result_t *result
) {
    lunaris_mcu_limits_t effective_limits;

    if (engine == NULL || task == NULL || result == NULL || !engine->initialized) {
        return false;
    }

    memset(result, 0, sizeof(*result));
    effective_limits = lunaris_mcu_clamp_limits(task->execution_limits, engine->default_limits, engine->max_limits);

    if (task->wasm_module == NULL || task->wasm_module_len == 0U) {
        result->succeeded = false;
        snprintf(result->result, sizeof(result->result), "%s", "");
        snprintf((char *)result->stderr_data, sizeof(result->stderr_data), "empty wasm module");
        result->stderr_len = strlen((const char *)result->stderr_data);
        return true;
    }

    if (task->wasm_module_len > effective_limits.max_module_bytes && effective_limits.max_module_bytes > 0ULL) {
        result->succeeded = false;
        snprintf((char *)result->stderr_data, sizeof(result->stderr_data), "module too large");
        result->stderr_len = strlen((const char *)result->stderr_data);
        return true;
    }

    IM3Module module = NULL;
    M3Result wasm3_result = m3_ParseModule(engine->environment, &module, task->wasm_module, (uint32_t)task->wasm_module_len);
    if (wasm3_result != m3Err_none) {
        result->succeeded = false;
        snprintf((char *)result->stderr_data, sizeof(result->stderr_data), "wasm3 parse failed: %s", wasm3_result);
        result->stderr_len = strlen((const char *)result->stderr_data);
        return true;
    }

    wasm3_result = m3_LoadModule(engine->runtime, module);
    if (wasm3_result != m3Err_none) {
        result->succeeded = false;
        snprintf((char *)result->stderr_data, sizeof(result->stderr_data), "wasm3 load failed: %s", wasm3_result);
        result->stderr_len = strlen((const char *)result->stderr_data);
        return true;
    }

    result->succeeded = true;
    snprintf(result->result, sizeof(result->result), "{\"task_id\":%llu}", (unsigned long long)task->task_id);
    snprintf((char *)result->stdout_data, sizeof(result->stdout_data), "wasm3 loaded: %s", task->entry);
    result->stdout_len = strlen((const char *)result->stdout_data);
    result->duration_ms = 0.0;
    return true;
}

void lunaris_mcu_engine_shutdown(lunaris_mcu_engine_t *engine) {
    if (engine == NULL) {
        return;
    }
    if (engine->runtime != NULL) {
        m3_FreeRuntime(engine->runtime);
        engine->runtime = NULL;
    }
    if (engine->environment != NULL) {
        m3_FreeEnvironment(engine->environment);
        engine->environment = NULL;
    }
    engine->initialized = false;
}
