#include "worker.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common.pb.h"
#include "pb_encode.h"
#include "worker.pb.h"

static void lunaris_mcu_copy_string(char *dst, size_t dst_len, const char *src) {
    if (dst == NULL || dst_len == 0U) {
        return;
    }
    if (src == NULL) {
        dst[0] = '\0';
        return;
    }
    strncpy(dst, src, dst_len - 1U);
    dst[dst_len - 1U] = '\0';
}

typedef struct lunaris_mcu_string_arg {
    const char *value;
} lunaris_mcu_string_arg_t;

typedef struct lunaris_mcu_string_list_arg {
    size_t count;
    char (*items)[LUNARIS_MCU_CAPABILITY_ITEM_MAX];
} lunaris_mcu_string_list_arg_t;

typedef struct lunaris_mcu_bytes_arg {
    const uint8_t *data;
    size_t size;
} lunaris_mcu_bytes_arg_t;

static bool lunaris_mcu_encode_string_callback(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
    const lunaris_mcu_string_arg_t *string_arg = (const lunaris_mcu_string_arg_t *)(*arg);
    size_t len;

    if (string_arg == NULL || string_arg->value == NULL) {
        return false;
    }
    len = strlen(string_arg->value);
    if (!pb_encode_tag_for_field(stream, field)) {
        return false;
    }
    return pb_encode_string(stream, (const pb_byte_t *)string_arg->value, len);
}

static bool lunaris_mcu_encode_bytes_callback(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
    const lunaris_mcu_bytes_arg_t *bytes_arg = (const lunaris_mcu_bytes_arg_t *)(*arg);

    if (bytes_arg == NULL || bytes_arg->data == NULL) {
        return false;
    }
    if (!pb_encode_tag_for_field(stream, field)) {
        return false;
    }
    return pb_encode_string(stream, bytes_arg->data, bytes_arg->size);
}

static bool lunaris_mcu_encode_string_list_callback(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
    const lunaris_mcu_string_list_arg_t *list_arg = (const lunaris_mcu_string_list_arg_t *)(*arg);
    size_t i;

    if (list_arg == NULL) {
        return false;
    }
    for (i = 0; i < list_arg->count; ++i) {
        size_t len = strlen(list_arg->items[i]);
        if (!pb_encode_tag_for_field(stream, field)) {
            return false;
        }
        if (!pb_encode_string(stream, (const pb_byte_t *)list_arg->items[i], len)) {
            return false;
        }
    }
    return true;
}

static bool lunaris_mcu_send_proto_frame(
    lunaris_mcu_worker_t *worker,
    lunaris_mcu_message_type_t type,
    const pb_msgdesc_t *fields,
    const void *message
) {
    uint8_t frame[LUNARIS_MCU_WS_BUFFER_SIZE];
    size_t frame_len = 0U;

    if (!lunaris_mcu_encode_envelope(
            type,
            worker->config.use_compression,
            fields,
            message,
            frame,
            sizeof(frame),
            &frame_len)) {
        return false;
    }

    return lunaris_mcu_ws_send(&worker->ws, frame, frame_len);
}

void lunaris_mcu_worker_config_init_defaults(lunaris_mcu_worker_config_t *config) {
    lunaris_mcu_platform_info_t info;

    if (config == NULL) {
        return;
    }

    memset(config, 0, sizeof(*config));
    config->master_uri = LUNARIS_MCU_MASTER_URI;
    config->token = LUNARIS_MCU_WORKER_TOKEN;
    lunaris_mcu_copy_string(config->name_storage, sizeof(config->name_storage), LUNARIS_MCU_WORKER_NAME);
    lunaris_mcu_copy_string(config->arch_storage, sizeof(config->arch_storage), LUNARIS_MCU_WORKER_ARCH);
    config->name = config->name_storage;
    config->arch = config->arch_storage;
    config->memory_size_mb = LUNARIS_MCU_MEMORY_SIZE_MB;
    config->max_concurrency = 1U;
    config->use_compression = false;
    config->default_limits = lunaris_mcu_default_limits();
    config->max_limits = lunaris_mcu_max_limits();

    if (lunaris_mcu_platform_get_info(&info)) {
        if (info.worker_name[0] != '\0') {
            lunaris_mcu_copy_string(config->name_storage, sizeof(config->name_storage), info.worker_name);
        }
        if (info.arch[0] != '\0') {
            lunaris_mcu_copy_string(config->arch_storage, sizeof(config->arch_storage), info.arch);
        }
        if (info.memory_size_mb > 0U) {
            config->memory_size_mb = info.memory_size_mb;
        }
    }
}

