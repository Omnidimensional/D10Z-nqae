/*
 * ══════════════════════════════════════════════════════════════════════════════
 * Pyraclaw-TTA SDK - EJEMPLO DE USO
 * ══════════════════════════════════════════════════════════════════════════════
 * 
 * Este ejemplo muestra cómo integrar el SDK Pyraclaw en:
 * - OpenWRT routers
 * - ESP32 / ESP8266
 * - FreeRTOS devices
 * - Linux embebido
 * 
 * ══════════════════════════════════════════════════════════════════════════════
 */

#include "pyraclaw_sdk.h"
#include <stdio.h>
#include <time.h>

/* ═══════════════════════════════════════════════════════════════════════════════
 * CALLBACKS - Implementar según plataforma
 * ═══════════════════════════════════════════════════════════════════════════════
 */

/* Callback: enviar heartbeat por broadcast */
void on_send_heartbeat(const pyraclaw_heartbeat_t *heartbeat, void *user_data) {
    uint8_t buffer[128];
    uint16_t len = pyraclaw_heartbeat_serialize(heartbeat, buffer, sizeof(buffer));
    
    if (len > 0) {
        /* 
         * PLATAFORMA ESPECÍFICA:
         * - OpenWRT: sendto() UDP broadcast en puerto 8470
         * - ESP32: esp_wifi_send_raw() o UDP
         * - BLE: characteristic notify
         */
        printf("[TX] Heartbeat: node=%s phi=%d e_tta=%u\n",
               heartbeat->node_id,
               heartbeat->state.phi,
               heartbeat->local_e_tta);
    }
}

/* Callback: enviar paquete a vecino específico */
void on_send_packet(const pyraclaw_packet_t *packet, const char *neighbor_id, void *user_data) {
    printf("[TX] Packet %s -> %s via %s (hop %d)\n",
           packet->source_id,
           packet->dest_id,
           neighbor_id,
           packet->hop_count);
    
    /* 
     * PLATAFORMA ESPECÍFICA:
     * - Buscar IP/MAC del neighbor_id
     * - Enviar por UDP unicast o WiFi Direct
     */
}

/* Callback: usar fallback (internet tradicional) */
void on_use_fallback(const pyraclaw_packet_t *packet, void *user_data) {
    printf("[FALLBACK] No nodal route for %s -> %s\n",
           packet->source_id,
           packet->dest_id);
    
    /*
     * Enviar por ruta tradicional (gateway, internet)
     */
}

/* Callback: paquete recibido para este nodo */
void on_packet_received(const pyraclaw_packet_t *packet, void *user_data) {
    printf("[RX] Packet from %s: %.*s\n",
           packet->source_id,
           packet->payload_len,
           packet->payload);
}

/* Callback: cambio de nivel de coherencia */
void on_level_changed(pyraclaw_level_t old_level, pyraclaw_level_t new_level, void *user_data) {
    printf("[ALERT] Level changed: %s -> %s\n",
           pyraclaw_level_to_string(old_level),
           pyraclaw_level_to_string(new_level));
    
    /*
     * Acciones según nivel:
     * - DEGRADED: activar modo ahorro
     * - CRITICAL: intentar reconectar
     * - ISOLATED: usar fallback exclusivo
     */
}

/* ═══════════════════════════════════════════════════════════════════════════════
 * SIMULACIÓN DE HEARTBEAT RECIBIDO
 * ═══════════════════════════════════════════════════════════════════════════════
 */

void simulate_received_heartbeat(pyraclaw_node_t *node, const char *neighbor_id, 
                                 uint16_t phi, int8_t rssi) {
    pyraclaw_heartbeat_t hb;
    memset(&hb, 0, sizeof(hb));
    
    strncpy(hb.node_id, neighbor_id, Pyraclaw_MAX_NODE_ID_LEN - 1);
    hb.timestamp_ms = (uint32_t)(time(NULL) * 1000);
    hb.state.phi = phi;
    hb.state.energy = 950;
    hb.neighbor_count = 2;
    hb.local_e_tta = 5000;
    
    uint16_t distance = pyraclaw_rssi_to_distance_cm(rssi, -59);
    
    pyraclaw_node_process_heartbeat(node, &hb, distance, rssi, Pyraclaw_CONN_WIFI);
    
    printf("[RX] Heartbeat from %s: phi=%d rssi=%d dist=%dcm\n",
           neighbor_id, phi, rssi, distance);
}

/* ═══════════════════════════════════════════════════════════════════════════════
 * MAIN - DEMO
 * ═══════════════════════════════════════════════════════════════════════════════
 */

