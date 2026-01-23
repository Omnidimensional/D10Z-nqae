/*
 * ══════════════════════════════════════════════════════════════════════════════
 * D10Z-TTA EMBEDDED SDK - IMPLEMENTACIÓN
 * ══════════════════════════════════════════════════════════════════════════════
 */

#include "d10z_sdk.h"
#include <string.h>
#include <stdlib.h>

/* ═══════════════════════════════════════════════════════════════════════════════
 * ESTRUCTURA INTERNA DEL NODO
 * ═══════════════════════════════════════════════════════════════════════════════
 */

struct d10z_node {
    char node_id[D10Z_MAX_NODE_ID_LEN];
    d10z_state_t state;
    d10z_neighbor_t neighbors[D10Z_MAX_NEIGHBORS];
    uint8_t neighbor_count;
    
    uint16_t alpha_decay;
    uint16_t beta_coupling;
    uint16_t heartbeat_interval_ms;
    uint16_t neighbor_timeout_ms;
    
    uint32_t last_heartbeat_ms;
    uint32_t last_consensus_ms;
    uint32_t start_time_ms;
    
    uint32_t local_e_tta;
    uint32_t consensus_e_tta;
    uint32_t packets_rx;
    uint32_t packets_tx;
    uint32_t packets_dropped;
    
    d10z_callbacks_t callbacks;
    bool initialized;
};

/* ═══════════════════════════════════════════════════════════════════════════════
 * FUNCIONES INTERNAS
 * ═══════════════════════════════════════════════════════════════════════════════
 */

static uint32_t isqrt(uint32_t n) {
    if (n == 0) return 0;
    uint32_t x = n, y = (x + 1) / 2;
    while (y < x) { x = y; y = (x + n / x) / 2; }
    return x;
}

static uint32_t vector3_magnitude(const d10z_vector3_t *v) {
    int64_t sum = (int64_t)v->x * v->x + (int64_t)v->y * v->y + (int64_t)v->z * v->z;
    return isqrt((uint32_t)(sum / 1000000));
}

static void prune_inactive_neighbors(d10z_node_t *node, uint32_t current_time_ms) {
    for (int i = 0; i < node->neighbor_count; ) {
        uint32_t age = current_time_ms - node->neighbors[i].last_seen_ms;
        if (age > node->neighbor_timeout_ms) {
            node->neighbors[i].active = false;
            if (i < node->neighbor_count - 1) {
                node->neighbors[i] = node->neighbors[node->neighbor_count - 1];
            }
            node->neighbor_count--;
        } else {
            i++;
        }
    }
}

static void propagate_coherence(d10z_node_t *node) {
    if (node->neighbor_count == 0) {
        uint32_t decay = (node->state.phi * node->alpha_decay) / 1000;
        if (node->state.phi > decay / 10) {
            node->state.phi -= decay / 10;
        }
        return;
    }
    
    uint32_t decay = (node->state.phi * node->alpha_decay) / 1000;
    uint32_t coupling_sum = 0, weight_sum = 0;
    
    for (int i = 0; i < node->neighbor_count; i++) {
        if (!node->neighbors[i].active) continue;
        uint32_t weight = 10000 / (node->neighbors[i].distance_cm + 100);
        coupling_sum += weight * node->neighbors[i].state.phi / 1000;
        weight_sum += weight;
    }
    
    uint32_t coupling = 0;
    if (weight_sum > 0) {
        coupling = (node->beta_coupling * coupling_sum) / weight_sum;
    }
    
    int32_t delta_phi = (-((int32_t)decay) + (int32_t)coupling) / 10;
    int32_t new_phi = (int32_t)node->state.phi + delta_phi;
    
    if (new_phi < 0) new_phi = 0;
    if (new_phi > 1000) new_phi = 1000;
    node->state.phi = (uint16_t)new_phi;
}

static void compute_local_e_tta(d10z_node_t *node) {
    uint32_t magnitude = vector3_magnitude(&node->state.position);
    uint32_t e_tta = (magnitude * node->state.phi) / 1000;
    
    for (int i = 0; i < node->neighbor_count; i++) {
        if (!node->neighbors[i].active) continue;
        uint32_t n_mag = vector3_magnitude(&node->neighbors[i].state.position);
        e_tta += (n_mag * node->neighbors[i].state.phi) / 1000;
    }
    node->local_e_tta = e_tta;
}

