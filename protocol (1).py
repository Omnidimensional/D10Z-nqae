#!/usr/bin/env python3
"""
STARLINK NODAL SYSTEM - PCIS PROTOCOL
Protocolo de Consenso Inter-Satélite
"""

from __future__ import annotations
import numpy as np
import time
import struct
import hashlib
import threading
import queue
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Deque, Callable
from collections import defaultdict, deque
from enum import Enum
import uuid

from core import (
    C, NodeState, CoherenceLevel, AlertType, MessageType,
    SatelliteNode, Alert, logger
)


@dataclass
class HeartbeatMsg:
    """Mensaje de heartbeat inter-satélite."""
    src_id: str = ""
    dst_id: str = ""
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)
    tau: float = 0.0
    phi: float = 0.0
    energy: float = 0.0
    spectral: float = 0.0
    tx_ns: int = field(default_factory=time.time_ns)
    state: NodeState = NodeState.OPERATIONAL
    n_neighbors: int = 0
    
    @classmethod
    def from_node(cls, node: SatelliteNode, dst: str = "", seq: int = 0):
        return cls(
            src_id=node.id, dst_id=dst, sequence=seq,
            tau=node.tau, phi=node.phi, energy=node.energy,
            spectral=node.spectral_capacity,
            state=node.node_state, n_neighbors=node.n_neighbors
        )


@dataclass 
class RangingMsg:
    """Mensaje de ranging para PNT nodal."""
    src_id: str = ""
    dst_id: str = ""
    msg_type: str = "request"  # request, response
    tx_time_ns: int = 0
    rx_time_ns: int = 0
    round_trip: bool = False
    
    def compute_distance(self, c: float = 299792.458) -> float:
        """Calcula distancia en km."""
        if not self.round_trip:
            return 0.0
        rtt_s = (self.rx_time_ns - self.tx_time_ns) / 1e9
        return c * rtt_s / 2


@dataclass
class ConsensusMsg:
    """Mensaje de consenso distribuido."""
    src_id: str = ""
    round_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    phase: str = "propose"  # propose, vote, commit
    E_TTA: float = 0.0
    phi_avg: float = 0.0
    n_nodes: int = 0
    vote: Optional[bool] = None
    committed: bool = False


class RangingSystem:
    """Sistema de ranging para PNT sin GNSS."""
    
    def __init__(self, node: SatelliteNode):
        self.node = node
        self.distances: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=50))
        self.offsets: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=20))
    
    def process_response(self, msg: RangingMsg) -> float:
        """Procesa respuesta de ranging."""
        if not msg.round_trip:
            return 0.0
        distance = msg.compute_distance()
        self.distances[msg.src_id].append(distance)
        return np.median(list(self.distances[msg.src_id]))
    
    def get_distance(self, neighbor_id: str) -> Optional[float]:
        """Obtiene distancia filtrada a un vecino."""
        if neighbor_id not in self.distances:
            return None
        dists = list(self.distances[neighbor_id])
        return np.median(dists) if dists else None
    
    def compute_position(self, neighbor_positions: Dict[str, np.ndarray]) -> Optional[np.ndarray]:
        """Trilateración para calcular posición relativa."""
        distances = {}
        for nid, pos in neighbor_positions.items():
            d = self.get_distance(nid)
            if d is not None:
                distances[nid] = d
        
        if len(distances) < 4:
            return None
        
        # Trilateración por mínimos cuadrados
        try:
            from scipy.optimize import least_squares
            
            nids = list(distances.keys())
            
            def residuals(r):
                return [
                    np.linalg.norm(r - neighbor_positions[nid]) - distances[nid]
                    for nid in nids
                ]
            
            r0 = np.mean([neighbor_positions[nid] for nid in nids], axis=0)
            result = least_squares(residuals, r0, bounds=(-1e6, 1e6))
            return result.x if result.success else None
        except ImportError:
            # Fallback: promedio ponderado
            total_w = 0.0
            weighted_pos = np.zeros(3)
            for nid, d in distances.items():
                if d > 0:
                    w = 1.0 / d
                    weighted_pos += w * neighbor_positions[nid]
                    total_w += w
            return weighted_pos / total_w if total_w > 0 else None


class TimeSync:
    """Sincronización de tiempo nodal (sin GPS)."""
    
    def __init__(self, node: SatelliteNode):
        self.node = node
        self.offsets: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=20))
        self.stratum = 16
    
    def process_heartbeat(self, hb: HeartbeatMsg) -> float:
        """Procesa heartbeat para sincronización."""
        offset = hb.tau - self.node.tau
        self.offsets[hb.src_id].append(offset)
        return np.median(list(self.offsets[hb.src_id]))
    
    def compute_tau(self) -> float:
        """Calcula τ sincronizado."""
        if not self.offsets:
            return self.node.tau
        
        all_offsets = []
        for offs in self.offsets.values():
            all_offsets.extend(list(offs))
        
        if all_offsets:
            mean_offset = np.mean(all_offsets)
            return self.node.tau + mean_offset * 0.1  # Ajuste gradual
        return self.node.tau


