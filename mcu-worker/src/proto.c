#include "proto.h"

#include <string.h>

#include "common.pb.h"
#include "pb_decode.h"
#include "pb_encode.h"
#include "worker.pb.h"

typedef struct lunaris_mcu_bytes_arg {
    const uint8_t *data;
    size_t size;
} lunaris_mcu_bytes_arg_t;

typedef struct lunaris_mcu_decode_bytes_arg {
    uint8_t *buffer;
    size_t capacity;
    size_t size;
} lunaris_mcu_decode_bytes_arg_t;

typedef struct lunaris_mcu_decode_string_arg {
    char *buffer;
    size_t capacity;
} lunaris_mcu_decode_string_arg_t;

typedef struct lunaris_mcu_task_decode_arg {
    lunaris_mcu_task_t *task;
} lunaris_mcu_task_decode_arg_t;

typedef struct lunaris_mcu_string_list_decode_arg {
    lunaris_mcu_host_capabilities_t *capabilities;
} lunaris_mcu_string_list_decode_arg_t;

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

static bool lunaris_mcu_decode_bytes_callback(pb_istream_t *stream, const pb_field_t *field, void **arg) {
    lunaris_mcu_decode_bytes_arg_t *bytes_arg = (lunaris_mcu_decode_bytes_arg_t *)(*arg);
    size_t bytes_left;

    (void)field;
    if (bytes_arg == NULL) {
        return false;
    }

    bytes_left = stream->bytes_left;
    if (bytes_left > bytes_arg->capacity) {
        return false;
    }
    if (!pb_read(stream, bytes_arg->buffer, bytes_left)) {
        return false;
    }
    bytes_arg->size = bytes_left;
    return true;
}

static bool lunaris_mcu_decode_string_callback(pb_istream_t *stream, const pb_field_t *field, void **arg) {
    lunaris_mcu_decode_string_arg_t *string_arg = (lunaris_mcu_decode_string_arg_t *)(*arg);
    size_t bytes_left;

    (void)field;
    if (string_arg == NULL || string_arg->buffer == NULL || string_arg->capacity == 0U) {
        return false;
    }

    bytes_left = stream->bytes_left;
    if (bytes_left >= string_arg->capacity) {
        return false;
    }
    if (!pb_read(stream, (pb_byte_t *)string_arg->buffer, bytes_left)) {
        return false;
    }
    string_arg->buffer[bytes_left] = '\0';
    return true;
}

static bool lunaris_mcu_decode_string_list_callback(pb_istream_t *stream, const pb_field_t *field, void **arg) {
    lunaris_mcu_string_list_decode_arg_t *list_arg = (lunaris_mcu_string_list_decode_arg_t *)(*arg);
    size_t bytes_left;
    size_t index;

    (void)field;
    if (list_arg == NULL || list_arg->capabilities == NULL) {
        return false;
    }
    if (list_arg->capabilities->count >= LUNARIS_MCU_CAPABILITIES_MAX) {
        return false;
    }

    index = list_arg->capabilities->count;
    bytes_left = stream->bytes_left;
    if (bytes_left >= LUNARIS_MCU_CAPABILITY_ITEM_MAX) {
        return false;
    }
    if (!pb_read(stream, (pb_byte_t *)list_arg->capabilities->items[index], bytes_left)) {
        return false;
    }
    list_arg->capabilities->items[index][bytes_left] = '\0';
    list_arg->capabilities->count++;
    return true;
}

static bool lunaris_mcu_decode_execution_limits(
    const lunaris_common_ExecutionLimits *limits,
    lunaris_mcu_limits_t *out_limits
) {
    if (limits == NULL || out_limits == NULL) {
        return false;
    }

    out_limits->max_fuel = limits->max_fuel;
    out_limits->max_memory_bytes = limits->max_memory_bytes;
    out_limits->max_module_bytes = limits->max_module_bytes;
    return true;
}

static bool lunaris_mcu_decode_envelope_payload(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_common_Envelope *envelope,
    lunaris_mcu_decode_bytes_arg_t *payload_arg
) {
    pb_istream_t stream;

    if (frame == NULL || envelope == NULL || payload_arg == NULL) {
        return false;
    }

    envelope->payload.funcs.decode = lunaris_mcu_decode_bytes_callback;
    envelope->payload.arg = payload_arg;
    stream = pb_istream_from_buffer(frame, frame_len);
    return pb_decode(&stream, lunaris_common_Envelope_fields, envelope);
}