static int find_neighbor(d10z_node_t *node, const char *node_id) {
    for (int i = 0; i < node->neighbor_count; i++) {
        if (strcmp(node->neighbors[i].node_id, node_id) == 0) return i;
    }
    return -1;
}

static const char* find_best_next_hop(d10z_node_t *node, const char *dest_id) {
    int best_idx = -1;
    uint32_t best_score = 0;
    
    for (int i = 0; i < node->neighbor_count; i++) {
        if (!node->neighbors[i].active) continue;
        if (node->neighbors[i].state.phi < 700) continue; /* PHI_OPERATIONAL */
        
        uint32_t score = node->neighbors[i].state.phi * (100 + node->neighbors[i].signal_strength) / 100;
        if (score > best_score) {
            best_score = score;
            best_idx = i;
        }
    }
    
    return (best_idx >= 0) ? node->neighbors[best_idx].node_id : NULL;
}

/* ═══════════════════════════════════════════════════════════════════════════════
 * API PÚBLICA
 * ═══════════════════════════════════════════════════════════════════════════════
 */

void d10z_config_default(d10z_config_t *config) {
    memset(config, 0, sizeof(*config));
    strcpy(config->node_id, "D10Z-NODE");
    config->initial_phi = 500;
    config->alpha_decay = 50;
    config->beta_coupling = 200;
    config->heartbeat_interval_ms = D10Z_HEARTBEAT_INTERVAL_MS;
    config->neighbor_timeout_ms = D10Z_NEIGHBOR_TIMEOUT_MS;
}

d10z_node_t* d10z_node_create(const d10z_config_t *config) {
    if (!config) return NULL;
    
    d10z_node_t *node = (d10z_node_t*)malloc(sizeof(d10z_node_t));
    if (!node) return NULL;
    
    memset(node, 0, sizeof(*node));
    strncpy(node->node_id, config->node_id, D10Z_MAX_NODE_ID_LEN - 1);
    node->state.phi = config->initial_phi;
    node->state.energy = 1000;
    node->alpha_decay = config->alpha_decay;
    node->beta_coupling = config->beta_coupling;
    node->heartbeat_interval_ms = config->heartbeat_interval_ms;
    node->neighbor_timeout_ms = config->neighbor_timeout_ms;
    node->callbacks = config->callbacks;
    node->initialized = true;
    
    return node;
}

void d10z_node_destroy(d10z_node_t *node) {
    if (node) free(node);
}

d10z_error_t d10z_node_tick(d10z_node_t *node, uint32_t current_time_ms) {
    if (!node || !node->initialized) return D10Z_ERROR_NOT_INITIALIZED;
    
    if (node->start_time_ms == 0) node->start_time_ms = current_time_ms;
    
    /* Heartbeat */
    if (current_time_ms - node->last_heartbeat_ms >= node->heartbeat_interval_ms) {
        node->last_heartbeat_ms = current_time_ms;
        
        prune_inactive_neighbors(node, current_time_ms);
        propagate_coherence(node);
        compute_local_e_tta(node);
        
        if (node->callbacks.send_heartbeat) {
            d10z_heartbeat_t hb;
            memset(&hb, 0, sizeof(hb));
            strncpy(hb.node_id, node->node_id, D10Z_MAX_NODE_ID_LEN - 1);
            hb.timestamp_ms = current_time_ms;
            hb.state = node->state;
            hb.neighbor_count = node->neighbor_count;
            hb.local_e_tta = node->local_e_tta;
            node->callbacks.send_heartbeat(&hb, node->callbacks.user_data);
        }
    }
    
    return D10Z_OK;
}

