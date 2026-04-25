#include "wifi.h"

#ifdef ESP_PLATFORM

#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

static const char *LUNARIS_MCU_WIFI_TAG = "lunaris.wifi";
static EventGroupHandle_t lunaris_mcu_wifi_events;

#define LUNARIS_MCU_WIFI_CONNECTED_BIT BIT0
#define LUNARIS_MCU_WIFI_FAIL_BIT BIT1

static void lunaris_mcu_wifi_event_handler(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data
) {
    (void)arg;
    (void)event_data;

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        return;
    }

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();
        xEventGroupSetBits(lunaris_mcu_wifi_events, LUNARIS_MCU_WIFI_FAIL_BIT);
        return;
    }

    if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(lunaris_mcu_wifi_events, LUNARIS_MCU_WIFI_CONNECTED_BIT);
    }
}

bool lunaris_mcu_wifi_connect(void) {
    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    wifi_config_t wifi_cfg = {0};
    EventBits_t bits;

    if (CONFIG_LUNARIS_WIFI_SSID[0] == '\0') {
        ESP_LOGE(LUNARIS_MCU_WIFI_TAG, "CONFIG_LUNARIS_WIFI_SSID is empty");
        return false;
    }

    lunaris_mcu_wifi_events = xEventGroupCreate();
    if (lunaris_mcu_wifi_events == NULL) {
        return false;
    }

    if (esp_netif_init() != ESP_OK) {
        return false;
    }
    if (esp_event_loop_create_default() != ESP_OK) {
        return false;
    }
    esp_netif_create_default_wifi_sta();

    if (esp_wifi_init(&init_cfg) != ESP_OK) {
        return false;
    }
    if (esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &lunaris_mcu_wifi_event_handler, NULL) != ESP_OK) {
        return false;
    }
    if (esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &lunaris_mcu_wifi_event_handler, NULL) != ESP_OK) {
        return false;
    }

    memcpy(wifi_cfg.sta.ssid, CONFIG_LUNARIS_WIFI_SSID, strlen(CONFIG_LUNARIS_WIFI_SSID));
    memcpy(wifi_cfg.sta.password, CONFIG_LUNARIS_WIFI_PASSWORD, strlen(CONFIG_LUNARIS_WIFI_PASSWORD));
    wifi_cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    if (esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK) {
        return false;
    }
    if (esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg) != ESP_OK) {
        return false;
    }
    if (esp_wifi_start() != ESP_OK) {
        return false;
    }

    bits = xEventGroupWaitBits(
        lunaris_mcu_wifi_events,
        LUNARIS_MCU_WIFI_CONNECTED_BIT | LUNARIS_MCU_WIFI_FAIL_BIT,
        pdFALSE,
        pdFALSE,
        pdMS_TO_TICKS(15000)
    );

    if ((bits & LUNARIS_MCU_WIFI_CONNECTED_BIT) != 0) {
        ESP_LOGI(LUNARIS_MCU_WIFI_TAG, "wifi connected");
        return true;
    }

    ESP_LOGE(LUNARIS_MCU_WIFI_TAG, "wifi connect failed");
    return false;
}

#else

bool lunaris_mcu_wifi_connect(void) {
    return false;
}

#endif