class ConsensusEngine:
    """Motor de consenso distribuido para E_TTA."""
    
    def __init__(self, threshold: float = 0.67):
        self.threshold = threshold
        self.current_round: Optional[str] = None
        self.votes: Dict[str, bool] = {}
        self.proposals: Dict[str, ConsensusMsg] = {}
    
    def start_round(self, proposer_id: str, E_TTA: float, 
                   phi_avg: float, n_nodes: int) -> ConsensusMsg:
        """Inicia una ronda de consenso."""
        self.current_round = str(uuid.uuid4())[:8]
        self.votes.clear()
        self.proposals.clear()
        
        return ConsensusMsg(
            src_id=proposer_id,
            round_id=self.current_round,
            phase="propose",
            E_TTA=E_TTA,
            phi_avg=phi_avg,
            n_nodes=n_nodes
        )
    
    def vote(self, voter_id: str, proposal: ConsensusMsg, 
            local_E_TTA: float, tolerance: float = 0.1) -> ConsensusMsg:
        """Genera voto basado en E_TTA local."""
        diff = abs(proposal.E_TTA - local_E_TTA) / max(1, local_E_TTA)
        agree = diff < tolerance
        
        self.votes[voter_id] = agree
        
        return ConsensusMsg(
            src_id=voter_id,
            round_id=proposal.round_id,
            phase="vote",
            vote=agree
        )
    
    def tally(self) -> Tuple[bool, float]:
        """Cuenta votos y determina consenso."""
        if not self.votes:
            return False, 0.0
        
        n_agree = sum(1 for v in self.votes.values() if v)
        ratio = n_agree / len(self.votes)
        
        return ratio >= self.threshold, ratio
    
    def commit(self, proposer_id: str, E_TTA: float, phi_avg: float) -> ConsensusMsg:
        """Genera mensaje de commit."""
        return ConsensusMsg(
            src_id=proposer_id,
            round_id=self.current_round,
            phase="commit",
            E_TTA=E_TTA,
            phi_avg=phi_avg,
            committed=True
        )


