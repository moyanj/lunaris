#ifndef LUNARIS_MCU_WORKER_H
#define LUNARIS_MCU_WORKER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "engine.h"
#include "platform.h"
#include "proto.h"
#include "websocket.h"

typedef struct lunaris_mcu_worker_config {
    const char *master_uri;
    const char *token;
    const char *name;
    const char *arch;
    char name_storage[LUNARIS_MCU_NAME_MAX];
    char arch_storage[LUNARIS_MCU_ARCH_MAX];
    uint64_t memory_size_mb;
    uint32_t max_concurrency;
    bool use_compression;
    lunaris_mcu_host_capabilities_t provided_capabilities;
    lunaris_mcu_limits_t default_limits;
    lunaris_mcu_limits_t max_limits;
} lunaris_mcu_worker_config_t;

typedef struct lunaris_mcu_worker {
    lunaris_mcu_worker_config_t config;
    lunaris_mcu_ws_client_t ws;
    lunaris_mcu_engine_t engine;
    char node_id[LUNARIS_MCU_NODE_ID_MAX];
    bool running;
    bool drain_enabled;
    bool task_cancelled;
    uint64_t cancelled_task_id;
    uint32_t current_task;
    bool registration_complete;
} lunaris_mcu_worker_t;

bool lunaris_mcu_worker_init(lunaris_mcu_worker_t *worker, const lunaris_mcu_worker_config_t *config);
void lunaris_mcu_worker_config_init_defaults(lunaris_mcu_worker_config_t *config);
bool lunaris_mcu_worker_connect(lunaris_mcu_worker_t *worker);
bool lunaris_mcu_worker_register(lunaris_mcu_worker_t *worker);
bool lunaris_mcu_worker_send_heartbeat(lunaris_mcu_worker_t *worker);
bool lunaris_mcu_worker_handle_task(lunaris_mcu_worker_t *worker, const lunaris_mcu_task_t *task);
bool lunaris_mcu_worker_handle_control(lunaris_mcu_worker_t *worker, const lunaris_mcu_control_command_t *command);
bool lunaris_mcu_worker_poll_once(lunaris_mcu_worker_t *worker);
bool lunaris_mcu_worker_run(lunaris_mcu_worker_t *worker);
bool lunaris_mcu_worker_run_once(lunaris_mcu_worker_t *worker);
void lunaris_mcu_worker_shutdown(lunaris_mcu_worker_t *worker);

#endif