bool lunaris_mcu_worker_init(lunaris_mcu_worker_t *worker, const lunaris_mcu_worker_config_t *config) {
    if (worker == NULL || config == NULL || config->master_uri == NULL || config->token == NULL) {
        return false;
    }

    memset(worker, 0, sizeof(*worker));
    worker->config = *config;
    if (worker->config.max_concurrency == 0U) {
        worker->config.max_concurrency = 1U;
    }

    if (!lunaris_mcu_engine_init(&worker->engine, worker->config.default_limits, worker->config.max_limits)) {
        return false;
    }

    worker->running = true;
    return true;
}

bool lunaris_mcu_worker_connect(lunaris_mcu_worker_t *worker) {
    if (worker == NULL) {
        return false;
    }
    if (worker->ws.connected) {
        return true;
    }
    return lunaris_mcu_ws_connect(&worker->ws, worker->config.master_uri);
}

bool lunaris_mcu_worker_register(lunaris_mcu_worker_t *worker) {
    lunaris_worker_NodeRegistration registration = lunaris_worker_NodeRegistration_init_zero;
    lunaris_mcu_string_arg_t name_arg = { worker->config.name };
    lunaris_mcu_string_arg_t arch_arg = { worker->config.arch };
    lunaris_mcu_string_arg_t token_arg = { worker->config.token };
    lunaris_mcu_string_list_arg_t capabilities_arg = {
        .count = worker->config.provided_capabilities.count,
        .items = worker->config.provided_capabilities.items,
    };

    if (worker == NULL) {
        return false;
    }

    registration.max_concurrency = worker->config.max_concurrency;
    registration.memory_size = worker->config.memory_size_mb;
    registration.type = worker->config.use_compression
        ? lunaris_worker_NodeRegistration_WorkerType_STANDARD
        : lunaris_worker_NodeRegistration_WorkerType_MCU;
    registration.name.funcs.encode = lunaris_mcu_encode_string_callback;
    registration.name.arg = &name_arg;
    registration.arch.funcs.encode = lunaris_mcu_encode_string_callback;
    registration.arch.arg = &arch_arg;
    registration.token.funcs.encode = lunaris_mcu_encode_string_callback;
    registration.token.arg = &token_arg;
    registration.has_provided_capabilities = worker->config.provided_capabilities.count > 0U;
    if (registration.has_provided_capabilities) {
        registration.provided_capabilities.items.funcs.encode = lunaris_mcu_encode_string_list_callback;
        registration.provided_capabilities.items.arg = &capabilities_arg;
    }

    uint8_t frame[LUNARIS_MCU_WS_BUFFER_SIZE];
    size_t frame_len = 0U;
    lunaris_mcu_node_registration_reply_t reply;

    if (!lunaris_mcu_encode_envelope(
            LUNARIS_MCU_MSG_NODE_REGISTRATION,
            worker->config.use_compression,
            lunaris_worker_NodeRegistration_fields,
            &registration,
            frame,
            sizeof(frame),
            &frame_len)) {
        return false;
    }
    if (!lunaris_mcu_ws_send(&worker->ws, frame, frame_len)) {
        return false;
    }
    if (!lunaris_mcu_ws_recv(&worker->ws, frame, sizeof(frame), &frame_len)) {
        return false;
    }
    if (!lunaris_mcu_decode_node_registration_reply(frame, frame_len, &reply)) {
        return false;
    }

    lunaris_mcu_copy_string(worker->node_id, sizeof(worker->node_id), reply.node_id);
    worker->registration_complete = true;
    return true;
}