bool lunaris_mcu_encode_envelope(
    lunaris_mcu_message_type_t type,
    bool compressed,
    const pb_msgdesc_t *payload_fields,
    const void *payload,
    uint8_t *out_buffer,
    size_t out_buffer_len,
    size_t *out_size
) {
    uint8_t payload_buffer[LUNARIS_MCU_PROTO_BUFFER_SIZE];
    pb_ostream_t payload_stream;
    pb_ostream_t envelope_stream;
    lunaris_common_Envelope envelope = lunaris_common_Envelope_init_zero;
    lunaris_mcu_bytes_arg_t payload_arg;

    if (payload_fields == NULL || payload == NULL || out_buffer == NULL || out_size == NULL) {
        return false;
    }
    payload_stream = pb_ostream_from_buffer(payload_buffer, sizeof(payload_buffer));
    if (!pb_encode(&payload_stream, payload_fields, payload)) {
        return false;
    }

    envelope.type = (lunaris_common_Envelope_MessageType)type;
    envelope.compressed = compressed;
    payload_arg.data = payload_buffer;
    payload_arg.size = payload_stream.bytes_written;
    envelope.payload.funcs.encode = lunaris_mcu_encode_bytes_callback;
    envelope.payload.arg = &payload_arg;

    envelope_stream = pb_ostream_from_buffer(out_buffer, out_buffer_len);
    if (!pb_encode(&envelope_stream, lunaris_common_Envelope_fields, &envelope)) {
        return false;
    }
    *out_size = envelope_stream.bytes_written;
    return true;
}

bool lunaris_mcu_decode_envelope_header(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_message_type_t *type,
    bool *compressed
) {
    lunaris_common_Envelope envelope = lunaris_common_Envelope_init_zero;
    uint8_t payload_buffer[LUNARIS_MCU_PROTO_BUFFER_SIZE];
    lunaris_mcu_decode_bytes_arg_t payload_arg = {
        .buffer = payload_buffer,
        .capacity = sizeof(payload_buffer),
        .size = 0U,
    };

    if (frame == NULL || type == NULL || compressed == NULL) {
        return false;
    }

    if (!lunaris_mcu_decode_envelope_payload(frame, frame_len, &envelope, &payload_arg)) {
        return false;
    }

    *type = (lunaris_mcu_message_type_t)envelope.type;
    *compressed = envelope.compressed;
    return true;
}

bool lunaris_mcu_decode_node_registration_reply(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_node_registration_reply_t *reply
) {
    lunaris_common_Envelope envelope = lunaris_common_Envelope_init_zero;
    lunaris_worker_NodeRegistrationReply payload = lunaris_worker_NodeRegistrationReply_init_zero;
    uint8_t payload_buffer[LUNARIS_MCU_PROTO_BUFFER_SIZE];
    lunaris_mcu_decode_bytes_arg_t payload_arg = {
        .buffer = payload_buffer,
        .capacity = sizeof(payload_buffer),
        .size = 0U,
    };
    lunaris_mcu_decode_string_arg_t node_id_arg;
    pb_istream_t payload_stream;

    if (reply == NULL) {
        return false;
    }
    memset(reply, 0, sizeof(*reply));
    node_id_arg.buffer = reply->node_id;
    node_id_arg.capacity = sizeof(reply->node_id);
    payload.node_id.funcs.decode = lunaris_mcu_decode_string_callback;
    payload.node_id.arg = &node_id_arg;

    if (!lunaris_mcu_decode_envelope_payload(frame, frame_len, &envelope, &payload_arg)) {
        return false;
    }
    if (envelope.type != lunaris_common_Envelope_MessageType_NODE_REGISTRATION_REPLY) {
        return false;
    }

    payload_stream = pb_istream_from_buffer(payload_buffer, payload_arg.size);
    return pb_decode(&payload_stream, lunaris_worker_NodeRegistrationReply_fields, &payload);
}

