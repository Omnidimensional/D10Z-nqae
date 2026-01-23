# D10Z-TTA Embedded SDK

SDK ligero para implementar nodos D10Z-TTA en dispositivos IoT, routers y sistemas embebidos.

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
d10z_sdk/
├── include/
│   └── d10z_sdk.h      # Header principal
├── src/
│   └── d10z_sdk.c      # Implementación
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
#include "d10z_sdk.h"

// Callbacks
void on_send_heartbeat(const d10z_heartbeat_t *hb, void *data) {
    // Enviar por UDP broadcast
}

void on_packet_received(const d10z_packet_t *pkt, void *data) {
    // Procesar paquete recibido
}

int main() {
    // Configurar
    d10z_config_t config;
    d10z_config_default(&config);
    strcpy(config.node_id, "MI-DISPOSITIVO");
    config.callbacks.send_heartbeat = on_send_heartbeat;
    config.callbacks.packet_received = on_packet_received;
    
    // Crear nodo
    d10z_node_t *node = d10z_node_create(&config);
    
    // Loop principal
    while (1) {
        // Procesar heartbeats recibidos
        // ...
        
        // Ejecutar ciclo D10Z (cada 100ms)
        d10z_node_tick(node, get_time_ms());
        
        sleep_ms(10);
    }
    
    d10z_node_destroy(node);
}
```

## Ecuaciones D10Z Implementadas

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
    SRCS "d10z_sdk.c"
    INCLUDE_DIRS "."
)
```

### OpenWRT

```makefile
# packages/d10z-sdk/Makefile
include $(TOPDIR)/rules.mk

PKG_NAME:=d10z-sdk
PKG_VERSION:=1.0.0

include $(INCLUDE_DIR)/package.mk

define Package/d10z-sdk
  SECTION:=libs
  CATEGORY:=Libraries
  TITLE:=D10Z-TTA Nodal SDK
endef

define Build/Compile
    $(MAKE) -C $(PKG_BUILD_DIR) \
        CC="$(TARGET_CC)" \
        CFLAGS="$(TARGET_CFLAGS)"
endef

$(eval $(call BuildPackage,d10z-sdk))
```

### FreeRTOS

```c
void d10z_task(void *param) {
    d10z_node_t *node = (d10z_node_t*)param;
    
    while (1) {
        d10z_node_tick(node, xTaskGetTickCount());
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

// Crear tarea
xTaskCreate(d10z_task, "D10Z", 4096, node, 5, NULL);
```

## Licencia

CC BY-NC 4.0 (Non-Commercial)

Uso comercial requiere autorización escrita de:
- D10Z Institute
- Jamil Al Thani (jamil@d10z.org)

## Autor

D10Z Institute  
ORCID: 0009-0000-8858-4992