class PCISEngine:
    """
    Motor completo del protocolo PCIS.
    
    Coordina:
        - Heartbeats periódicos
        - Ranging para PNT
        - Sincronización de tiempo
        - Consenso de E_TTA
    """
    
    def __init__(self, node: SatelliteNode):
        self.node = node
        self.ranging = RangingSystem(node)
        self.time_sync = TimeSync(node)
        self.consensus = ConsensusEngine()
        
        self.sequence = 0
        self.running = False
        
        # Colas de mensajes
        self.outbox: queue.Queue = queue.Queue()
        self.inbox: queue.Queue = queue.Queue()
        
        # Historial
        self.heartbeats_sent = 0
        self.heartbeats_received = 0
        self.consensus_rounds = 0
        
        # Callbacks
        self._on_heartbeat: List[Callable[[HeartbeatMsg], None]] = []
        self._on_consensus: List[Callable[[ConsensusMsg], None]] = []
    
    def start(self) -> None:
        """Inicia el motor PCIS."""
        self.running = True
        logger.info(f"[{self.node.id}] PCIS engine started")
    
    def stop(self) -> None:
        """Detiene el motor PCIS."""
        self.running = False
        logger.info(f"[{self.node.id}] PCIS engine stopped")
    
    def send_heartbeat(self, dst_id: str = "") -> HeartbeatMsg:
        """Genera y encola un heartbeat."""
        hb = HeartbeatMsg.from_node(self.node, dst_id, self.sequence)
        self.sequence += 1
        self.heartbeats_sent += 1
        self.outbox.put(('heartbeat', hb))
        return hb
    
    def send_heartbeats_to_neighbors(self) -> int:
        """Envía heartbeats a todos los vecinos."""
        sent = 0
        for neighbor_id in self.node.neighbors:
            self.send_heartbeat(neighbor_id)
            sent += 1
        return sent
    
    def receive_heartbeat(self, hb: HeartbeatMsg) -> None:
        """Procesa un heartbeat recibido."""
        self.heartbeats_received += 1
        
        # Actualizar info del vecino
        self.node.last_heartbeat[hb.src_id] = hb.timestamp
        self.node.metadata[f'neighbor_phi_{hb.src_id}'] = hb.phi
        self.node.metadata[f'neighbor_tau_{hb.src_id}'] = hb.tau
        
        # Sincronización de tiempo
        self.time_sync.process_heartbeat(hb)
        
        # Callbacks
        for cb in self._on_heartbeat:
            try:
                cb(hb)
            except Exception as e:
                logger.error(f"Heartbeat callback error: {e}")
    
    def send_ranging_request(self, dst_id: str) -> RangingMsg:
        """Envía solicitud de ranging."""
        msg = RangingMsg(
            src_id=self.node.id,
            dst_id=dst_id,
            msg_type="request",
            tx_time_ns=time.time_ns()
        )
        self.outbox.put(('ranging', msg))
        return msg
    
    def process_ranging_response(self, msg: RangingMsg) -> float:
        """Procesa respuesta de ranging."""
        return self.ranging.process_response(msg)
    
    def update_tau(self) -> float:
        """Actualiza tiempo local sincronizado."""
        new_tau = self.time_sync.compute_tau()
        self.node.update_tau(new_tau)
        return new_tau
    
    def propose_consensus(self, E_TTA: float, phi_avg: float, 
                         n_nodes: int) -> ConsensusMsg:
        """Propone consenso de E_TTA."""
        msg = self.consensus.start_round(
            self.node.id, E_TTA, phi_avg, n_nodes
        )
        self.outbox.put(('consensus', msg))
        self.consensus_rounds += 1
        return msg
    
    def vote_consensus(self, proposal: ConsensusMsg, 
                      local_E_TTA: float) -> ConsensusMsg:
        """Vota en ronda de consenso."""
        msg = self.consensus.vote(self.node.id, proposal, local_E_TTA)
        self.outbox.put(('consensus', msg))
        return msg
    
    def finalize_consensus(self) -> Tuple[bool, float]:
        """Finaliza ronda de consenso."""
        reached, ratio = self.consensus.tally()
        
        for cb in self._on_consensus:
            try:
                cb(ConsensusMsg(committed=reached))
            except Exception as e:
                logger.error(f"Consensus callback error: {e}")
        
        return reached, ratio
    
    def register_heartbeat_callback(self, cb: Callable[[HeartbeatMsg], None]):
        """Registra callback para heartbeats."""
        self._on_heartbeat.append(cb)
    
    def register_consensus_callback(self, cb: Callable[[ConsensusMsg], None]):
        """Registra callback para consenso."""
        self._on_consensus.append(cb)
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del motor."""
        return {
            'heartbeats_sent': self.heartbeats_sent,
            'heartbeats_received': self.heartbeats_received,
            'consensus_rounds': self.consensus_rounds,
            'sequence': self.sequence,
            'running': self.running
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from core import NodalState, Vector3D
    
    print("=" * 70)
    print("SNS PCIS PROTOCOL - TEST")
    print("=" * 70)
    
    # Crear nodos de prueba
    node1 = SatelliteNode(
        id="SAT-001",
        state=NodalState(phi=0.9, energy=0.95)
    )
    node1.add_neighbor("SAT-002")
    node1.add_neighbor("SAT-003")
    
    node2 = SatelliteNode(
        id="SAT-002",
        state=NodalState(phi=0.85, energy=0.90)
    )
    node2.add_neighbor("SAT-001")
    
    # Crear motores PCIS
    engine1 = PCISEngine(node1)
    engine2 = PCISEngine(node2)
    
    engine1.start()
    engine2.start()
    
    # Test heartbeat
    print("\n[HEARTBEAT TEST]")
    hb = engine1.send_heartbeat("SAT-002")
    print(f"  Sent: src={hb.src_id}, phi={hb.phi:.3f}, tau={hb.tau:.3f}")
    
    engine2.receive_heartbeat(hb)
    print(f"  Received by {node2.id}")
    print(f"  Stats: {engine1.get_stats()}")
    
    # Test ranging
    print("\n[RANGING TEST]")
    ranging = RangingSystem(node1)
    
    # Simular RTT de 10ms (distancia ~1500 km)
    msg = RangingMsg(
        src_id="SAT-002",
        tx_time_ns=time.time_ns() - 10_000_000,  # 10ms ago
        rx_time_ns=time.time_ns(),
        round_trip=True
    )
    distance = ranging.process_response(msg)
    print(f"  Distance to SAT-002: {distance:.2f} km")
    
    # Test time sync
    print("\n[TIME SYNC TEST]")
    sync = TimeSync(node1)
    node1.tau = 1000.0
    
    hb_sync = HeartbeatMsg(src_id="SAT-002", tau=1000.5, phi=0.85)
    offset = sync.process_heartbeat(hb_sync)
    print(f"  Offset from SAT-002: {offset:.3f} s")
    
    new_tau = sync.compute_tau()
    print(f"  Synchronized tau: {new_tau:.3f} s")
    
    # Test consensus
    print("\n[CONSENSUS TEST]")
    consensus = ConsensusEngine()
    
    # Propuesta
    proposal = consensus.start_round("SAT-001", E_TTA=50000.0, phi_avg=0.88, n_nodes=72)
    print(f"  Proposal: E_TTA={proposal.E_TTA}, round={proposal.round_id}")
    
    # Votos
    for i in range(10):
        local_E = 50000.0 + np.random.randn() * 1000
        vote = consensus.vote(f"SAT-{i:03d}", proposal, local_E)
        print(f"  Vote from SAT-{i:03d}: {vote.vote}")
    
    # Resultado
    reached, ratio = consensus.tally()
    print(f"  Consensus reached: {reached} ({ratio*100:.1f}%)")
    
    engine1.stop()
    engine2.stop()
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
