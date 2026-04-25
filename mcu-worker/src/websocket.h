#ifndef LUNARIS_MCU_WEBSOCKET_H
#define LUNARIS_MCU_WEBSOCKET_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "config.h"

#ifdef ESP_PLATFORM
#include "esp_websocket_client.h"
#endif

typedef struct lunaris_mcu_ws_client {
    bool connected;
    char uri[128];
    uint8_t rx_buffer[LUNARIS_MCU_WS_BUFFER_SIZE];
    uint8_t tx_buffer[LUNARIS_MCU_WS_BUFFER_SIZE];
    size_t last_rx_size;
    size_t last_tx_size;
#ifdef ESP_PLATFORM
    esp_websocket_client_handle_t handle;
#endif
} lunaris_mcu_ws_client_t;

bool lunaris_mcu_ws_connect(lunaris_mcu_ws_client_t *client, const char *uri);
bool lunaris_mcu_ws_send(lunaris_mcu_ws_client_t *client, const uint8_t *data, size_t len);
bool lunaris_mcu_ws_recv(lunaris_mcu_ws_client_t *client, uint8_t *buffer, size_t buffer_len, size_t *received);
bool lunaris_mcu_ws_push_rx_frame(lunaris_mcu_ws_client_t *client, const uint8_t *data, size_t len);
void lunaris_mcu_ws_close(lunaris_mcu_ws_client_t *client);

#endif
