#include "platform.h"

#include <string.h>
#include <time.h>

static uint64_t lunaris_mcu_platform_now_ms(void) {
    struct timespec ts;

    if (timespec_get(&ts, TIME_UTC) != TIME_UTC) {
        return 0U;
    }

    return ((uint64_t)ts.tv_sec * 1000ULL) + ((uint64_t)ts.tv_nsec / 1000000ULL);
}

bool lunaris_mcu_platform_init(void) {
    return true;
}

void lunaris_mcu_platform_shutdown(void) {
}

uint32_t lunaris_mcu_platform_millis(void) {
    return (uint32_t)(lunaris_mcu_platform_now_ms() & 0xFFFFFFFFU);
}

void lunaris_mcu_platform_delay_ms(uint32_t ms) {
    uint64_t start = lunaris_mcu_platform_now_ms();
    while ((lunaris_mcu_platform_now_ms() - start) < (uint64_t)ms) {
    }
}

bool lunaris_mcu_platform_get_info(lunaris_mcu_platform_info_t *info) {
    if (info == NULL) {
        return false;
    }

    memset(info, 0, sizeof(*info));
    strncpy(info->worker_name, "lunaris-mcu", sizeof(info->worker_name) - 1U);
    strncpy(info->arch, "generic-mcu", sizeof(info->arch) - 1U);
    info->memory_size_mb = 1U;
    return true;
}
