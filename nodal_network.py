#!/usr/bin/env python3
"""
D10Z-TTA NODAL NETWORK
======================
Sistema de red P2P nodal con soporte para:
- WiFi Direct
- Bluetooth LE Mesh
- WiFi Aware
- Comunicación Hz nodal

Implementa el protocolo de comunicación D10Z para
reemplazo de internet tradicional.
"""

import numpy as np
import hashlib
import struct
import time
import threading
import queue
import socket
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable, Set
from enum import Enum
from abc import ABC, abstractmethod
import json

# Importar core
import sys
sys.path.insert(0, '..')
from core.engine import (
    D10ZConstants, PathMode, CoherenceLevel,
    CoherenceAnalyzer, IsisLawEngine, ETTACalculator,
    generate_node_id, compute_hash, d10z_hash
)


# =============================================================================
# TIPOS DE TRAMA
# =============================================================================

class FrameType(Enum):
    """Tipos de trama del protocolo D10Z."""
    HEARTBEAT = 0x01
    DATA = 0x02
    ROUTE_REQUEST = 0x31
    ROUTE_REPLY = 0x32
    ROUTE_ERROR = 0x33
    CONSENSUS_PROPOSE = 0x41
    CONSENSUS_VOTE = 0x42
    CONSENSUS_COMMIT = 0x43
    CHUNK_REQUEST = 0x51
    CHUNK_RESPONSE = 0x52
    NAME_REGISTER = 0x61
    NAME_RESOLVE = 0x62