bool lunaris_mcu_worker_send_heartbeat(lunaris_mcu_worker_t *worker) {
    lunaris_worker_NodeStatus status = lunaris_worker_NodeStatus_init_zero;
    lunaris_mcu_string_arg_t node_id_arg = { worker->node_id };

    if (worker == NULL || !worker->ws.connected) {
        return false;
    }

    status.node_id.funcs.encode = lunaris_mcu_encode_string_callback;
    status.node_id.arg = &node_id_arg;
    status.current_task = worker->current_task;
    status.status = worker->current_task >= worker->config.max_concurrency
        ? lunaris_worker_NodeStatus_NodeState_BUSY
        : lunaris_worker_NodeStatus_NodeState_IDLE;

    return lunaris_mcu_send_proto_frame(
        worker,
        LUNARIS_MCU_MSG_NODE_STATUS,
        lunaris_worker_NodeStatus_fields,
        &status
    );
}

static bool lunaris_mcu_worker_send_task_accepted(
    lunaris_mcu_worker_t *worker,
    const lunaris_mcu_task_t *task
) {
    lunaris_worker_TaskAccepted accepted = lunaris_worker_TaskAccepted_init_zero;
    lunaris_mcu_string_arg_t node_id_arg = { worker->node_id };

    accepted.task_id = task->task_id;
    accepted.attempt = task->attempt;
    accepted.node_id.funcs.encode = lunaris_mcu_encode_string_callback;
    accepted.node_id.arg = &node_id_arg;

    return lunaris_mcu_send_proto_frame(
        worker,
        LUNARIS_MCU_MSG_TASK_ACCEPTED,
        lunaris_worker_TaskAccepted_fields,
        &accepted
    );
}

static bool lunaris_mcu_worker_send_result(
    lunaris_mcu_worker_t *worker,
    const lunaris_mcu_task_result_t *task_result
) {
    lunaris_common_TaskResult result = lunaris_common_TaskResult_init_zero;
    lunaris_mcu_string_arg_t result_arg = { task_result->result };
    lunaris_mcu_bytes_arg_t stdout_arg = { task_result->stdout_data, task_result->stdout_len };
    lunaris_mcu_bytes_arg_t stderr_arg = { task_result->stderr_data, task_result->stderr_len };

    result.task_id = task_result->task_id;
    result.time = task_result->duration_ms;
    result.succeeded = task_result->succeeded;
    result.attempt = task_result->attempt;
    result.result.funcs.encode = lunaris_mcu_encode_string_callback;
    result.result.arg = &result_arg;
    result.stdout.funcs.encode = lunaris_mcu_encode_bytes_callback;
    result.stdout.arg = &stdout_arg;
    result.stderr.funcs.encode = lunaris_mcu_encode_bytes_callback;
    result.stderr.arg = &stderr_arg;

    return lunaris_mcu_send_proto_frame(
        worker,
        LUNARIS_MCU_MSG_TASK_RESULT,
        lunaris_common_TaskResult_fields,
        &result
    );
}

bool lunaris_mcu_worker_handle_task(lunaris_mcu_worker_t *worker, const lunaris_mcu_task_t *task) {
    lunaris_mcu_engine_result_t engine_result;
    lunaris_mcu_task_result_t task_result;

    if (worker == NULL || task == NULL || !worker->running) {
        return false;
    }

    memset(&task_result, 0, sizeof(task_result));

    if (worker->drain_enabled || (worker->task_cancelled && worker->cancelled_task_id == task->task_id)) {
        task_result.task_id = task->task_id;
        task_result.attempt = task->attempt;
        snprintf((char *)task_result.stderr_data, sizeof(task_result.stderr_data), "task cancelled");
        task_result.stderr_len = strlen((const char *)task_result.stderr_data);
        task_result.succeeded = false;
        return lunaris_mcu_worker_send_result(worker, &task_result);
    }

    if (!lunaris_mcu_worker_send_task_accepted(worker, task)) {
        return false;
    }

    worker->current_task = 1U;
    if (!lunaris_mcu_engine_exec(&worker->engine, task, &engine_result)) {
        worker->current_task = 0U;
        return false;
    }

    task_result.task_id = task->task_id;
    task_result.attempt = task->attempt;
    task_result.succeeded = engine_result.succeeded;
    task_result.duration_ms = engine_result.duration_ms;
    lunaris_mcu_copy_string(task_result.result, sizeof(task_result.result), engine_result.result);
    memcpy(task_result.stdout_data, engine_result.stdout_data, engine_result.stdout_len);
    memcpy(task_result.stderr_data, engine_result.stderr_data, engine_result.stderr_len);
    task_result.stdout_len = engine_result.stdout_len;
    task_result.stderr_len = engine_result.stderr_len;

    worker->current_task = 0U;
    return lunaris_mcu_worker_send_result(worker, &task_result);
}