d10z_error_t d10z_node_update_state(d10z_node_t *node, const d10z_state_t *state) {
    if (!node || !state) return D10Z_ERROR_INVALID_PARAM;
    
    d10z_level_t old_level = d10z_phi_to_level(node->state.phi);
    node->state = *state;
    d10z_level_t new_level = d10z_phi_to_level(node->state.phi);
    
    if (old_level != new_level && node->callbacks.level_changed) {
        node->callbacks.level_changed(old_level, new_level, node->callbacks.user_data);
    }
    
    return D10Z_OK;
}

d10z_error_t d10z_node_update_position(d10z_node_t *node, int32_t lat_e6, int32_t lon_e6, int32_t alt_m) {
    if (!node) return D10Z_ERROR_INVALID_PARAM;
    
    /* Conversión lat/lon a coordenadas locales (simplificada) */
    node->state.position.x = (lon_e6 * 111) / 1000;
    node->state.position.y = (lat_e6 * 111) / 1000;
    node->state.position.z = alt_m * 1000;
    node->state.altitude = alt_m;
    
    return D10Z_OK;
}

d10z_error_t d10z_node_process_heartbeat(
    d10z_node_t *node,
    const d10z_heartbeat_t *heartbeat,
    uint16_t distance_cm,
    int8_t signal_strength,
    d10z_conn_type_t conn_type
) {
    if (!node || !heartbeat) return D10Z_ERROR_INVALID_PARAM;
    if (strcmp(heartbeat->node_id, node->node_id) == 0) return D10Z_OK; /* Ignorar propio */
    
    int idx = find_neighbor(node, heartbeat->node_id);
    
    if (idx < 0) {
        if (node->neighbor_count >= D10Z_MAX_NEIGHBORS) {
            /* Remover el más antiguo */
            uint32_t oldest_time = 0xFFFFFFFF;
            int oldest_idx = 0;
            for (int i = 0; i < node->neighbor_count; i++) {
                if (node->neighbors[i].last_seen_ms < oldest_time) {
                    oldest_time = node->neighbors[i].last_seen_ms;
                    oldest_idx = i;
                }
            }
            idx = oldest_idx;
        } else {
            idx = node->neighbor_count++;
        }
    }
    
    d10z_neighbor_t *neighbor = &node->neighbors[idx];
    strncpy(neighbor->node_id, heartbeat->node_id, D10Z_MAX_NODE_ID_LEN - 1);
    neighbor->state = heartbeat->state;
    neighbor->distance_cm = distance_cm;
    neighbor->signal_strength = signal_strength;
    neighbor->last_seen_ms = heartbeat->timestamp_ms;
    neighbor->conn_type = conn_type;
    neighbor->active = true;
    
    return D10Z_OK;
}

d10z_error_t d10z_node_send(
    d10z_node_t *node,
    const char *dest_id,
    const uint8_t *payload,
    uint16_t payload_len
) {
    if (!node || !dest_id || !payload || payload_len > D10Z_MAX_PACKET_SIZE) {
        return D10Z_ERROR_INVALID_PARAM;
    }
    
    d10z_packet_t packet;
    memset(&packet, 0, sizeof(packet));
    
    /* Generar ID simple */
    static uint32_t packet_counter = 0;
    snprintf(packet.packet_id, sizeof(packet.packet_id), "P%08X", packet_counter++);
    
    strncpy(packet.source_id, node->node_id, D10Z_MAX_NODE_ID_LEN - 1);
    strncpy(packet.dest_id, dest_id, D10Z_MAX_NODE_ID_LEN - 1);
    packet.hop_count = 0;
    packet.payload_len = payload_len;
    memcpy(packet.payload, payload, payload_len);
    
    const char *next_hop = find_best_next_hop(node, dest_id);
    
    if (next_hop) {
        if (node->callbacks.send_packet) {
            node->callbacks.send_packet(&packet, next_hop, node->callbacks.user_data);
            node->packets_tx++;
        }
        return D10Z_OK;
    } else {
        if (node->callbacks.use_fallback) {
            node->callbacks.use_fallback(&packet, node->callbacks.user_data);
        }
        return D10Z_ERROR_NEIGHBOR_NOT_FOUND;
    }
}

