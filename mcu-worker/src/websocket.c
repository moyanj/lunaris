#include "websocket.h"

#include <string.h>

#ifdef ESP_PLATFORM

#include "esp_event.h"
#include "esp_log.h"
#include "esp_rom_sys.h"

static const char *LUNARIS_MCU_WS_TAG = "lunaris.ws";

static void lunaris_mcu_ws_event_handler(
    void *handler_args,
    esp_event_base_t base,
    int32_t event_id,
    void *event_data
) {
    lunaris_mcu_ws_client_t *client = (lunaris_mcu_ws_client_t *)handler_args;
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;

    (void)base;
    if (client == NULL) {
        return;
    }

    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            client->connected = true;
            break;
        case WEBSOCKET_EVENT_DISCONNECTED:
            client->connected = false;
            client->last_rx_size = 0U;
            break;
        case WEBSOCKET_EVENT_DATA:
            if (data != NULL && data->data_ptr != NULL && data->data_len > 0
                && (size_t)data->data_len <= sizeof(client->rx_buffer)) {
                memcpy(client->rx_buffer, data->data_ptr, (size_t)data->data_len);
                client->last_rx_size = (size_t)data->data_len;
            }
            break;
        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(LUNARIS_MCU_WS_TAG, "websocket error");
            break;
        default:
            break;
    }
}

bool lunaris_mcu_ws_connect(lunaris_mcu_ws_client_t *client, const char *uri) {
    esp_websocket_client_config_t config = {0};
    uint32_t retry;

    if (client == NULL || uri == NULL) {
        return false;
    }
    if (client->connected) {
        return true;
    }

    memset(client, 0, sizeof(*client));
    strncpy(client->uri, uri, sizeof(client->uri) - 1U);
    config.uri = client->uri;
    config.disable_auto_reconnect = false;
    config.network_timeout_ms = 10000;

    client->handle = esp_websocket_client_init(&config);
    if (client->handle == NULL) {
        return false;
    }
    if (esp_websocket_register_events(
            client->handle,
            WEBSOCKET_EVENT_ANY,
            lunaris_mcu_ws_event_handler,
            client) != ESP_OK) {
        esp_websocket_client_destroy(client->handle);
        client->handle = NULL;
        return false;
    }
    if (esp_websocket_client_start(client->handle) != ESP_OK) {
        esp_websocket_client_destroy(client->handle);
        client->handle = NULL;
        return false;
    }

    for (retry = 0; retry < 100U; ++retry) {
        if (client->connected) {
            return true;
        }
        esp_rom_delay_us(10000);
    }
    return false;
}

bool lunaris_mcu_ws_send(lunaris_mcu_ws_client_t *client, const uint8_t *data, size_t len) {
    int sent;

    if (client == NULL || data == NULL || !client->connected || client->handle == NULL || len > sizeof(client->tx_buffer)) {
        return false;
    }

    memcpy(client->tx_buffer, data, len);
    client->last_tx_size = len;
    sent = esp_websocket_client_send_bin(client->handle, (const char *)data, (int)len, portMAX_DELAY);
    return sent == (int)len;
}

bool lunaris_mcu_ws_recv(lunaris_mcu_ws_client_t *client, uint8_t *buffer, size_t buffer_len, size_t *received) {
    uint32_t retry;

    if (client == NULL || buffer == NULL || received == NULL || !client->connected) {
        return false;
    }

    for (retry = 0; retry < LUNARIS_MCU_WS_RECV_POLL_MS; ++retry) {
        if (client->last_rx_size > 0U) {
            break;
        }
        esp_rom_delay_us(1000);
    }

    if (client->last_rx_size == 0U || client->last_rx_size > buffer_len) {
        *received = 0U;
        return false;
    }

    memcpy(buffer, client->rx_buffer, client->last_rx_size);
    *received = client->last_rx_size;
    client->last_rx_size = 0U;
    return true;
}

bool lunaris_mcu_ws_push_rx_frame(lunaris_mcu_ws_client_t *client, const uint8_t *data, size_t len) {
    (void)client;
    (void)data;
    (void)len;
    return false;
}

void lunaris_mcu_ws_close(lunaris_mcu_ws_client_t *client) {
    if (client == NULL) {
        return;
    }
    if (client->handle != NULL) {
        esp_websocket_client_stop(client->handle);
        esp_websocket_client_destroy(client->handle);
        client->handle = NULL;
    }
    client->connected = false;
    client->last_rx_size = 0U;
    client->last_tx_size = 0U;
}

#else

bool lunaris_mcu_ws_connect(lunaris_mcu_ws_client_t *client, const char *uri) {
    if (client == NULL || uri == NULL) {
        return false;
    }

    memset(client, 0, sizeof(*client));
    strncpy(client->uri, uri, sizeof(client->uri) - 1U);
    client->connected = true;
    return true;
}

bool lunaris_mcu_ws_send(lunaris_mcu_ws_client_t *client, const uint8_t *data, size_t len) {
    if (client == NULL || data == NULL || !client->connected || len > sizeof(client->tx_buffer)) {
        return false;
    }

    memcpy(client->tx_buffer, data, len);
    client->last_tx_size = len;
    return true;
}

bool lunaris_mcu_ws_recv(lunaris_mcu_ws_client_t *client, uint8_t *buffer, size_t buffer_len, size_t *received) {
    if (client == NULL || buffer == NULL || received == NULL || !client->connected) {
        return false;
    }

    if (client->last_rx_size == 0U || client->last_rx_size > buffer_len) {
        *received = 0U;
        return false;
    }

    memcpy(buffer, client->rx_buffer, client->last_rx_size);
    *received = client->last_rx_size;
    client->last_rx_size = 0U;
    return true;
}

bool lunaris_mcu_ws_push_rx_frame(lunaris_mcu_ws_client_t *client, const uint8_t *data, size_t len) {
    if (client == NULL || data == NULL || len > sizeof(client->rx_buffer)) {
        return false;
    }

    memcpy(client->rx_buffer, data, len);
    client->last_rx_size = len;
    return true;
}

void lunaris_mcu_ws_close(lunaris_mcu_ws_client_t *client) {
    if (client == NULL) {
        return;
    }
    client->connected = false;
    client->last_rx_size = 0U;
    client->last_tx_size = 0U;
}

#endif