bool lunaris_mcu_worker_handle_control(lunaris_mcu_worker_t *worker, const lunaris_mcu_control_command_t *command) {
    if (worker == NULL || command == NULL) {
        return false;
    }

    switch (command->type) {
        case LUNARIS_MCU_CONTROL_SHUTDOWN:
            worker->running = false;
            return true;
        case LUNARIS_MCU_CONTROL_SET_DRAIN:
            worker->drain_enabled = strstr(command->data, "true") != NULL;
            return true;
        case LUNARIS_MCU_CONTROL_CANCEL_TASK:
            worker->task_cancelled = true;
            worker->cancelled_task_id = (uint64_t)strtoull(command->data, NULL, 10);
            return true;
        case LUNARIS_MCU_CONTROL_HEARTBEAT:
            return lunaris_mcu_worker_send_heartbeat(worker);
        default:
            return false;
    }
}

bool lunaris_mcu_worker_run_once(lunaris_mcu_worker_t *worker) {
    if (worker == NULL) {
        return false;
    }

    if (!lunaris_mcu_worker_connect(worker)) {
        return false;
    }
    if (!lunaris_mcu_worker_register(worker)) {
        return false;
    }
    return lunaris_mcu_worker_send_heartbeat(worker);
}

bool lunaris_mcu_worker_poll_once(lunaris_mcu_worker_t *worker) {
    uint8_t frame[LUNARIS_MCU_WS_BUFFER_SIZE];
    size_t frame_len = 0U;
    lunaris_mcu_message_type_t type;
    bool compressed = false;

    if (worker == NULL || !worker->running) {
        return false;
    }
    if (!lunaris_mcu_ws_recv(&worker->ws, frame, sizeof(frame), &frame_len)) {
        return false;
    }
    if (!lunaris_mcu_decode_envelope_header(frame, frame_len, &type, &compressed)) {
        return false;
    }
    if (compressed) {
        return false;
    }

    if (type == LUNARIS_MCU_MSG_TASK) {
        lunaris_mcu_task_t task;
        if (!lunaris_mcu_decode_task(frame, frame_len, &task)) {
            return false;
        }
        return lunaris_mcu_worker_handle_task(worker, &task);
    }

    if (type == LUNARIS_MCU_MSG_CONTROL_COMMAND) {
        lunaris_mcu_control_command_t command;
        if (!lunaris_mcu_decode_control_command(frame, frame_len, &command)) {
            return false;
        }
        return lunaris_mcu_worker_handle_control(worker, &command);
    }

    return false;
}

bool lunaris_mcu_worker_run(lunaris_mcu_worker_t *worker) {
    uint32_t last_heartbeat_ms;

    if (!worker->registration_complete) {
        if (!lunaris_mcu_worker_run_once(worker)) {
            return false;
        }
    }

    last_heartbeat_ms = lunaris_mcu_platform_millis();
    while (worker->running) {
        uint32_t now_ms = lunaris_mcu_platform_millis();

        if ((uint32_t)(now_ms - last_heartbeat_ms) >= LUNARIS_MCU_HEARTBEAT_INTERVAL_MS) {
            if (!lunaris_mcu_worker_send_heartbeat(worker)) {
                return false;
            }
            last_heartbeat_ms = now_ms;
        }

        if (!lunaris_mcu_worker_poll_once(worker)) {
            lunaris_mcu_platform_delay_ms(10U);
        }
    }
    return true;
}

void lunaris_mcu_worker_shutdown(lunaris_mcu_worker_t *worker) {
    if (worker == NULL) {
        return;
    }
    worker->running = false;
    lunaris_mcu_ws_close(&worker->ws);
    lunaris_mcu_engine_shutdown(&worker->engine);
}