d10z_error_t d10z_node_receive(d10z_node_t *node, const d10z_packet_t *packet) {
    if (!node || !packet) return D10Z_ERROR_INVALID_PARAM;
    
    node->packets_rx++;
    
    /* ¿Es para nosotros? */
    if (strcmp(packet->dest_id, node->node_id) == 0) {
        if (node->callbacks.packet_received) {
            node->callbacks.packet_received(packet, node->callbacks.user_data);
        }
        return D10Z_OK;
    }
    
    /* Reenviar */
    if (packet->hop_count >= D10Z_MAX_HOP_COUNT) {
        node->packets_dropped++;
        return D10Z_ERROR_TIMEOUT;
    }
    
    const char *next_hop = find_best_next_hop(node, packet->dest_id);
    
    if (next_hop) {
        d10z_packet_t fwd_packet = *packet;
        fwd_packet.hop_count++;
        
        if (node->callbacks.send_packet) {
            node->callbacks.send_packet(&fwd_packet, next_hop, node->callbacks.user_data);
            node->packets_tx++;
        }
        return D10Z_OK;
    } else {
        if (node->callbacks.use_fallback) {
            node->callbacks.use_fallback(packet, node->callbacks.user_data);
        }
        return D10Z_ERROR_NEIGHBOR_NOT_FOUND;
    }
}

d10z_error_t d10z_node_get_state(const d10z_node_t *node, d10z_state_t *state) {
    if (!node || !state) return D10Z_ERROR_INVALID_PARAM;
    *state = node->state;
    return D10Z_OK;
}

d10z_error_t d10z_node_get_metrics(const d10z_node_t *node, d10z_metrics_t *metrics) {
    if (!node || !metrics) return D10Z_ERROR_INVALID_PARAM;
    
    metrics->phi = node->state.phi;
    metrics->level = d10z_phi_to_level(node->state.phi);
    metrics->neighbor_count = node->neighbor_count;
    metrics->local_e_tta = node->local_e_tta;
    metrics->consensus_e_tta = node->consensus_e_tta;
    metrics->packets_rx = node->packets_rx;
    metrics->packets_tx = node->packets_tx;
    metrics->packets_dropped = node->packets_dropped;
    metrics->uptime_ms = node->last_heartbeat_ms - node->start_time_ms;
    
    return D10Z_OK;
}

d10z_error_t d10z_node_get_neighbors(
    const d10z_node_t *node,
    d10z_neighbor_t *neighbors,
    uint8_t *count,
    uint8_t max_count
) {
    if (!node || !neighbors || !count) return D10Z_ERROR_INVALID_PARAM;
    
    uint8_t n = (node->neighbor_count < max_count) ? node->neighbor_count : max_count;
    memcpy(neighbors, node->neighbors, n * sizeof(d10z_neighbor_t));
    *count = n;
    
    return D10Z_OK;
}

d10z_level_t d10z_node_get_level(const d10z_node_t *node) {
    if (!node) return D10Z_LEVEL_ISOLATED;
    return d10z_phi_to_level(node->state.phi);
}

uint32_t d10z_node_get_e_tta(const d10z_node_t *node) {
    return node ? node->local_e_tta : 0;
}

/* ═══════════════════════════════════════════════════════════════════════════════
 * UTILIDADES
 * ═══════════════════════════════════════════════════════════════════════════════
 */

d10z_level_t d10z_phi_to_level(uint16_t phi) {
    if (phi >= 900) return D10Z_LEVEL_OPTIMAL;
    if (phi >= 700) return D10Z_LEVEL_OPERATIONAL;
    if (phi >= 500) return D10Z_LEVEL_DEGRADED;
    if (phi >= 300) return D10Z_LEVEL_CRITICAL;
    return D10Z_LEVEL_ISOLATED;
}

uint32_t d10z_vector3_distance(const d10z_vector3_t *a, const d10z_vector3_t *b) {
    d10z_vector3_t diff = { a->x - b->x, a->y - b->y, a->z - b->z };
    return vector3_magnitude(&diff);
}

