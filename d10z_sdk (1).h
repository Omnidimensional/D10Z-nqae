/*
 * ══════════════════════════════════════════════════════════════════════════════
 * D10Z-TTA EMBEDDED SDK
 * ══════════════════════════════════════════════════════════════════════════════
 * 
 * SDK ligero para dispositivos IoT, routers y sistemas embebidos.
 * 
 * Características:
 *   - ~50KB footprint
 *   - Sin dependencias externas (standalone)
 *   - Compatible con: OpenWRT, FreeRTOS, bare-metal
 *   - API simple en C
 * 
 * Autor: D10Z Institute
 * Licencia: CC BY-NC 4.0
 * ══════════════════════════════════════════════════════════════════════════════
 */

#ifndef D10Z_SDK_H
#define D10Z_SDK_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════════════════════════════
 * VERSIÓN Y CONSTANTES
 * ═══════════════════════════════════════════════════════════════════════════════
 */

#define D10Z_SDK_VERSION_MAJOR 1
#define D10Z_SDK_VERSION_MINOR 0
#define D10Z_SDK_VERSION_PATCH 0
#define D10Z_SDK_VERSION "1.0.0"

/* Constantes D10Z */
#define D10Z_GM_SCALE           1e-51
#define D10Z_ALPHA_DECAY        0.05
#define D10Z_BETA_COUPLING      0.20

/* Umbrales de coherencia */
#define D10Z_PHI_OPTIMAL        0.90
#define D10Z_PHI_OPERATIONAL    0.70
#define D10Z_PHI_DEGRADED       0.50
#define D10Z_PHI_CRITICAL       0.30

/* Límites del sistema */
#define D10Z_MAX_NEIGHBORS      16
#define D10Z_MAX_NODE_ID_LEN    32
#define D10Z_MAX_PACKET_SIZE    1024
#define D10Z_MAX_HOP_COUNT      10

/* Timing (milisegundos) */
#define D10Z_HEARTBEAT_INTERVAL_MS  100
#define D10Z_CONSENSUS_INTERVAL_MS  5000
#define D10Z_NEIGHBOR_TIMEOUT_MS    3000

/* ═══════════════════════════════════════════════════════════════════════════════
 * TIPOS FUNDAMENTALES
 * ═══════════════════════════════════════════════════════════════════════════════
 */

/**
 * Código de error
 */
typedef enum {
    D10Z_OK = 0,
    D10Z_ERROR_INVALID_PARAM,
    D10Z_ERROR_NO_MEMORY,
    D10Z_ERROR_BUFFER_FULL,
    D10Z_ERROR_NOT_INITIALIZED,
    D10Z_ERROR_NEIGHBOR_NOT_FOUND,
    D10Z_ERROR_TIMEOUT,
    D10Z_ERROR_NETWORK
} d10z_error_t;

/**
 * Nivel de coherencia
 */
typedef enum {
    D10Z_LEVEL_OPTIMAL = 0,
    D10Z_LEVEL_OPERATIONAL,
    D10Z_LEVEL_DEGRADED,
    D10Z_LEVEL_CRITICAL,
    D10Z_LEVEL_ISOLATED
} d10z_level_t;

/**
 * Tipo de conexión
 */
typedef enum {
    D10Z_CONN_WIFI = 0,
    D10Z_CONN_BLUETOOTH,
    D10Z_CONN_ETHERNET,
    D10Z_CONN_LORA,
    D10Z_CONN_CUSTOM
} d10z_conn_type_t;

/**
 * Vector 3D (fixed-point para embebidos)
 */
typedef struct {
    int32_t x;  /* Escalado por 1000 */
    int32_t y;
    int32_t z;
} d10z_vector3_t;

/**
 * Estado nodal Zₙ
 */
typedef struct {
    d10z_vector3_t position;    /* Posición relativa */
    d10z_vector3_t velocity;    /* Velocidad */
    int32_t altitude;           /* Altitud (metros) */
    uint16_t energy;            /* Energía 0-1000 (0.0-1.0 escalado) */
    uint32_t frequency;         /* Frecuencia Hz */
    uint16_t phi;               /* Coherencia 0-1000 (0.0-1.0 escalado) */
} d10z_state_t;

