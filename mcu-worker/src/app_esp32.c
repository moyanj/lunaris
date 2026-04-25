#ifdef ESP_PLATFORM

#include "platform.h"
#include "wifi.h"
#include "worker.h"

void app_main(void) {
    lunaris_mcu_worker_t worker;
    lunaris_mcu_worker_config_t config;

    if (!lunaris_mcu_platform_init()) {
        return;
    }
    if (!lunaris_mcu_wifi_connect()) {
        lunaris_mcu_platform_shutdown();
        return;
    }

    lunaris_mcu_worker_config_init_defaults(&config);

    if (!lunaris_mcu_worker_init(&worker, &config)) {
        lunaris_mcu_platform_shutdown();
        return;
    }

    if (!lunaris_mcu_worker_run(&worker)) {
        lunaris_mcu_worker_shutdown(&worker);
        lunaris_mcu_platform_shutdown();
        return;
    }

    lunaris_mcu_worker_shutdown(&worker);
    lunaris_mcu_platform_shutdown();
}

#endif
