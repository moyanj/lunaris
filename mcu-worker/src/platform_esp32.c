#include "platform.h"

#include <string.h>

#include "esp_timer.h"

bool lunaris_mcu_platform_init(void) {
    return true;
}

void lunaris_mcu_platform_shutdown(void) {
}

uint32_t lunaris_mcu_platform_millis(void) {
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

void lunaris_mcu_platform_delay_ms(uint32_t ms) {
    uint64_t start = esp_timer_get_time() / 1000ULL;
    while (((esp_timer_get_time() / 1000ULL) - start) < (uint64_t)ms) {
    }
}

bool lunaris_mcu_platform_get_info(lunaris_mcu_platform_info_t *info) {
    if (info == NULL) {
        return false;
    }

    memset(info, 0, sizeof(*info));
    strncpy(info->worker_name, "lunaris-esp32", sizeof(info->worker_name) - 1U);
    strncpy(info->arch, "xtensa-esp32", sizeof(info->arch) - 1U);
    info->memory_size_mb = 1U;
    return true;
}