/**
 * Información de vecino
 */
typedef struct {
    char node_id[D10Z_MAX_NODE_ID_LEN];
    d10z_state_t state;
    uint16_t distance_cm;       /* Distancia en centímetros */
    int8_t signal_strength;     /* RSSI en dBm */
    uint32_t last_seen_ms;      /* Timestamp */
    d10z_conn_type_t conn_type;
    bool active;
} d10z_neighbor_t;

/**
 * Mensaje de heartbeat
 */
typedef struct {
    char node_id[D10Z_MAX_NODE_ID_LEN];
    uint32_t timestamp_ms;
    d10z_state_t state;
    uint8_t neighbor_count;
    uint32_t local_e_tta;       /* E_TTA local escalado */
} d10z_heartbeat_t;

/**
 * Paquete de datos
 */
typedef struct {
    char packet_id[16];
    char source_id[D10Z_MAX_NODE_ID_LEN];
    char dest_id[D10Z_MAX_NODE_ID_LEN];
    uint8_t hop_count;
    uint32_t timestamp_ms;
    uint16_t payload_len;
    uint8_t payload[D10Z_MAX_PACKET_SIZE];
} d10z_packet_t;

/**
 * Métricas del nodo
 */
typedef struct {
    uint16_t phi;               /* 0-1000 */
    d10z_level_t level;
    uint8_t neighbor_count;
    uint32_t local_e_tta;
    uint32_t consensus_e_tta;
    uint32_t packets_rx;
    uint32_t packets_tx;
    uint32_t packets_dropped;
    uint32_t uptime_ms;
} d10z_metrics_t;

/* ═══════════════════════════════════════════════════════════════════════════════
 * CALLBACKS
 * ═══════════════════════════════════════════════════════════════════════════════
 */

/**
 * Callback para enviar heartbeat por la red
 */
typedef void (*d10z_send_heartbeat_fn)(const d10z_heartbeat_t *heartbeat, void *user_data);

/**
 * Callback para enviar paquete a un vecino específico
 */
typedef void (*d10z_send_packet_fn)(const d10z_packet_t *packet, const char *neighbor_id, void *user_data);

/**
 * Callback para usar fallback (internet tradicional)
 */
typedef void (*d10z_use_fallback_fn)(const d10z_packet_t *packet, void *user_data);

/**
 * Callback cuando se recibe un paquete para este nodo
 */
typedef void (*d10z_packet_received_fn)(const d10z_packet_t *packet, void *user_data);

/**
 * Callback cuando cambia el nivel de coherencia
 */
typedef void (*d10z_level_changed_fn)(d10z_level_t old_level, d10z_level_t new_level, void *user_data);

/**
 * Callbacks del sistema
 */
typedef struct {
    d10z_send_heartbeat_fn send_heartbeat;
    d10z_send_packet_fn send_packet;
    d10z_use_fallback_fn use_fallback;
    d10z_packet_received_fn packet_received;
    d10z_level_changed_fn level_changed;
    void *user_data;
} d10z_callbacks_t;

/* ═══════════════════════════════════════════════════════════════════════════════
 * CONTEXTO DEL NODO
 * ═══════════════════════════════════════════════════════════════════════════════
 */

/**
 * Contexto del nodo D10Z (opaco)
 */
typedef struct d10z_node d10z_node_t;

/**
 * Configuración del nodo
 */
typedef struct {
    char node_id[D10Z_MAX_NODE_ID_LEN];
    uint16_t initial_phi;           /* 0-1000 */
    uint16_t alpha_decay;           /* 0-1000 (0.05 = 50) */
    uint16_t beta_coupling;         /* 0-1000 (0.20 = 200) */
    uint16_t heartbeat_interval_ms;
    uint16_t neighbor_timeout_ms;
    d10z_callbacks_t callbacks;
} d10z_config_t;

/* ═══════════════════════════════════════════════════════════════════════════════
 * API PRINCIPAL
 * ═══════════════════════════════════════════════════════════════════════════════
 */

/**
 * Obtiene la configuración por defecto
 */
void d10z_config_default(d10z_config_t *config);