int main(void) {
    printf("══════════════════════════════════════════════════════════════════\n");
    printf("Pyraclaw-TTA Embedded SDK v%s\n", PYRACLAW_SDK_VERSION);
    printf("══════════════════════════════════════════════════════════════════\n\n");
    
    /* ─────────────────────────────────────────────────────────────────────
     * 1. CONFIGURACIÓN
     * ───────────────────────────────────────────────────────────────────── */
    
    pyraclaw_config_t config;
    pyraclaw_config_default(&config);
    
    strcpy(config.node_id, "Pyraclaw-ROUTER-001");
    config.initial_phi = 500;  /* 0.5 */
    config.heartbeat_interval_ms = 100;
    
    /* Configurar callbacks */
    config.callbacks.send_heartbeat = on_send_heartbeat;
    config.callbacks.send_packet = on_send_packet;
    config.callbacks.use_fallback = on_use_fallback;
    config.callbacks.packet_received = on_packet_received;
    config.callbacks.level_changed = on_level_changed;
    config.callbacks.user_data = NULL;
    
    /* ─────────────────────────────────────────────────────────────────────
     * 2. CREAR NODO
     * ───────────────────────────────────────────────────────────────────── */
    
    pyraclaw_node_t *node = pyraclaw_node_create(&config);
    if (!node) {
        printf("ERROR: Failed to create node\n");
        return 1;
    }
    
    printf("Node created: %s\n\n", config.node_id);
    
    /* ─────────────────────────────────────────────────────────────────────
     * 3. ACTUALIZAR POSICIÓN (GPS o manual)
     * ───────────────────────────────────────────────────────────────────── */
    
    /* Lima, Perú: -12.0464, -77.0428 */
    pyraclaw_node_update_position(node, -12046400, -77042800, 150);
    
    /* ─────────────────────────────────────────────────────────────────────
     * 4. SIMULAR CICLOS
     * ───────────────────────────────────────────────────────────────────── */
    
    printf("─── Simulando 10 ciclos con vecinos ───\n\n");
    
    uint32_t time_ms = 0;
    
    for (int cycle = 0; cycle < 10; cycle++) {
        time_ms += 100;  /* 100ms por ciclo */
        
        /* Simular heartbeats de vecinos */
        if (cycle == 0) {
            simulate_received_heartbeat(node, "Pyraclaw-NEIGHBOR-A", 900, -45);
            simulate_received_heartbeat(node, "Pyraclaw-NEIGHBOR-B", 850, -55);
            simulate_received_heartbeat(node, "Pyraclaw-NEIGHBOR-C", 800, -65);
        }
        
        /* Ejecutar ciclo Pyraclaw */
        pyraclaw_node_tick(node, time_ms);
        
        /* Mostrar métricas cada 5 ciclos */
        if ((cycle + 1) % 5 == 0) {
            pyraclaw_metrics_t metrics;
            pyraclaw_node_get_metrics(node, &metrics);
            
            printf("\n─── Cycle %d ───\n", cycle + 1);
            printf("  Φ: %d/1000 (%s)\n", metrics.phi, pyraclaw_level_to_string(metrics.level));
            printf("  E_TTA: %u\n", metrics.local_e_tta);
            printf("  Neighbors: %d\n", metrics.neighbor_count);
            printf("  Packets: RX=%u TX=%u DROP=%u\n",
                   metrics.packets_rx, metrics.packets_tx, metrics.packets_dropped);
        }
    }
    
    /* ─────────────────────────────────────────────────────────────────────
     * 5. ENVIAR MENSAJE
     * ───────────────────────────────────────────────────────────────────── */
    
    printf("\n─── Enviando mensaje ───\n");
    
    const char *message = "Hola desde Pyraclaw!";
    pyraclaw_error_t err = pyraclaw_node_send(node, "Pyraclaw-DESTINATION", 
                                       (const uint8_t*)message, strlen(message));
    
    printf("Send result: %s\n", pyraclaw_error_to_string(err));
    
    /* ─────────────────────────────────────────────────────────────────────
     * 6. LISTAR VECINOS
     * ───────────────────────────────────────────────────────────────────── */
    
    printf("\n─── Vecinos activos ───\n");
    
    pyraclaw_neighbor_t neighbors[Pyraclaw_MAX_NEIGHBORS];
    uint8_t neighbor_count = 0;
    
    pyraclaw_node_get_neighbors(node, neighbors, &neighbor_count, Pyraclaw_MAX_NEIGHBORS);
    
    for (int i = 0; i < neighbor_count; i++) {
        printf("  [%d] %s: phi=%d dist=%dcm rssi=%d\n",
               i,
               neighbors[i].node_id,
               neighbors[i].state.phi,
               neighbors[i].distance_cm,
               neighbors[i].signal_strength);
    }
    
    /* ─────────────────────────────────────────────────────────────────────
     * 7. CLEANUP
     * ───────────────────────────────────────────────────────────────────── */
    
    pyraclaw_node_destroy(node);
    
    printf("\n══════════════════════════════════════════════════════════════════\n");
    printf("Demo completed\n");
    printf("══════════════════════════════════════════════════════════════════\n");
    
    return 0;
}

/* ═══════════════════════════════════════════════════════════════════════════════
 * EJEMPLO: LOOP PRINCIPAL PARA EMBEBIDOS
 * ═══════════════════════════════════════════════════════════════════════════════
 *
 * Para OpenWRT/FreeRTOS/bare-metal:
 *
 * void main_loop(pyraclaw_node_t *node) {
 *     while (1) {
 *         uint32_t now = get_time_ms();  // Función de plataforma
 *         
 *         // Procesar heartbeats UDP recibidos
 *         while (udp_data_available()) {
 *             uint8_t buffer[128];
 *             int len = udp_recv(buffer, sizeof(buffer));
 *             
 *             pyraclaw_heartbeat_t hb;
 *             if (pyraclaw_heartbeat_deserialize(buffer, len, &hb) == Pyraclaw_OK) {
 *                 pyraclaw_node_process_heartbeat(node, &hb, 
 *                     estimate_distance(), get_rssi(), Pyraclaw_CONN_WIFI);
 *             }
 *         }
 *         
 *         // Ejecutar ciclo Pyraclaw
 *         pyraclaw_node_tick(node, now);
 *         
 *         // Dormir hasta siguiente ciclo
 *         sleep_ms(10);
 *     }
 * }
 *
 * ═══════════════════════════════════════════════════════════════════════════════
 */