class BandType(Enum):
    """Bandas de frecuencia soportadas."""
    WIFI_24 = 0x01      # 2.4 GHz
    WIFI_5 = 0x02       # 5 GHz
    WIFI_6E = 0x03      # 6 GHz
    BLE = 0x04          # Bluetooth LE
    LORA = 0x05         # LoRa 868/915 MHz
    UWB = 0x06          # Ultra-Wideband
    SATELLITE = 0x07    # Ku/Ka band


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class NodeInfo:
    """Información de un nodo vecino."""
    node_id: bytes
    phi: float
    distance: float
    rssi: int
    band: BandType
    last_seen: int  # timestamp ms
    services: int   # bitmap de servicios
    position: Optional[Tuple[float, float, float]] = None
    
    def is_stale(self, timeout_ms: int = D10ZConstants.NEIGHBOR_TIMEOUT_MS) -> bool:
        """Verifica si el nodo está inactivo."""
        return (time.time_ns() // 1_000_000 - self.last_seen) > timeout_ms
    
    def to_dict(self) -> Dict:
        return {
            'node_id': self.node_id.hex()[:16],
            'phi': self.phi,
            'distance': self.distance,
            'rssi': self.rssi,
            'band': self.band.name,
            'last_seen': self.last_seen,
        }


@dataclass
class RouteEntry:
    """Entrada en la tabla de rutas."""
    dest_id: bytes
    next_hop: bytes
    hop_count: int
    phi_path: float  # Φ mínimo del camino
    sequence: int
    expires_at: int  # timestamp ms
    
    def is_valid(self) -> bool:
        """Verifica si la ruta es válida."""
        return (time.time_ns() // 1_000_000) < self.expires_at


@dataclass
class Packet:
    """Paquete de datos D10Z."""
    frame_type: FrameType
    source_id: bytes
    dest_id: bytes
    sequence: int
    ttl: int
    hop_count: int
    phi_source: float
    payload: bytes
    path: List[bytes] = field(default_factory=list)
    timestamp: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time_ns() // 1_000_000
    
    def serialize(self) -> bytes:
        """Serializa el paquete a bytes."""
        # Header
        data = struct.pack(
            '>4sHBBHH16s16sIBBHI',
            D10ZConstants.MAGIC,
            D10ZConstants.VERSION,
            self.frame_type.value,
            0,  # flags
            int(self.phi_source * 65535),
            len(self.payload),
            self.source_id[:16],
            self.dest_id[:16],
            self.sequence,
            self.ttl,
            self.hop_count,
            len(self.path),
            self.timestamp
        )
        
        # Path
        for node_id in self.path:
            data += node_id[:8]
        
        # Payload
        data += self.payload
        
        # CRC32
        crc = compute_hash(data)[:4]
        data += crc
        
        return data
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Packet':
        """Deserializa paquete desde bytes."""
        # Verificar magic
        if data[:4] != D10ZConstants.MAGIC:
            raise ValueError("Invalid magic number")
        
        # Header
        (magic, version, frame_type, flags, phi_raw, payload_len,
         source_id, dest_id, sequence, ttl, hop_count, path_len,
         timestamp) = struct.unpack('>4sHBBHH16s16sIBBHI', data[:52])
        
        offset = 52
        
        # Path
        path = []
        for _ in range(path_len):
            path.append(data[offset:offset+8])
            offset += 8
        
        # Payload
        payload = data[offset:offset+payload_len]
        
        return cls(
            frame_type=FrameType(frame_type),
            source_id=source_id,
            dest_id=dest_id,
            sequence=sequence,
            ttl=ttl,
            hop_count=hop_count,
            phi_source=phi_raw / 65535.0,
            payload=payload,
            path=path,
            timestamp=timestamp
        )


@dataclass 
class Heartbeat:
    """Mensaje de heartbeat."""
    node_id: bytes
    phi: float
    energy: float
    neighbors_count: int
    capacity_mb: int
    content_count: int
    position: Tuple[float, float, float]  # lat, lon, alt
    services: int
    uptime: int
    
    def serialize(self) -> bytes:
        """Serializa heartbeat."""
        lat, lon, alt = self.position
        return struct.pack(
            '>16sHHBIHiiiIHI',
            self.node_id[:16],
            int(self.phi * 65535),
            int(self.energy * 65535),
            self.neighbors_count,
            self.capacity_mb,
            self.content_count,
            int(lat * 1e7),
            int(lon * 1e7),
            int(alt * 100),
            self.services,
            0,  # reserved
            self.uptime
        )
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Heartbeat':
        """Deserializa heartbeat."""
        (node_id, phi_raw, energy_raw, neighbors, capacity,
         content_count, lat_raw, lon_raw, alt_raw, services,
         _, uptime) = struct.unpack('>16sHHBIHiiiIHI', data[:50])
        
        return cls(
            node_id=node_id,
            phi=phi_raw / 65535.0,
            energy=energy_raw / 65535.0,
            neighbors_count=neighbors,
            capacity_mb=capacity,
            content_count=content_count,
            position=(lat_raw / 1e7, lon_raw / 1e7, alt_raw / 100),
            services=services,
            uptime=uptime
        )


# =============================================================================
# CAPA DE ENLACE
# =============================================================================

class LinkLayer:
    """
    Capa de enlace D10Z.
    
    Gestiona:
    - Descubrimiento de vecinos
    - Heartbeats
    - Mantenimiento de coherencia
    """
    
    def __init__(self, node_id: bytes):
        self.node_id = node_id
        self.neighbors: Dict[bytes, NodeInfo] = {}
        self.coherence = IsisLawEngine()
        self.analyzer = CoherenceAnalyzer()
        
        self.sequence_counter = 0
        self.running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._rx_queue: queue.Queue = queue.Queue()
        
        # Callbacks
        self.on_neighbor_discovered: Optional[Callable] = None
        self.on_neighbor_lost: Optional[Callable] = None
        self.on_packet_received: Optional[Callable] = None
        
    def start(self):
        """Inicia la capa de enlace."""
        self.running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()
        
    def stop(self):
        """Detiene la capa de enlace."""
        self.running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)
    
    def _heartbeat_loop(self):
        """Loop de heartbeat."""
        while self.running:
            # Generar y enviar heartbeat
            heartbeat = self._create_heartbeat()
            self._broadcast_heartbeat(heartbeat)
            
            # Propagar coherencia
            neighbor_data = [
                (info.phi, info.distance)
                for info in self.neighbors.values()
                if not info.is_stale()
            ]
            self.coherence.propagate(neighbor_data)
            
            # Limpiar vecinos inactivos
            self._prune_stale_neighbors()
            
            time.sleep(D10ZConstants.HEARTBEAT_INTERVAL_MS / 1000)
    
    def _create_heartbeat(self) -> Heartbeat:
        """Crea heartbeat con estado actual."""
        return Heartbeat(
            node_id=self.node_id,
            phi=self.coherence.phi,
            energy=1.0,  # TODO: medir energía real
            neighbors_count=len(self.neighbors),
            capacity_mb=1024,  # TODO: medir capacidad real
            content_count=0,
            position=(0.0, 0.0, 0.0),  # TODO: obtener posición
            services=0x01,  # RELAY básico
            uptime=int(time.time())
        )
    
    def _broadcast_heartbeat(self, heartbeat: Heartbeat):
        """Envía heartbeat por broadcast."""
        packet = Packet(
            frame_type=FrameType.HEARTBEAT,
            source_id=self.node_id,
            dest_id=b'\x00' * 16,  # Broadcast
            sequence=self._next_sequence(),
            ttl=1,
            hop_count=0,
            phi_source=heartbeat.phi,
            payload=heartbeat.serialize()
        )
        
        # TODO: Enviar por todas las bandas disponibles
        self._send_raw(packet.serialize())
    
    def _send_raw(self, data: bytes):
        """Envía datos raw (stub para implementar transporte real)."""
        # TODO: Implementar envío real por WiFi Direct, BLE, etc.
        pass
    
    def process_heartbeat(self, heartbeat: Heartbeat, rssi: int, band: BandType):
        """Procesa heartbeat recibido."""
        if heartbeat.node_id == self.node_id:
            return  # Ignorar propio
        
        # Estimar distancia por RSSI
        distance = self._estimate_distance(rssi, band)
        
        # Crear/actualizar info de vecino
        neighbor = NodeInfo(
            node_id=heartbeat.node_id,
            phi=heartbeat.phi,
            distance=distance,
            rssi=rssi,
            band=band,
            last_seen=time.time_ns() // 1_000_000,
            services=heartbeat.services,
            position=heartbeat.position
        )
        
        is_new = heartbeat.node_id not in self.neighbors
        self.neighbors[heartbeat.node_id] = neighbor
        
        if is_new and self.on_neighbor_discovered:
            self.on_neighbor_discovered(neighbor)
    
    def _estimate_distance(self, rssi: int, band: BandType) -> float:
        """Estima distancia por RSSI."""
        # Modelo simplificado de path loss
        # d = 10^((TxPower - RSSI) / (10 * n))
        
        tx_power = -40  # dBm típico
        n = 2.0  # Exponente de path loss
        
        if band == BandType.BLE:
            tx_power = -50
        elif band == BandType.LORA:
            tx_power = 14
            n = 2.5
        
        distance = 10 ** ((tx_power - rssi) / (10 * n))
        return max(1.0, min(1000.0, distance))
    
    def _prune_stale_neighbors(self):
        """Elimina vecinos inactivos."""
        stale = [
            node_id for node_id, info in self.neighbors.items()
            if info.is_stale()
        ]
        
        for node_id in stale:
            neighbor = self.neighbors.pop(node_id)
            if self.on_neighbor_lost:
                self.on_neighbor_lost(neighbor)
    
    def _next_sequence(self) -> int:
        """Genera siguiente número de secuencia."""
        self.sequence_counter += 1
        return self.sequence_counter
    
    def get_best_neighbors(self, count: int = 8) -> List[NodeInfo]:
        """Retorna los mejores vecinos por Φ × señal."""
        scored = [
            (info, info.phi * (100 + info.rssi) / 100)
            for info in self.neighbors.values()
            if not info.is_stale() and info.phi >= 0.5
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [info for info, _ in scored[:count]]
    
    def get_neighbor_phi(self, node_id: bytes) -> float:
        """Obtiene Φ de un vecino."""
        if node_id in self.neighbors:
            return self.neighbors[node_id].phi
        return 0.0


# =============================================================================
# CAPA DE RED - ENRUTAMIENTO
# =============================================================================

class Router:
    """
    Enrutador D10Z basado en coherencia.
    
    Implementa D10Z-AODV-Φ:
    - Enrutamiento on-demand
    - Métricas basadas en coherencia
    - Selección de ruta por Φ mínimo del path
    """
    
    ROUTE_TTL_MS = 30000
    
    def __init__(self, node_id: bytes, link: LinkLayer):
        self.node_id = node_id
        self.link = link
        
        self.routing_table: Dict[bytes, RouteEntry] = {}
        self.pending_routes: Dict[bytes, List[Callable]] = {}
        self.seen_packets: Set[Tuple[bytes, int]] = set()
        
        self.sequence_counter = 0
        
    def route_packet(self, packet: Packet) -> str:
        """
        Enruta un paquete.
        
        Returns:
            'DELIVERED' | 'FORWARDED' | 'NO_ROUTE' | 'DUPLICATE' | 'TTL_EXPIRED'
        """
        # ¿Es para nosotros?
        if packet.dest_id[:16] == self.node_id[:16]:
            return 'DELIVERED'
        
        # ¿TTL expirado?
        if packet.ttl <= 0:
            return 'TTL_EXPIRED'
        
        # ¿Duplicado?
        packet_key = (packet.source_id, packet.sequence)
        if packet_key in self.seen_packets:
            return 'DUPLICATE'
        self.seen_packets.add(packet_key)
        
        # Limpiar packets viejos
        if len(self.seen_packets) > 10000:
            self.seen_packets = set(list(self.seen_packets)[-5000:])
        
        # Buscar siguiente salto
        next_hop = self._find_next_hop(packet.dest_id, packet.path)
        
        if next_hop is None:
            return 'NO_ROUTE'
        
        # Decrementar TTL y agregar a path
        packet.ttl -= 1
        packet.hop_count += 1
        packet.path.append(self.node_id[:8])
        
        # Enviar
        self._send_to_neighbor(next_hop, packet)
        
        return 'FORWARDED'
    
    def _find_next_hop(self, dest_id: bytes, excluded_path: List[bytes]) -> Optional[bytes]:
        """Encuentra el mejor siguiente salto."""
        
        # Verificar tabla de rutas
        if dest_id in self.routing_table:
            route = self.routing_table[dest_id]
            if route.is_valid():
                return route.next_hop
        
        # ¿El destino es vecino directo?
        if dest_id in self.link.neighbors:
            neighbor = self.link.neighbors[dest_id]
            if neighbor.phi >= 0.7:
                return dest_id
        
        # Buscar mejor vecino no visitado
        candidates = []
        excluded_set = set(p[:8] for p in excluded_path)
        
        for neighbor in self.link.neighbors.values():
            if neighbor.node_id[:8] in excluded_set:
                continue
            if neighbor.phi < 0.5:
                continue
            
            score = neighbor.phi * (100.0 / max(1, neighbor.distance))
            candidates.append((neighbor.node_id, score))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _send_to_neighbor(self, neighbor_id: bytes, packet: Packet):
        """Envía paquete a un vecino."""
        # TODO: Implementar envío real
        pass
    
    def calculate_route_metric(self, route: RouteEntry) -> float:
        """
        Calcula métrica de calidad de ruta.
        
        M = (Φ_min × 0.5) + (1/hops × 0.3) + (1/latency × 0.2)
        """
        phi_score = route.phi_path
        hops_score = 1.0 / max(1, route.hop_count)
        latency_score = 1.0  # TODO: estimar latencia
        
        return (phi_score * 0.5 + hops_score * 0.3 + latency_score * 0.2)


# =============================================================================
# DHT - TABLA HASH DISTRIBUIDA
# =============================================================================

class NodalDHT:
    """
    DHT basada en Kademlia adaptada para D10Z.
    
    Diferencias con Kademlia estándar:
    - Distancia incluye factor de coherencia Φ
    - Replicación adaptativa según demanda
    """
    
    K = 20  # Nodos por bucket
    ALPHA = 3  # Paralelismo de búsqueda
    
    def __init__(self, node_id: bytes, router: Router):
        self.node_id = node_id
        self.router = router
        
        self.buckets: List[List[NodeInfo]] = [[] for _ in range(256)]
        self.storage: Dict[bytes, bytes] = {}
        self.providers: Dict[bytes, Set[bytes]] = {}
        
    def distance(self, id1: bytes, id2: bytes, phi: float = 1.0) -> int:
        """
        Distancia XOR modificada con Φ.
        d(a, b, Φ) = XOR(a, b) / Φ
        """
        xor_bytes = bytes(a ^ b for a, b in zip(id1[:16], id2[:16]))
        xor_dist = int.from_bytes(xor_bytes, 'big')
        return int(xor_dist / max(0.1, phi))
    
    def store(self, key: bytes, value: bytes, replication: int = 3) -> int:
        """Almacena valor en la DHT."""
        # Almacenar localmente
        self.storage[key] = value
        
        # TODO: Replicar a nodos cercanos
        return 1
    
    def get(self, key: bytes) -> Optional[bytes]:
        """Obtiene valor de la DHT."""
        # Buscar localmente
        if key in self.storage:
            return self.storage[key]
        
        # TODO: Buscar en la red
        return None
    
    def announce_provider(self, content_hash: bytes):
        """Anuncia que tenemos un contenido."""
        if content_hash not in self.providers:
            self.providers[content_hash] = set()
        self.providers[content_hash].add(self.node_id)
    
    def find_providers(self, content_hash: bytes) -> List[bytes]:
        """Encuentra proveedores de un contenido."""
        if content_hash in self.providers:
            return list(self.providers[content_hash])
        return []


# =============================================================================
# NODO COMPLETO
# =============================================================================

class D10ZNode:
    """
    Nodo D10Z-TTA completo.
    
    Integra todas las capas:
    - Enlace (vecinos, heartbeat)
    - Red (enrutamiento)
    - DHT (almacenamiento distribuido)
    - Coherencia (Ley Isis)
    """
    
    def __init__(self, seed: bytes = None):
        # Generar identidad
        if seed:
            self.node_id = compute_hash(seed)
        else:
            self.node_id = generate_node_id()
        
        # Capas
        self.link = LinkLayer(self.node_id)
        self.router = Router(self.node_id, self.link)
        self.dht = NodalDHT(self.node_id, self.router)
        self.analyzer = CoherenceAnalyzer()
        
        # Estado
        self.running = False
        self.start_time = 0
        
        # Callbacks
        self.link.on_neighbor_discovered = self._on_neighbor_discovered
        self.link.on_neighbor_lost = self._on_neighbor_lost
        
    def start(self):
        """Inicia el nodo."""
        self.running = True
        self.start_time = time.time()
        self.link.start()
        
        print(f"🚀 D10Z Node started: {self.node_id.hex()[:16]}...")
        print(f"   Φ = {self.link.coherence.phi:.3f}")
        
    def stop(self):
        """Detiene el nodo."""
        self.running = False
        self.link.stop()
        print(f"🛑 D10Z Node stopped: {self.node_id.hex()[:16]}...")
    
    def _on_neighbor_discovered(self, neighbor: NodeInfo):
        """Callback cuando se descubre un vecino."""
        print(f"   📡 Neighbor discovered: {neighbor.node_id.hex()[:8]}... Φ={neighbor.phi:.2f}")
    
    def _on_neighbor_lost(self, neighbor: NodeInfo):
        """Callback cuando se pierde un vecino."""
        print(f"   ❌ Neighbor lost: {neighbor.node_id.hex()[:8]}...")
    
    def send_message(self, dest_id: bytes, data: bytes) -> bool:
        """Envía mensaje a otro nodo."""
        packet = Packet(
            frame_type=FrameType.DATA,
            source_id=self.node_id,
            dest_id=dest_id,
            sequence=self.link._next_sequence(),
            ttl=D10ZConstants.MAX_HOPS,
            hop_count=0,
            phi_source=self.link.coherence.phi,
            payload=data
        )
        
        result = self.router.route_packet(packet)
        return result in ('DELIVERED', 'FORWARDED')
    
    def store_content(self, data: bytes) -> str:
        """Almacena contenido en la red."""
        content_hash = compute_hash(data)
        
        # Almacenar en DHT
        self.dht.store(content_hash, data)
        self.dht.announce_provider(content_hash)
        
        return d10z_hash(data)
    
    def get_content(self, content_hash: bytes) -> Optional[bytes]:
        """Obtiene contenido de la red."""
        return self.dht.get(content_hash)
    
    def get_status(self) -> Dict:
        """Obtiene estado del nodo."""
        return {
            'node_id': self.node_id.hex()[:16],
            'phi': self.link.coherence.phi,
            'level': CoherenceLevel(
                'OPTIMAL' if self.link.coherence.phi >= 0.9 else
                'OPERATIONAL' if self.link.coherence.phi >= 0.7 else
                'DEGRADED' if self.link.coherence.phi >= 0.5 else
                'CRITICAL' if self.link.coherence.phi >= 0.3 else
                'ISOLATED'
            ).value,
            'neighbors': len(self.link.neighbors),
            'uptime': int(time.time() - self.start_time) if self.running else 0,
            'running': self.running,
        }


# =============================================================================
# SIMULADOR DE RED
# =============================================================================

class NetworkSimulator:
    """Simulador de red D10Z para testing."""
    
    def __init__(self, num_nodes: int = 10):
        self.nodes: List[D10ZNode] = []
        
        for i in range(num_nodes):
            node = D10ZNode(seed=f"node_{i}".encode())
            self.nodes.append(node)
        
        # Conectar nodos (topología mesh simple)
        self._create_mesh_topology()
    
    def _create_mesh_topology(self):
        """Crea topología mesh entre nodos."""
        for i, node in enumerate(self.nodes):
            # Conectar con vecinos cercanos
            for j in range(max(0, i-2), min(len(self.nodes), i+3)):
                if i != j:
                    neighbor = self.nodes[j]
                    distance = abs(i - j) * 10.0  # Distancia proporcional
                    
                    # Simular heartbeat recibido
                    heartbeat = Heartbeat(
                        node_id=neighbor.node_id,
                        phi=0.5 + np.random.random() * 0.4,  # 0.5-0.9
                        energy=1.0,
                        neighbors_count=2,
                        capacity_mb=1024,
                        content_count=0,
                        position=(0, 0, 0),
                        services=1,
                        uptime=0
                    )
                    
                    rssi = -40 - int(distance)  # RSSI decrece con distancia
                    node.link.process_heartbeat(heartbeat, rssi, BandType.WIFI_24)
    
    def simulate_step(self):
        """Ejecuta un paso de simulación."""
        for node in self.nodes:
            # Propagar coherencia
            neighbor_data = [
                (info.phi, info.distance)
                for info in node.link.neighbors.values()
            ]
            node.link.coherence.propagate(neighbor_data)
    
    def run(self, steps: int = 100):
        """Ejecuta simulación."""
        print(f"🌐 Simulating {len(self.nodes)} nodes for {steps} steps...")
        
        for step in range(steps):
            self.simulate_step()
            
            if step % 20 == 0:
                avg_phi = np.mean([n.link.coherence.phi for n in self.nodes])
                print(f"   Step {step}: Average Φ = {avg_phi:.3f}")
        
        # Reporte final
        print("\n📊 Final State:")
        for i, node in enumerate(self.nodes):
            print(f"   Node {i}: Φ = {node.link.coherence.phi:.3f}, "
                  f"Neighbors = {len(node.link.neighbors)}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("D10Z-TTA NODAL NETWORK - TEST")
    print("=" * 70)
    
    # Test nodo individual
    print("\n📡 Test Nodo Individual:")
    node = D10ZNode()
    print(f"   ID: {node.node_id.hex()[:16]}...")
    print(f"   Φ inicial: {node.link.coherence.phi:.3f}")
    
    # Test almacenamiento
    print("\n💾 Test Almacenamiento:")
    test_data = b"Hello, D10Z Nodal Network!"
    content_hash = node.store_content(test_data)
    print(f"   Stored: {content_hash}")
    
    # Recuperar
    recovered = node.get_content(compute_hash(test_data))
    print(f"   Recovered: {recovered == test_data}")
    
    # Test simulador de red
    print("\n🌐 Test Simulador de Red:")
    sim = NetworkSimulator(num_nodes=10)
    sim.run(steps=50)
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETO")
    print("=" * 70)
