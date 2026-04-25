#ifndef LUNARIS_MCU_PROTO_H
#define LUNARIS_MCU_PROTO_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "config.h"
#include "pb.h"

typedef enum lunaris_mcu_message_type {
    LUNARIS_MCU_MSG_TASK = 0,
    LUNARIS_MCU_MSG_TASK_RESULT = 1,
    LUNARIS_MCU_MSG_CONTROL_COMMAND = 2,
    LUNARIS_MCU_MSG_NODE_STATUS = 3,
    LUNARIS_MCU_MSG_NODE_REGISTRATION = 4,
    LUNARIS_MCU_MSG_NODE_REGISTRATION_REPLY = 5,
    LUNARIS_MCU_MSG_UNREGISTER_NODE = 6,
    LUNARIS_MCU_MSG_TASK_ACCEPTED = 11
} lunaris_mcu_message_type_t;

typedef enum lunaris_mcu_worker_type {
    LUNARIS_MCU_WORKER_STANDARD = 0,
    LUNARIS_MCU_WORKER_MCU = 1
} lunaris_mcu_worker_type_t;

typedef enum lunaris_mcu_node_state {
    LUNARIS_MCU_NODE_IDLE = 0,
    LUNARIS_MCU_NODE_BUSY = 1
} lunaris_mcu_node_state_t;

typedef enum lunaris_mcu_control_type {
    LUNARIS_MCU_CONTROL_HEARTBEAT = 0,
    LUNARIS_MCU_CONTROL_SHUTDOWN = 1,
    LUNARIS_MCU_CONTROL_CANCEL_TASK = 2,
    LUNARIS_MCU_CONTROL_SET_DRAIN = 3
} lunaris_mcu_control_type_t;

typedef struct lunaris_mcu_host_capabilities {
    size_t count;
    char items[LUNARIS_MCU_CAPABILITIES_MAX][LUNARIS_MCU_CAPABILITY_ITEM_MAX];
} lunaris_mcu_host_capabilities_t;

typedef struct lunaris_mcu_task {
    uint64_t task_id;
    uint32_t attempt;
    char entry[LUNARIS_MCU_ENTRY_MAX];
    char args[LUNARIS_MCU_ARGS_MAX];
    const uint8_t *wasm_module;
    size_t wasm_module_len;
    lunaris_mcu_limits_t execution_limits;
} lunaris_mcu_task_t;

typedef struct lunaris_mcu_task_accepted {
    uint64_t task_id;
    uint32_t attempt;
    char node_id[LUNARIS_MCU_NODE_ID_MAX];
} lunaris_mcu_task_accepted_t;

typedef struct lunaris_mcu_task_result {
    uint64_t task_id;
    uint32_t attempt;
    bool succeeded;
    double duration_ms;
    char result[LUNARIS_MCU_RESULT_MAX];
    uint8_t stdout_data[LUNARIS_MCU_STDIO_MAX];
    size_t stdout_len;
    uint8_t stderr_data[LUNARIS_MCU_STDIO_MAX];
    size_t stderr_len;
} lunaris_mcu_task_result_t;

typedef struct lunaris_mcu_control_command {
    lunaris_mcu_control_type_t type;
    char data[LUNARIS_MCU_ARGS_MAX];
} lunaris_mcu_control_command_t;

typedef struct lunaris_mcu_node_status {
    char node_id[LUNARIS_MCU_NODE_ID_MAX];
    lunaris_mcu_node_state_t state;
    uint32_t current_task;
} lunaris_mcu_node_status_t;

typedef struct lunaris_mcu_node_registration {
    char name[LUNARIS_MCU_NAME_MAX];
    char arch[LUNARIS_MCU_ARCH_MAX];
    uint32_t max_concurrency;
    uint64_t memory_size_mb;
    char token[LUNARIS_MCU_TOKEN_MAX];
    lunaris_mcu_host_capabilities_t provided_capabilities;
    lunaris_mcu_worker_type_t worker_type;
} lunaris_mcu_node_registration_t;

typedef struct lunaris_mcu_node_registration_reply {
    char node_id[LUNARIS_MCU_NODE_ID_MAX];
} lunaris_mcu_node_registration_reply_t;

typedef struct lunaris_mcu_unregister_node {
    char node_id[LUNARIS_MCU_NODE_ID_MAX];
} lunaris_mcu_unregister_node_t;

bool lunaris_mcu_decode_node_registration_reply(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_node_registration_reply_t *reply
);

bool lunaris_mcu_decode_control_command(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_control_command_t *command
);

bool lunaris_mcu_decode_task(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_task_t *task
);

bool lunaris_mcu_encode_envelope(
    lunaris_mcu_message_type_t type,
    bool compressed,
    const pb_msgdesc_t *payload_fields,
    const void *payload,
    uint8_t *out_buffer,
    size_t out_buffer_len,
    size_t *out_size
);

bool lunaris_mcu_decode_envelope_header(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_message_type_t *type,
    bool *compressed
);

#endif
