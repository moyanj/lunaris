#include "worker.h"

int main(void) {
    lunaris_mcu_worker_t worker;
    lunaris_mcu_worker_config_t config;

    if (!lunaris_mcu_platform_init()) {
        return 1;
    }

    lunaris_mcu_worker_config_init_defaults(&config);

    if (!lunaris_mcu_worker_init(&worker, &config)) {
        lunaris_mcu_platform_shutdown();
        return 1;
    }

    if (!lunaris_mcu_worker_run(&worker)) {
        lunaris_mcu_worker_shutdown(&worker);
        lunaris_mcu_platform_shutdown();
        return 1;
    }

    lunaris_mcu_worker_shutdown(&worker);
    lunaris_mcu_platform_shutdown();
    return 0;
}