uint16_t d10z_heartbeat_serialize(const d10z_heartbeat_t *hb, uint8_t *buf, uint16_t len) {
    if (len < 80) return 0;
    
    uint16_t pos = 0;
    buf[pos++] = 0xD1; buf[pos++] = 0x0Z; /* Magic */
    buf[pos++] = 0x01; /* Type: heartbeat */
    
    memcpy(&buf[pos], hb->node_id, D10Z_MAX_NODE_ID_LEN); pos += D10Z_MAX_NODE_ID_LEN;
    memcpy(&buf[pos], &hb->timestamp_ms, 4); pos += 4;
    memcpy(&buf[pos], &hb->state.phi, 2); pos += 2;
    memcpy(&buf[pos], &hb->state.energy, 2); pos += 2;
    memcpy(&buf[pos], &hb->state.position.x, 4); pos += 4;
    memcpy(&buf[pos], &hb->state.position.y, 4); pos += 4;
    memcpy(&buf[pos], &hb->state.position.z, 4); pos += 4;
    buf[pos++] = hb->neighbor_count;
    memcpy(&buf[pos], &hb->local_e_tta, 4); pos += 4;
    
    return pos;
}

d10z_error_t d10z_heartbeat_deserialize(const uint8_t *buf, uint16_t len, d10z_heartbeat_t *hb) {
    if (len < 60 || buf[0] != 0xD1 || buf[1] != 0x0Z || buf[2] != 0x01) {
        return D10Z_ERROR_INVALID_PARAM;
    }
    
    uint16_t pos = 3;
    memset(hb, 0, sizeof(*hb));
    
    memcpy(hb->node_id, &buf[pos], D10Z_MAX_NODE_ID_LEN); pos += D10Z_MAX_NODE_ID_LEN;
    memcpy(&hb->timestamp_ms, &buf[pos], 4); pos += 4;
    memcpy(&hb->state.phi, &buf[pos], 2); pos += 2;
    memcpy(&hb->state.energy, &buf[pos], 2); pos += 2;
    memcpy(&hb->state.position.x, &buf[pos], 4); pos += 4;
    memcpy(&hb->state.position.y, &buf[pos], 4); pos += 4;
    memcpy(&hb->state.position.z, &buf[pos], 4); pos += 4;
    hb->neighbor_count = buf[pos++];
    memcpy(&hb->local_e_tta, &buf[pos], 4);
    
    return D10Z_OK;
}

uint16_t d10z_rssi_to_distance_cm(int8_t rssi, int8_t tx_power) {
    /* d = 10^((TxPower - RSSI) / (10 * n)) */
    int diff = tx_power - rssi;
    if (diff < 0) diff = 0;
    
    /* Aproximación con n=2 */
    uint32_t distance_m;
    if (diff < 20) distance_m = 1;
    else if (diff < 40) distance_m = 10;
    else if (diff < 60) distance_m = 100;
    else distance_m = 1000;
    
    return (uint16_t)(distance_m * 100);
}

const char* d10z_level_to_string(d10z_level_t level) {
    switch (level) {
        case D10Z_LEVEL_OPTIMAL: return "OPTIMAL";
        case D10Z_LEVEL_OPERATIONAL: return "OPERATIONAL";
        case D10Z_LEVEL_DEGRADED: return "DEGRADED";
        case D10Z_LEVEL_CRITICAL: return "CRITICAL";
        case D10Z_LEVEL_ISOLATED: return "ISOLATED";
        default: return "UNKNOWN";
    }
}

const char* d10z_error_to_string(d10z_error_t error) {
    switch (error) {
        case D10Z_OK: return "OK";
        case D10Z_ERROR_INVALID_PARAM: return "INVALID_PARAM";
        case D10Z_ERROR_NO_MEMORY: return "NO_MEMORY";
        case D10Z_ERROR_BUFFER_FULL: return "BUFFER_FULL";
        case D10Z_ERROR_NOT_INITIALIZED: return "NOT_INITIALIZED";
        case D10Z_ERROR_NEIGHBOR_NOT_FOUND: return "NEIGHBOR_NOT_FOUND";
        case D10Z_ERROR_TIMEOUT: return "TIMEOUT";
        case D10Z_ERROR_NETWORK: return "NETWORK";
        default: return "UNKNOWN";
    }
}
