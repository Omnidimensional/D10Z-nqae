# Pyraclaw-TTA Embedded SDK

SDK ligero para implementar nodos Pyraclaw-TTA en dispositivos IoT, routers y sistemas embebidos.

## Características

- **~50KB footprint** (biblioteca compilada)
- **Sin dependencias externas** (standalone C)
- **API simple** en C puro
- **Plataformas soportadas:**
  - OpenWRT routers
  - ESP32 / ESP8266
  - FreeRTOS
  - Linux embebido
  - Bare-metal ARM/MIPS

## Estructura

```
pyraclaw_sdk/
├── include/
│   └── pyraclaw_sdk.h      # Header principal
├── src/
│   └── pyraclaw_sdk.c      # Implementación
├── examples/
│   └── demo.c          # Ejemplo de uso
├── Makefile
└── README.md
```

## Compilación

```bash
# Biblioteca + demo
make

# Solo biblioteca
make lib

# Ejecutar demo
make run

# Cross-compile ARM (Raspberry Pi)
make arm

# Cross-compile MIPS (OpenWRT routers)
make mips
```

## Uso Básico

```c
#include "pyraclaw_sdk.h"

// Callbacks
void on_send_heartbeat(const pyraclaw_heartbeat_t *hb, void *data) {
    // Enviar por UDP broadcast
}

void on_packet_received(const pyraclaw_packet_t *pkt, void *data) {
    // Procesar paquete recibido
}

int main() {
    // Configurar
    pyraclaw_config_t config;
    pyraclaw_config_default(&config);
    strcpy(config.node_id, "MI-DISPOSITIVO");
    config.callbacks.send_heartbeat = on_send_heartbeat;
    config.callbacks.packet_received = on_packet_received;
    
    // Crear nodo
    pyraclaw_node_t *node = pyraclaw_node_create(&config);
    
    // Loop principal
    while (1) {
        // Procesar heartbeats recibidos
        // ...
        
        // Ejecutar ciclo Pyraclaw (cada 100ms)
        pyraclaw_node_tick(node, get_time_ms());
        
        sleep_ms(10);
    }
    
    pyraclaw_node_destroy(node);
}
```

## Ecuaciones Pyraclaw Implementadas

```
E_TTA = Σ |Zₙ| · Φₙ           (Energía del sistema)

Ley Isis:
∂Φ/∂t = -αΦ + β Σ wΦⱼ / |N|   (Propagación de coherencia)

Parámetros por defecto:
α = 0.05 (decay)
β = 0.20 (coupling)
Φ ≥ 0.70 (umbral operativo)
```

## Integración

### ESP32 (ESP-IDF)

```cmake
# CMakeLists.txt
idf_component_register(
    SRCS "pyraclaw_sdk.c"
    INCLUDE_DIRS "."
)
```

### OpenWRT

```makefile
# packages/pyraclaw-sdk/Makefile
include $(TOPDIR)/rules.mk

PKG_NAME:=pyraclaw-sdk
PKG_VERSION:=1.0.0

include $(INCLUDE_DIR)/package.mk

define Package/pyraclaw-sdk
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=Pyraclaw-TTA Nodal SDK
endef

define Build/Compile
    $(MAKE) -C $(PKG_BUILD_DIR) \
        CC="$(TARGET_CC)" \
        CFLAGS="$(TARGET_CFLAGS)"
endef

$(eval $(call BuildPackage,pyraclaw-sdk))
```

### FreeRTOS

```c
void pyraclaw_task(void *param) {
    pyraclaw_node_t *node = (pyraclaw_node_t*)param;
    
    while (1) {
        pyraclaw_node_tick(node, xTaskGetTickCount());
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

// Crear tarea
xTaskCreate(pyraclaw_task, "Pyraclaw", 4096, node, 5, NULL);
```

## Licencia

CC BY-NC 4.0 (Non-Commercial)

Uso comercial requiere autorización escrita de:
- Byron Callaghan / Pyraclaw
- Byron Callaghan (contact@pyraclaw.institute)

## Autor

Byron Callaghan / Pyraclaw  
Rights Holder: Byron Callaghan
