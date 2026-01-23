#!/usr/bin/env python3
"""
STARLINK NODAL SYSTEM (SNS) - IMPLEMENTACIÓN D10Z-TTA
Autor: Jamil Al Thani | ORCID: 0009-0000-8858-4992
Licencia: CC0 1.0 (Dominio Público)
"""

import numpy as np
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Deque, Any
from collections import defaultdict, deque
from enum import Enum
import heapq

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES D10Z
# ═══════════════════════════════════════════════════════════════════════════════

GM_10_51 = 1e-51
PHI_THRESHOLD = 0.7
PHI_CRITICAL = 0.3
PHI_DEGRADED = 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# ESTRUCTURAS
# ═══════════════════════════════════════════════════════════════════════════════

class NodeState(Enum):
    INITIALIZING = "initializing"
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    ISOLATED = "isolated"


@dataclass
class SatelliteNode:
    """Nodo satelital bajo ontología D10Z."""
    id: str
    shell: int = 1
    plane: int = 0
    position: int = 0
    position_rel: np.ndarray = field(default_factory=lambda: np.zeros(3))
    velocity_rel: np.ndarray = field(default_factory=lambda: np.zeros(3))
    altitude: float = 550.0
    energy: float = 1.0
    frequency: float = 10.0
    phi: float = 1.0
    tau: float = 0.0
    spectral_cap: float = 1.0
    neighbors: List[str] = field(default_factory=list)
    edge_weights: Dict[str, float] = field(default_factory=dict)
    state: NodeState = NodeState.INITIALIZING
    health_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def state_vector(self) -> np.ndarray:
        return np.concatenate([
            self.position_rel, self.velocity_rel,
            [self.altitude, self.energy, self.frequency, self.phi]
        ])
    
    @property
    def state_norm(self) -> float:
        return np.linalg.norm(self.state_vector)
    
    @property
    def level(self) -> str:
        if self.phi >= 0.9: return "OPTIMAL"
        elif self.phi >= PHI_THRESHOLD: return "OPERATIONAL"
        elif self.phi >= PHI_DEGRADED: return "DEGRADED"
        elif self.phi >= PHI_CRITICAL: return "CRITICAL"
        else: return "ISOLATED"


class ConstellationGraph:
    """Grafo nodal de la constelación SNS."""
    
    def __init__(self):
        self.nodes: Dict[str, SatelliteNode] = {}
        self.edges: Dict[Tuple[str, str], float] = {}
        self.E_TTA_history: Deque[float] = deque(maxlen=1000)
    
    def add_satellite(self, node: SatelliteNode):
        self.nodes[node.id] = node
    
    def add_isl(self, from_id: str, to_id: str, weight: float = 1.0):
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ValueError("Nodos no registrados")
        if (from_id, to_id) in self.edges:
            return
        self.edges[(from_id, to_id)] = weight
        self.edges[(to_id, from_id)] = weight
        if to_id not in self.nodes[from_id].neighbors:
            self.nodes[from_id].neighbors.append(to_id)
        if from_id not in self.nodes[to_id].neighbors:
            self.nodes[to_id].neighbors.append(from_id)
        self.nodes[from_id].edge_weights[to_id] = weight
        self.nodes[to_id].edge_weights[from_id] = weight
    
    def compute_E_TTA(self) -> float:
        """E_TTA = Σ |Zₖ| · Φₖ"""
        if not self.nodes:
            return 0.0
        E = sum(n.state_norm * n.phi for n in self.nodes.values())
        self.E_TTA_history.append(E)
        return E
    
    def propagate_coherence(self, dt: float = 1.0, alpha: float = 0.05, beta: float = 0.2):
        """Ley Isis: ∂Φₖ/∂t = -α·Φₖ + β·Σⱼ w_{kj}·Φⱼ / |Nₖ|"""
        new_phi = {}
        for nid, node in self.nodes.items():
            decay = -alpha * node.phi
            coupling = 0.0
            if node.neighbors:
                for neighbor_id in node.neighbors:
                    if neighbor_id in self.nodes:
                        w = node.edge_weights.get(neighbor_id, 1.0)
                        coupling += w * self.nodes[neighbor_id].phi
                coupling *= beta / len(node.neighbors)
            new_phi[nid] = max(0.0, min(1.0, node.phi + dt * (decay + coupling)))
        for nid, phi in new_phi.items():
            self.nodes[nid].phi = phi
            self.nodes[nid].health_history.append(phi)
    
    @property
    def average_phi(self) -> float:
        if not self.nodes: return 0.0
        return sum(n.phi for n in self.nodes.values()) / len(self.nodes)
    
    @property
    def is_operational(self) -> bool:
        return self.average_phi >= PHI_THRESHOLD
    
    def get_status(self) -> Dict[str, Any]:
        E = self.compute_E_TTA()
        levels = {"OPTIMAL": 0, "OPERATIONAL": 0, "DEGRADED": 0, "CRITICAL": 0, "ISOLATED": 0}
        for n in self.nodes.values():
            levels[n.level] += 1
        return {
            'n_nodes': len(self.nodes),
            'n_edges': len(self.edges) // 2,
            'E_TTA': E,
            'phi_avg': self.average_phi,
            'phi_min': min(n.phi for n in self.nodes.values()) if self.nodes else 0,
            'phi_max': max(n.phi for n in self.nodes.values()) if self.nodes else 0,
            'operational': self.is_operational,
            'levels': levels
        }