bool lunaris_mcu_decode_control_command(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_control_command_t *command
) {
    lunaris_common_Envelope envelope = lunaris_common_Envelope_init_zero;
    lunaris_worker_ControlCommand payload = lunaris_worker_ControlCommand_init_zero;
    uint8_t payload_buffer[LUNARIS_MCU_PROTO_BUFFER_SIZE];
    lunaris_mcu_decode_bytes_arg_t payload_arg = {
        .buffer = payload_buffer,
        .capacity = sizeof(payload_buffer),
        .size = 0U,
    };
    lunaris_mcu_decode_string_arg_t data_arg;
    pb_istream_t payload_stream;

    if (command == NULL) {
        return false;
    }
    memset(command, 0, sizeof(*command));
    data_arg.buffer = command->data;
    data_arg.capacity = sizeof(command->data);
    payload.data.funcs.decode = lunaris_mcu_decode_string_callback;
    payload.data.arg = &data_arg;

    if (!lunaris_mcu_decode_envelope_payload(frame, frame_len, &envelope, &payload_arg)) {
        return false;
    }
    if (envelope.type != lunaris_common_Envelope_MessageType_CONTROL_COMMAND) {
        return false;
    }

    payload_stream = pb_istream_from_buffer(payload_buffer, payload_arg.size);
    if (!pb_decode(&payload_stream, lunaris_worker_ControlCommand_fields, &payload)) {
        return false;
    }
    command->type = (lunaris_mcu_control_type_t)payload.type;
    return true;
}

bool lunaris_mcu_decode_task(
    const uint8_t *frame,
    size_t frame_len,
    lunaris_mcu_task_t *task
) {
    lunaris_common_Envelope envelope = lunaris_common_Envelope_init_zero;
    lunaris_worker_Task payload = lunaris_worker_Task_init_zero;
    static uint8_t wasm_module_storage[LUNARIS_MCU_MAX_MODULE];
    uint8_t payload_buffer[LUNARIS_MCU_PROTO_BUFFER_SIZE];
    lunaris_mcu_decode_bytes_arg_t payload_arg = {
        .buffer = payload_buffer,
        .capacity = sizeof(payload_buffer),
        .size = 0U,
    };
    lunaris_mcu_decode_bytes_arg_t wasm_arg = {
        .buffer = wasm_module_storage,
        .capacity = sizeof(wasm_module_storage),
        .size = 0U,
    };
    lunaris_mcu_decode_string_arg_t args_arg;
    lunaris_mcu_decode_string_arg_t entry_arg;
    lunaris_mcu_string_list_decode_arg_t caps_arg;
    pb_istream_t payload_stream;

    if (task == NULL) {
        return false;
    }
    memset(task, 0, sizeof(*task));

    args_arg.buffer = task->args;
    args_arg.capacity = sizeof(task->args);
    entry_arg.buffer = task->entry;
    entry_arg.capacity = sizeof(task->entry);
    caps_arg.capabilities = &(lunaris_mcu_host_capabilities_t){0};

    payload.wasm_module.funcs.decode = lunaris_mcu_decode_bytes_callback;
    payload.wasm_module.arg = &wasm_arg;
    payload.args.funcs.decode = lunaris_mcu_decode_string_callback;
    payload.args.arg = &args_arg;
    payload.entry.funcs.decode = lunaris_mcu_decode_string_callback;
    payload.entry.arg = &entry_arg;
    payload.host_capabilities.items.funcs.decode = lunaris_mcu_decode_string_list_callback;
    payload.host_capabilities.items.arg = &caps_arg;

    if (!lunaris_mcu_decode_envelope_payload(frame, frame_len, &envelope, &payload_arg)) {
        return false;
    }
    if (envelope.type != lunaris_common_Envelope_MessageType_TASK) {
        return false;
    }

    payload_stream = pb_istream_from_buffer(payload_buffer, payload_arg.size);
    if (!pb_decode(&payload_stream, lunaris_worker_Task_fields, &payload)) {
        return false;
    }

    task->task_id = payload.task_id;
    task->attempt = payload.attempt;
    task->wasm_module = wasm_module_storage;
    task->wasm_module_len = wasm_arg.size;
    if (payload.has_execution_limits) {
        lunaris_mcu_decode_execution_limits(&payload.execution_limits, &task->execution_limits);
    }
    return true;
}