/**
 * Crea e inicializa un nodo D10Z
 * 
 * @param config Configuración del nodo
 * @return Puntero al nodo o NULL si error
 */
d10z_node_t* d10z_node_create(const d10z_config_t *config);

/**
 * Destruye un nodo y libera memoria
 */
void d10z_node_destroy(d10z_node_t *node);

/**
 * Ejecuta un ciclo del motor D10Z
 * Debe llamarse periódicamente (cada heartbeat_interval_ms)
 * 
 * @param node Nodo D10Z
 * @param current_time_ms Tiempo actual en milisegundos
 * @return D10Z_OK si éxito
 */
d10z_error_t d10z_node_tick(d10z_node_t *node, uint32_t current_time_ms);

/**
 * Actualiza el estado del nodo
 */
d10z_error_t d10z_node_update_state(d10z_node_t *node, const d10z_state_t *state);

/**
 * Actualiza solo la posición
 */
d10z_error_t d10z_node_update_position(d10z_node_t *node, int32_t lat_e6, int32_t lon_e6, int32_t alt_m);

/**
 * Procesa un heartbeat recibido
 */
d10z_error_t d10z_node_process_heartbeat(
    d10z_node_t *node,
    const d10z_heartbeat_t *heartbeat,
    uint16_t distance_cm,
    int8_t signal_strength,
    d10z_conn_type_t conn_type
);

/**
 * Envía un paquete de datos
 */
d10z_error_t d10z_node_send(
    d10z_node_t *node,
    const char *dest_id,
    const uint8_t *payload,
    uint16_t payload_len
);

/**
 * Procesa un paquete recibido
 */
d10z_error_t d10z_node_receive(d10z_node_t *node, const d10z_packet_t *packet);

/**
 * Obtiene el estado actual
 */
d10z_error_t d10z_node_get_state(const d10z_node_t *node, d10z_state_t *state);

/**
 * Obtiene las métricas
 */
d10z_error_t d10z_node_get_metrics(const d10z_node_t *node, d10z_metrics_t *metrics);

/**
 * Obtiene la lista de vecinos activos
 */
d10z_error_t d10z_node_get_neighbors(
    const d10z_node_t *node,
    d10z_neighbor_t *neighbors,
    uint8_t *count,
    uint8_t max_count
);

/**
 * Obtiene el nivel de coherencia actual
 */
d10z_level_t d10z_node_get_level(const d10z_node_t *node);

/**
 * Obtiene el E_TTA local
 */
uint32_t d10z_node_get_e_tta(const d10z_node_t *node);

/* ═══════════════════════════════════════════════════════════════════════════════
 * UTILIDADES
 * ═══════════════════════════════════════════════════════════════════════════════
 */

/**
 * Convierte phi (0-1000) a nivel
 */
d10z_level_t d10z_phi_to_level(uint16_t phi);

/**
 * Calcula distancia entre dos vectores
 */
uint32_t d10z_vector3_distance(const d10z_vector3_t *a, const d10z_vector3_t *b);

/**
 * Serializa heartbeat a buffer
 */
uint16_t d10z_heartbeat_serialize(const d10z_heartbeat_t *heartbeat, uint8_t *buffer, uint16_t buffer_len);

/**
 * Deserializa heartbeat desde buffer
 */
d10z_error_t d10z_heartbeat_deserialize(const uint8_t *buffer, uint16_t len, d10z_heartbeat_t *heartbeat);

/**
 * Serializa paquete a buffer
 */
uint16_t d10z_packet_serialize(const d10z_packet_t *packet, uint8_t *buffer, uint16_t buffer_len);

/**
 * Deserializa paquete desde buffer
 */
d10z_error_t d10z_packet_deserialize(const uint8_t *buffer, uint16_t len, d10z_packet_t *packet);

/**
 * Estima distancia basada en RSSI
 */
uint16_t d10z_rssi_to_distance_cm(int8_t rssi, int8_t tx_power);

/**
 * Obtiene string del nivel
 */
const char* d10z_level_to_string(d10z_level_t level);

/**
 * Obtiene string del error
 */
const char* d10z_error_to_string(d10z_error_t error);

#ifdef __cplusplus
}
#endif

#endif /* D10Z_SDK_H */