class CoherenceRouter:
    """Router basado en Φ."""
    
    def __init__(self, graph: ConstellationGraph):
        self.graph = graph
    
    def find_route(self, src: str, dst: str) -> List[str]:
        if src not in self.graph.nodes or dst not in self.graph.nodes:
            return []
        distances = {nid: float('inf') for nid in self.graph.nodes}
        distances[src] = 0
        previous = {}
        pq = [(0, src)]
        visited = set()
        
        while pq:
            d, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)
            if current == dst:
                break
            node = self.graph.nodes[current]
            for neighbor_id in node.neighbors:
                if neighbor_id not in self.graph.nodes or neighbor_id in visited:
                    continue
                neighbor = self.graph.nodes[neighbor_id]
                phi_factor = max(0.01, node.phi * neighbor.phi)
                cost = node.edge_weights.get(neighbor_id, 1.0) / phi_factor
                new_d = d + cost
                if new_d < distances[neighbor_id]:
                    distances[neighbor_id] = new_d
                    previous[neighbor_id] = current
                    heapq.heappush(pq, (new_d, neighbor_id))
        
        if dst not in previous and src != dst:
            return []
        path = [dst]
        current = dst
        while current != src and current in previous:
            current = previous[current]
            path.append(current)
        return list(reversed(path))


