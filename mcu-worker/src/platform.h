#ifndef LUNARIS_MCU_PLATFORM_H
#define LUNARIS_MCU_PLATFORM_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct lunaris_mcu_platform_info {
    char worker_name[64];
    char arch[32];
    uint64_t memory_size_mb;
} lunaris_mcu_platform_info_t;

bool lunaris_mcu_platform_init(void);
void lunaris_mcu_platform_shutdown(void);
uint32_t lunaris_mcu_platform_millis(void);
void lunaris_mcu_platform_delay_ms(uint32_t ms);
bool lunaris_mcu_platform_get_info(lunaris_mcu_platform_info_t *info);

#endif