class StarlinkNodalSystem:
    """Sistema completo SNS."""
    
    def __init__(self, name: str = "SNS"):
        self.name = name
        self.graph = ConstellationGraph()
        self.router = CoherenceRouter(self.graph)
    
    def initialize(self, shells: List[Dict] = None):
        if shells is None:
            shells = [{'shell': 1, 'planes': 6, 'sats_per_plane': 12, 'altitude': 550}]
        for cfg in shells:
            self._create_shell(cfg)
        self._create_topology()
        print(f"[{self.name}] Inicializado: {len(self.graph.nodes)} nodos, "
              f"{len(self.graph.edges)//2} ISLs")
    
    def _create_shell(self, cfg: Dict):
        shell, planes, sats, alt = cfg['shell'], cfg['planes'], cfg['sats_per_plane'], cfg['altitude']
        for plane in range(planes):
            for pos in range(sats):
                nid = f"S{shell}-P{plane:02d}-{pos:02d}"
                theta = 2 * np.pi * pos / sats
                node = SatelliteNode(
                    id=nid, shell=shell, plane=plane, position=pos,
                    altitude=alt,
                    position_rel=np.array([alt * np.cos(theta), alt * np.sin(theta), plane * 10]),
                    phi=0.85 + 0.15 * np.random.random(),
                    energy=0.9 + 0.1 * np.random.random()
                )
                self.graph.add_satellite(node)
    
    def _create_topology(self):
        by_plane = defaultdict(list)
        for nid, n in self.graph.nodes.items():
            by_plane[(n.shell, n.plane)].append(n)
        
        # Intra-plano
        for nodes in by_plane.values():
            nodes.sort(key=lambda n: n.position)
            for i in range(len(nodes)):
                self.graph.add_isl(nodes[i].id, nodes[(i+1) % len(nodes)].id)
        
        # Inter-plano
        shells = defaultdict(dict)
        for (shell, plane), nodes in by_plane.items():
            shells[shell][plane] = nodes
        for shell, planes_dict in shells.items():
            plane_nums = sorted(planes_dict.keys())
            for i, plane in enumerate(plane_nums):
                next_plane = plane_nums[(i+1) % len(plane_nums)]
                for node in planes_dict[plane]:
                    if next_plane in planes_dict:
                        candidates = [n for n in planes_dict[next_plane] 
                                     if abs(n.position - node.position) <= 1]
                        if candidates:
                            target = min(candidates, key=lambda n: abs(n.position - node.position))
                            self.graph.add_isl(node.id, target.id, weight=1.2)
    
    def inject_attack(self, attack_type: str, targets: List[str] = None, intensity: float = 0.5):
        if targets is None:
            n = max(1, len(self.graph.nodes) // 20)
            targets = list(np.random.choice(list(self.graph.nodes.keys()), n, replace=False))
        print(f"[{self.name}] Ataque '{attack_type}' en {len(targets)} nodos")
        for nid in targets:
            if nid in self.graph.nodes:
                node = self.graph.nodes[nid]
                if attack_type == 'jamming':
                    node.phi *= (1 - intensity)
                    node.spectral_cap *= (1 - intensity)
                elif attack_type == 'eclipse':
                    node.phi = 0.0
                    node.neighbors.clear()
    
    def status(self) -> Dict:
        s = self.graph.get_status()
        s['name'] = self.name
        return s


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    print("=" * 70)
    print("STARLINK NODAL SYSTEM - D10Z-TTA DEMO")
    print("=" * 70)
    
    sns = StarlinkNodalSystem("SNS-DEMO")
    sns.initialize()
    
    print("\n[INICIAL]")
    s = sns.status()
    print(f"  E_TTA: {s['E_TTA']:.2f}, Φ: {s['phi_avg']:.4f}, Op: {s['operational']}")
    
    print("\n[EVOLUCIÓN NORMAL] 20 ciclos...")
    for i in range(20):
        sns.graph.propagate_coherence()
        if i % 5 == 0:
            print(f"  Ciclo {i}: E_TTA={sns.graph.compute_E_TTA():.2f}, Φ={sns.graph.average_phi:.4f}")
    
    print("\n[ATAQUE JAMMING]")
    targets = list(sns.graph.nodes.keys())[:8]
    sns.inject_attack('jamming', targets, 0.8)
    
    print("\n[POST-ATAQUE] 20 ciclos...")
    for i in range(20):
        sns.graph.propagate_coherence()
        if i % 5 == 0:
            s = sns.status()
            print(f"  Ciclo {i}: E_TTA={s['E_TTA']:.2f}, Φ={s['phi_avg']:.4f}, "
                  f"Levels={s['levels']}")
    
    print("\n[FINAL]")
    s = sns.status()
    print(f"  E_TTA: {s['E_TTA']:.2f}")
    print(f"  Φ: {s['phi_avg']:.4f}")
    print(f"  Operativo: {s['operational']}")
    print(f"  Niveles: {s['levels']}")
    
    print("\n[ROUTING TEST]")
    nodes = list(sns.graph.nodes.keys())
    route = sns.router.find_route(nodes[0], nodes[-1])
    print(f"  Ruta {nodes[0]} → {nodes[-1]}: {len(route)} saltos")
    
    print("\n" + "=" * 70)
    print("FIN DEMO")
    print("=" * 70)
    
    return sns


if __name__ == "__main__":
    demo()
