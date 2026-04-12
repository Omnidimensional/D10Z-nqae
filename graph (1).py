#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════════════════
STARLINK NODAL SYSTEM (SNS) - GRAPH MODULE
══════════════════════════════════════════════════════════════════════════════════

Grafo nodal de la constelación con implementación completa de:
    - E_TTA = Σ Zₙ · Φₙ
    - Ley Isis de propagación de coherencia
    - Detección de anomalías
    - Métricas del sistema

══════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import numpy as np
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Deque, Any, Set, Iterator, Callable
from collections import defaultdict, deque
import heapq
import json

from core import (
    C, PyraclawConstants,
    NodeState, CoherenceLevel, AlertType, AlertSeverity,
    Vector3D, OrbitalElements, Timestamp,
    NodalState, SatelliteNode,
    Alert, Event, SystemMetrics,
    logger
)


# ═══════════════════════════════════════════════════════════════════════════════
# GRAFO DE CONSTELACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class ConstellationGraph:
    """
    Grafo nodal de la constelación SNS.
    
    Implementa el modelo Pyraclaw donde:
        - Cada satélite es un nodo Zₖ
        - Cada ISL es una arista con peso
        - E_TTA = Σ |Zₖ| · Φₖ es la energía total
        - Φ se propaga según Ley Isis
    
    Thread-safe para operaciones concurrentes.
    """
    
    def __init__(self, name: str = "SNS-CONSTELLATION"):
        self.name = name
        
        # Estructuras principales
        self.nodes: Dict[str, SatelliteNode] = {}
        self.edges: Dict[Tuple[str, str], float] = {}
        
        # Historial de métricas
        self.E_TTA_history: Deque[float] = deque(maxlen=C.MAX_HISTORY_LENGTH)
        self.phi_avg_history: Deque[float] = deque(maxlen=C.MAX_HISTORY_LENGTH)
        self.metrics_history: Deque[SystemMetrics] = deque(maxlen=1000)
        
        # Alertas activas
        self.alerts: List[Alert] = []
        
        # Eventos
        self.events: Deque[Event] = deque(maxlen=10000)
        
        # Epoch del sistema
        self.epoch: float = time.time()
        self.cycle_count: int = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Callbacks
        self._on_alert_callbacks: List[Callable[[Alert], None]] = []
        self._on_node_change_callbacks: List[Callable[[SatelliteNode, str], None]] = []
        
        logger.info(f"[{self.name}] Graph initialized")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Gestión de nodos
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_node(self, node: SatelliteNode) -> None:
        """Agrega un nodo al grafo."""
        with self._lock:
            if node.id in self.nodes:
                logger.warning(f"Node {node.id} already exists, updating")
            
            self.nodes[node.id] = node
            self._emit_event("node_added", node.id, {'phi': node.phi})
            
            for callback in self._on_node_change_callbacks:
                try:
                    callback(node, "added")
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def remove_node(self, node_id: str) -> Optional[SatelliteNode]:
        """Elimina un nodo del grafo."""
        with self._lock:
            if node_id not in self.nodes:
                return None
            
            node = self.nodes[node_id]
            
            # Desconectar de vecinos
            for neighbor_id in list(node.neighbors):
                self._disconnect_nodes(node_id, neighbor_id)
            
            # Eliminar nodo
            del self.nodes[node_id]
            
            self._emit_event("node_removed", node_id, {})
            
            for callback in self._on_node_change_callbacks:
                try:
                    callback(node, "removed")
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            return node
    
    def get_node(self, node_id: str) -> Optional[SatelliteNode]:
        """Obtiene un nodo por ID."""
        return self.nodes.get(node_id)
    
    def has_node(self, node_id: str) -> bool:
        """Verifica si existe un nodo."""
        return node_id in self.nodes
    
    # ─────────────────────────────────────────────────────────────────────────
    # Gestión de aristas (ISL)
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_edge(self, from_id: str, to_id: str, weight: float = 1.0,
                latency: float = 5.0, bidirectional: bool = True) -> bool:
        """Agrega una arista ISL entre dos nodos."""
        with self._lock:
            if from_id not in self.nodes or to_id not in self.nodes:
                logger.warning(f"Cannot add edge: nodes not found ({from_id}, {to_id})")
                return False
            
            if from_id == to_id:
                return False
            
            # Agregar arista
            self.edges[(from_id, to_id)] = weight
            self.nodes[from_id].add_neighbor(to_id, weight, latency)
            
            if bidirectional:
                self.edges[(to_id, from_id)] = weight
                self.nodes[to_id].add_neighbor(from_id, weight, latency)
            
            return True
    
    def remove_edge(self, from_id: str, to_id: str, 
                   bidirectional: bool = True) -> bool:
        """Elimina una arista ISL."""
        with self._lock:
            removed = False
            
            if (from_id, to_id) in self.edges:
                del self.edges[(from_id, to_id)]
                if from_id in self.nodes:
                    self.nodes[from_id].remove_neighbor(to_id)
                removed = True
            
            if bidirectional and (to_id, from_id) in self.edges:
                del self.edges[(to_id, from_id)]
                if to_id in self.nodes:
                    self.nodes[to_id].remove_neighbor(from_id)
                removed = True
            
            return removed
    
    def _disconnect_nodes(self, node_a: str, node_b: str) -> None:
        """Desconecta dos nodos completamente."""
        self.edges.pop((node_a, node_b), None)
        self.edges.pop((node_b, node_a), None)
        
        if node_a in self.nodes:
            self.nodes[node_a].remove_neighbor(node_b)
        if node_b in self.nodes:
            self.nodes[node_b].remove_neighbor(node_a)
    
    def get_edge_weight(self, from_id: str, to_id: str) -> float:
        """Obtiene el peso de una arista."""
        return self.edges.get((from_id, to_id), 0.0)
    
    def has_edge(self, from_id: str, to_id: str) -> bool:
        """Verifica si existe una arista."""
        return (from_id, to_id) in self.edges
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cálculos Pyraclaw
    # ─────────────────────────────────────────────────────────────────────────
    
    def compute_E_TTA(self) -> float:
        """
        Calcula la energía TTA total del sistema.
        
        E_TTA = Σₖ |Zₖ| · Φₖ
        
        Esta es la métrica fundamental de salud del sistema Pyraclaw.
        """
        with self._lock:
            if not self.nodes:
                return 0.0
            
            E = sum(
                node.state_norm * node.phi
                for node in self.nodes.values()
            )
            
            self.E_TTA_history.append(E)
            return E
    
    def compute_nodal_velocity(self, node_id: str) -> float:
        """
        Calcula la velocidad nodal vₙ = promedio |Zⱼ - Zₙ| para vecinos.
        """
        with self._lock:
            if node_id not in self.nodes:
                return 0.0
            
            node = self.nodes[node_id]
            if not node.neighbors:
                return 0.0
            
            velocities = []
            for neighbor_id in node.neighbors:
                if neighbor_id in self.nodes:
                    neighbor = self.nodes[neighbor_id]
                    v = node.state.distance_to(neighbor.state)
                    w = node.edge_weights.get(neighbor_id, 1.0)
                    velocities.append(v * w)
            
            return np.mean(velocities) if velocities else 0.0
    
    def compute_phi_field(self) -> Dict[str, float]:
        """Retorna el campo de coherencia {node_id: Φ}."""
        with self._lock:
            return {nid: node.phi for nid, node in self.nodes.items()}
    
    def propagate_coherence(self, dt: float = 1.0,
                           alpha: float = None,
                           beta: float = None) -> None:
        """
        Propaga la coherencia según la Ley Isis.
        
        ∂Φₖ/∂t = -α·Φₖ + β·Σⱼ w_{kj}·Φⱼ / |Nₖ|
        
        Args:
            dt: Paso de tiempo
            alpha: Tasa de decaimiento (default: C.ALPHA_DECAY)
            beta: Tasa de acoplamiento (default: C.BETA_COUPLING)
        """
        if alpha is None:
            alpha = C.ALPHA_DECAY
        if beta is None:
            beta = C.BETA_COUPLING
        
        with self._lock:
            if not self.nodes:
                return
            
            new_phi = {}
            
            for node_id, node in self.nodes.items():
                # Término de decaimiento local
                decay = -alpha * node.phi
                
                # Término de acoplamiento con vecinos
                coupling = 0.0
                total_weight = 0.0
                
                for neighbor_id in node.neighbors:
                    if neighbor_id in self.nodes:
                        neighbor = self.nodes[neighbor_id]
                        w = node.edge_weights.get(neighbor_id, 1.0)
                        coupling += w * neighbor.phi
                        total_weight += w
                
                if total_weight > 0:
                    coupling = beta * coupling / total_weight
                
                # Integración Euler
                phi_new = node.phi + dt * (decay + coupling)
                
                # Clamp a [0, 1]
                new_phi[node_id] = max(0.0, min(1.0, phi_new))
            
            # Aplicar nuevos valores
            for node_id, phi in new_phi.items():
                self.nodes[node_id].phi = phi
            
            # Actualizar historial promedio
            self.phi_avg_history.append(self.average_phi)
            self.cycle_count += 1
    
    def compute_E_TTA_derivative(self) -> float:
        """
        Calcula dE_TTA/dt (tasa de cambio normalizada).
        
        Usado para detectar anomalías según Ley Sahana.
        """
        if len(self.E_TTA_history) < 2:
            return 0.0
        
        E_current = self.E_TTA_history[-1]
        E_previous = self.E_TTA_history[-2]
        
        if E_previous == 0:
            return 0.0
        
        return (E_current - E_previous) / E_previous
    
    # ─────────────────────────────────────────────────────────────────────────
    # Propiedades del sistema
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def n_nodes(self) -> int:
        return len(self.nodes)
    
    @property
    def n_edges(self) -> int:
        return len(self.edges) // 2  # Bidireccionales
    
    @property
    def average_phi(self) -> float:
        """Coherencia promedio del sistema."""
        with self._lock:
            if not self.nodes:
                return 0.0
            return sum(n.phi for n in self.nodes.values()) / len(self.nodes)
    
    @property
    def min_phi(self) -> float:
        with self._lock:
            if not self.nodes:
                return 0.0
            return min(n.phi for n in self.nodes.values())
    
    @property
    def max_phi(self) -> float:
        with self._lock:
            if not self.nodes:
                return 0.0
            return max(n.phi for n in self.nodes.values())
    
    @property
    def phi_std(self) -> float:
        """Desviación estándar de Φ."""
        with self._lock:
            if not self.nodes:
                return 0.0
            phis = [n.phi for n in self.nodes.values()]
            return float(np.std(phis))
    
    @property
    def is_operational(self) -> bool:
        """Sistema operativo si Φ_promedio ≥ umbral."""
        return self.average_phi >= C.PHI_THRESHOLD
    
    @property
    def system_level(self) -> CoherenceLevel:
        """Nivel de coherencia del sistema."""
        return CoherenceLevel.from_phi(self.average_phi)
    
    @property
    def E_TTA(self) -> float:
        """Último valor de E_TTA calculado."""
        if self.E_TTA_history:
            return self.E_TTA_history[-1]
        return self.compute_E_TTA()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Conteo por niveles
    # ─────────────────────────────────────────────────────────────────────────
    
    def count_by_level(self) -> Dict[CoherenceLevel, int]:
        """Cuenta nodos por nivel de coherencia."""
        with self._lock:
            counts = {level: 0 for level in CoherenceLevel}
            for node in self.nodes.values():
                counts[node.level] += 1
            return counts
    
    def count_by_state(self) -> Dict[NodeState, int]:
        """Cuenta nodos por estado."""
        with self._lock:
            counts = {state: 0 for state in NodeState}
            for node in self.nodes.values():
                counts[node.node_state] += 1
            return counts
    
    @property
    def n_operational(self) -> int:
        return sum(1 for n in self.nodes.values() if n.is_operational)
    
    @property
    def n_degraded(self) -> int:
        return sum(1 for n in self.nodes.values() if n.is_degraded)
    
    @property
    def n_isolated(self) -> int:
        return sum(1 for n in self.nodes.values() if n.is_isolated)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Detección de anomalías
    # ─────────────────────────────────────────────────────────────────────────
    
    def detect_anomalies(self) -> List[Alert]:
        """
        Detecta anomalías en el sistema.
        
        Verifica:
            1. Caída de E_TTA (violación Ley Sahana)
            2. Nodos con Φ crítico
            3. Divergencia de Φ entre vecinos
            4. Pérdida de heartbeats
        """
        alerts = []
        
        with self._lock:
            # 1. Verificar tendencia de E_TTA
            dE = self.compute_E_TTA_derivative()
            if dE < C.E_TTA_DECLINE_THRESHOLD:
                # Identificar nodos con mayor caída
                suspects = self._identify_declining_nodes()
                
                alert = Alert(
                    alert_type=AlertType.E_TTA_DECLINE,
                    severity=AlertSeverity.HIGH if dE < -0.1 else AlertSeverity.MEDIUM,
                    message=f"E_TTA declining at {dE*100:.1f}% per cycle",
                    affected_nodes=suspects,
                    metrics={'dE_TTA': dE, 'E_TTA': self.E_TTA}
                )
                alerts.append(alert)
            
            # 2. Verificar nodos críticos
            critical_nodes = [
                nid for nid, n in self.nodes.items()
                if n.phi < C.PHI_CRITICAL
            ]
            if len(critical_nodes) > max(1, len(self.nodes) * 0.05):
                alert = Alert(
                    alert_type=AlertType.PHI_CRITICAL,
                    severity=AlertSeverity.HIGH,
                    message=f"{len(critical_nodes)} nodes below critical threshold",
                    affected_nodes=critical_nodes,
                    metrics={'n_critical': len(critical_nodes)}
                )
                alerts.append(alert)
            
            # 3. Verificar nodos aislados
            isolated_nodes = [
                nid for nid, n in self.nodes.items()
                if n.is_isolated
            ]
            if isolated_nodes:
                alert = Alert(
                    alert_type=AlertType.NODE_ISOLATED,
                    severity=AlertSeverity.MEDIUM,
                    message=f"{len(isolated_nodes)} nodes isolated",
                    affected_nodes=isolated_nodes,
                    metrics={'n_isolated': len(isolated_nodes)}
                )
                alerts.append(alert)
            
            # 4. Verificar divergencia de Φ
            divergent = self._find_phi_divergent_pairs()
            if divergent:
                affected = list(set([p[0] for p in divergent]))
                alert = Alert(
                    alert_type=AlertType.PHI_DIVERGENCE,
                    severity=AlertSeverity.MEDIUM,
                    message=f"{len(divergent)} neighbor pairs with divergent phi",
                    affected_nodes=affected[:10],
                    metrics={'n_divergent_pairs': len(divergent)}
                )
                alerts.append(alert)
        
        # Registrar alertas
        for alert in alerts:
            self._add_alert(alert)
        
        return alerts
    
    def _identify_declining_nodes(self, top_n: int = 10) -> List[str]:
        """Identifica nodos con mayor caída de Φ."""
        declines = []
        
        for node_id, node in self.nodes.items():
            if len(node.phi_history) >= 2:
                d_phi = node.phi_history[-1] - node.phi_history[-2]
                if d_phi < 0:
                    declines.append((node_id, d_phi))
        
        declines.sort(key=lambda x: x[1])
        return [nid for nid, _ in declines[:top_n]]
    
    def _find_phi_divergent_pairs(self) -> List[Tuple[str, str, float]]:
        """Encuentra pares de vecinos con Φ muy diferente."""
        divergent = []
        checked = set()
        
        for node_id, node in self.nodes.items():
            for neighbor_id in node.neighbors:
                pair = tuple(sorted([node_id, neighbor_id]))
                if pair in checked:
                    continue
                checked.add(pair)
                
                if neighbor_id in self.nodes:
                    neighbor = self.nodes[neighbor_id]
                    diff = abs(node.phi - neighbor.phi)
                    if diff > C.PHI_DIVERGENCE_THRESHOLD:
                        divergent.append((node_id, neighbor_id, diff))
        
        return divergent
    
    def _add_alert(self, alert: Alert) -> None:
        """Agrega una alerta al sistema."""
        self.alerts.append(alert)
        
        for callback in self._on_alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        self._emit_event("alert_raised", alert.source_node or "system", 
                        alert.to_dict())
    
    # ─────────────────────────────────────────────────────────────────────────
    # Métricas del sistema
    # ─────────────────────────────────────────────────────────────────────────
    
    def compute_metrics(self) -> SystemMetrics:
        """Calcula métricas completas del sistema."""
        with self._lock:
            levels = self.count_by_level()
            E = self.compute_E_TTA()
            
            # Capacidad
            total_cap = sum(n.spectral_capacity for n in self.nodes.values())
            avail_cap = sum(
                n.spectral_capacity * n.phi
                for n in self.nodes.values()
            )
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                n_nodes=self.n_nodes,
                n_edges=self.n_edges,
                n_operational=levels[CoherenceLevel.OPTIMAL] + levels[CoherenceLevel.OPERATIONAL],
                n_degraded=levels[CoherenceLevel.DEGRADED],
                n_critical=levels[CoherenceLevel.CRITICAL],
                n_isolated=levels[CoherenceLevel.ISOLATED],
                E_TTA=E,
                phi_average=self.average_phi,
                phi_min=self.min_phi,
                phi_max=self.max_phi,
                phi_std=self.phi_std,
                total_capacity=total_cap,
                available_capacity=avail_cap,
                utilization=avail_cap / total_cap if total_cap > 0 else 0,
                is_operational=self.is_operational,
                system_level=self.system_level,
                n_alerts=len([a for a in self.alerts if a.is_active]),
                n_critical_alerts=len([
                    a for a in self.alerts 
                    if a.is_active and a.severity >= AlertSeverity.CRITICAL
                ])
            )
            
            self.metrics_history.append(metrics)
            return metrics
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna estado completo del sistema."""
        metrics = self.compute_metrics()
        return metrics.to_dict()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Eventos
    # ─────────────────────────────────────────────────────────────────────────
    
    def _emit_event(self, event_type: str, source: str, data: Dict) -> None:
        """Emite un evento del sistema."""
        event = Event(
            event_type=event_type,
            source_node=source,
            data=data
        )
        self.events.append(event)
    
    def register_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Registra callback para alertas."""
        self._on_alert_callbacks.append(callback)
    
    def register_node_callback(self, 
                               callback: Callable[[SatelliteNode, str], None]) -> None:
        """Registra callback para cambios de nodo."""
        self._on_node_change_callbacks.append(callback)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Iteradores
    # ─────────────────────────────────────────────────────────────────────────
    
    def iter_nodes(self) -> Iterator[SatelliteNode]:
        """Itera sobre todos los nodos."""
        return iter(self.nodes.values())
    
    def iter_edges(self) -> Iterator[Tuple[str, str, float]]:
        """Itera sobre todas las aristas (from, to, weight)."""
        seen = set()
        for (from_id, to_id), weight in self.edges.items():
            pair = tuple(sorted([from_id, to_id]))
            if pair not in seen:
                seen.add(pair)
                yield (from_id, to_id, weight)
    
    def iter_neighbors(self, node_id: str) -> Iterator[SatelliteNode]:
        """Itera sobre los vecinos de un nodo."""
        if node_id not in self.nodes:
            return
        for neighbor_id in self.nodes[node_id].neighbors:
            if neighbor_id in self.nodes:
                yield self.nodes[neighbor_id]
    
    # ─────────────────────────────────────────────────────────────────────────
    # Búsqueda y filtrado
    # ─────────────────────────────────────────────────────────────────────────
    
    def find_nodes(self, 
                   predicate: Callable[[SatelliteNode], bool]) -> List[SatelliteNode]:
        """Encuentra nodos que cumplen una condición."""
        return [n for n in self.nodes.values() if predicate(n)]
    
    def find_by_level(self, level: CoherenceLevel) -> List[SatelliteNode]:
        """Encuentra nodos por nivel de coherencia."""
        return [n for n in self.nodes.values() if n.level == level]
    
    def find_by_state(self, state: NodeState) -> List[SatelliteNode]:
        """Encuentra nodos por estado."""
        return [n for n in self.nodes.values() if n.node_state == state]
    
    def find_by_shell(self, shell: int) -> List[SatelliteNode]:
        """Encuentra nodos por shell orbital."""
        return [n for n in self.nodes.values() if n.shell == shell]
    
    def find_by_plane(self, shell: int, plane: int) -> List[SatelliteNode]:
        """Encuentra nodos por plano orbital."""
        return [n for n in self.nodes.values() 
                if n.shell == shell and n.plane == plane]
    
    # ─────────────────────────────────────────────────────────────────────────
    # Serialización
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa el grafo completo."""
        return {
            'name': self.name,
            'epoch': self.epoch,
            'cycle_count': self.cycle_count,
            'nodes': {nid: n.to_dict() for nid, n in self.nodes.items()},
            'edges': [
                {'from': f, 'to': t, 'weight': w}
                for f, t, w in self.iter_edges()
            ],
            'metrics': self.get_status()
        }
    
    def to_adjacency_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """Convierte a matriz de adyacencia."""
        node_ids = list(self.nodes.keys())
        n = len(node_ids)
        id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        
        matrix = np.zeros((n, n))
        for (from_id, to_id), weight in self.edges.items():
            if from_id in id_to_idx and to_id in id_to_idx:
                i, j = id_to_idx[from_id], id_to_idx[to_id]
                matrix[i, j] = weight
        
        return matrix, node_ids
    
    # ─────────────────────────────────────────────────────────────────────────
    # Operaciones de alto nivel
    # ─────────────────────────────────────────────────────────────────────────
    
    def isolate_node(self, node_id: str) -> bool:
        """Aísla un nodo del grafo (desconecta todos los ISLs)."""
        with self._lock:
            if node_id not in self.nodes:
                return False
            
            node = self.nodes[node_id]
            
            for neighbor_id in list(node.neighbors):
                self._disconnect_nodes(node_id, neighbor_id)
            
            node.phi = 0.0
            node.transition_to(NodeState.ISOLATED, "manual isolation")
            
            self._emit_event("node_isolated", node_id, {})
            return True
    
    def reconnect_node(self, node_id: str, 
                      neighbors: List[str], 
                      initial_phi: float = 0.5) -> bool:
        """Reconecta un nodo aislado."""
        with self._lock:
            if node_id not in self.nodes:
                return False
            
            node = self.nodes[node_id]
            
            for neighbor_id in neighbors:
                if neighbor_id in self.nodes:
                    self.add_edge(node_id, neighbor_id)
            
            node.phi = initial_phi
            node.transition_to(NodeState.SYNCHRONIZING, "reconnection")
            
            self._emit_event("node_reconnected", node_id, 
                           {'neighbors': neighbors, 'phi': initial_phi})
            return True
    
    def clear(self) -> None:
        """Limpia el grafo completamente."""
        with self._lock:
            self.nodes.clear()
            self.edges.clear()
            self.E_TTA_history.clear()
            self.phi_avg_history.clear()
            self.alerts.clear()
            self.events.clear()
            self.cycle_count = 0
            self.epoch = time.time()
    
    def __len__(self) -> int:
        return len(self.nodes)
    
    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes
    
    def __repr__(self) -> str:
        return (f"ConstellationGraph(name={self.name}, "
                f"nodes={self.n_nodes}, edges={self.n_edges}, "
                f"phi_avg={self.average_phi:.4f})")


# ═══════════════════════════════════════════════════════════════════════════════
# BUILDER DE CONSTELACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class ConstellationBuilder:
    """
    Constructor de constelaciones satelitales.
    
    Permite crear configuraciones tipo Starlink con múltiples shells.
    """
    
    def __init__(self, name: str = "SNS"):
        self.name = name
        self.shells: List[Dict] = []
        self.initial_phi: float = 0.9
        self.phi_variance: float = 0.1
    
    def add_shell(self, shell_id: int, planes: int, sats_per_plane: int,
                 altitude: float, inclination: float = 53.0) -> 'ConstellationBuilder':
        """Agrega un shell orbital."""
        self.shells.append({
            'shell': shell_id,
            'planes': planes,
            'sats_per_plane': sats_per_plane,
            'altitude': altitude,
            'inclination': inclination
        })
        return self
    
    def with_initial_phi(self, phi: float, variance: float = 0.1) -> 'ConstellationBuilder':
        """Configura Φ inicial."""
        self.initial_phi = phi
        self.phi_variance = variance
        return self
    
    def build(self) -> ConstellationGraph:
        """Construye el grafo de constelación."""
        graph = ConstellationGraph(name=self.name)
        
        # Crear nodos por shell
        for shell_cfg in self.shells:
            self._create_shell(graph, shell_cfg)
        
        # Crear topología ISL
        self._create_topology(graph)
        
        logger.info(f"Built constellation: {graph.n_nodes} nodes, {graph.n_edges} edges")
        return graph
    
    def _create_shell(self, graph: ConstellationGraph, cfg: Dict) -> None:
        """Crea un shell orbital."""
        shell = cfg['shell']
        planes = cfg['planes']
        sats = cfg['sats_per_plane']
        altitude = cfg['altitude']
        inclination = cfg['inclination']
        
        for plane in range(planes):
            raan = 360.0 * plane / planes
            
            for pos in range(sats):
                true_anomaly = 2 * np.pi * pos / sats
                
                # Crear elementos orbitales
                orbital = OrbitalElements(
                    semi_major_axis=C.EARTH_RADIUS + altitude,
                    inclination=inclination,
                    raan=raan,
                    true_anomaly=true_anomaly
                )
                
                # Posición inicial
                position = orbital.to_position()
                
                # Φ inicial con varianza
                phi = self.initial_phi + self.phi_variance * (np.random.random() - 0.5)
                phi = max(0.0, min(1.0, phi))
                
                # Crear nodo
                node_id = f"S{shell}-P{plane:02d}-{pos:02d}"
                node = SatelliteNode(
                    id=node_id,
                    shell=shell,
                    plane=plane,
                    position_in_plane=pos,
                    state=NodalState(
                        position=position,
                        altitude=altitude,
                        phi=phi,
                        energy=0.9 + 0.1 * np.random.random()
                    ),
                    orbital=orbital
                )
                
                graph.add_node(node)
    
    def _create_topology(self, graph: ConstellationGraph) -> None:
        """Crea la topología ISL."""
        # Agrupar nodos por shell y plano
        by_shell_plane: Dict[Tuple[int, int], List[SatelliteNode]] = defaultdict(list)
        
        for node in graph.iter_nodes():
            by_shell_plane[(node.shell, node.plane)].append(node)
        
        # Ordenar por posición en plano
        for nodes in by_shell_plane.values():
            nodes.sort(key=lambda n: n.position_in_plane)
        
        # Conectar intra-plano (anillo)
        for (shell, plane), nodes in by_shell_plane.items():
            n = len(nodes)
            for i in range(n):
                current = nodes[i]
                next_node = nodes[(i + 1) % n]
                graph.add_edge(current.id, next_node.id, weight=1.0, latency=2.0)
        
        # Conectar inter-plano
        shells: Dict[int, Dict[int, List[SatelliteNode]]] = defaultdict(dict)
        for (shell, plane), nodes in by_shell_plane.items():
            shells[shell][plane] = nodes
        
        for shell_id, planes_dict in shells.items():
            plane_nums = sorted(planes_dict.keys())
            n_planes = len(plane_nums)
            
            for i, plane in enumerate(plane_nums):
                next_plane = plane_nums[(i + 1) % n_planes]
                
                nodes_current = planes_dict[plane]
                nodes_next = planes_dict[next_plane]
                
                # Conectar nodos con posición similar
                for node in nodes_current:
                    # Encontrar mejor candidato en plano adyacente
                    best = min(
                        nodes_next,
                        key=lambda n: abs(n.position_in_plane - node.position_in_plane)
                    )
                    
                    if abs(best.position_in_plane - node.position_in_plane) <= 1:
                        graph.add_edge(node.id, best.id, weight=1.2, latency=5.0)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'ConstellationGraph',
    'ConstellationBuilder'
]


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("SNS GRAPH MODULE - TEST")
    print("=" * 70)
    
    # Crear constelación de prueba
    builder = ConstellationBuilder("SNS-TEST")
    builder.add_shell(shell_id=1, planes=6, sats_per_plane=12, 
                     altitude=550.0, inclination=53.0)
    builder.with_initial_phi(0.9, variance=0.1)
    
    graph = builder.build()
    
    print(f"\n{graph}")
    
    # Estado inicial
    metrics = graph.compute_metrics()
    print(f"\nInitial metrics:")
    print(f"  E_TTA: {metrics.E_TTA:.2f}")
    print(f"  Phi average: {metrics.phi_average:.4f}")
    print(f"  Phi range: [{metrics.phi_min:.4f}, {metrics.phi_max:.4f}]")
    print(f"  Operational: {metrics.is_operational}")
    print(f"  Levels: Op={metrics.n_operational}, Deg={metrics.n_degraded}, "
          f"Crit={metrics.n_critical}, Iso={metrics.n_isolated}")
    
    # Propagación de coherencia
    print(f"\nPropagating coherence (20 cycles)...")
    for i in range(20):
        graph.propagate_coherence(dt=1.0)
        if (i + 1) % 5 == 0:
            E = graph.compute_E_TTA()
            print(f"  Cycle {i+1}: E_TTA={E:.2f}, Phi={graph.average_phi:.4f}")
    
    # Simular degradación
    print(f"\nSimulating attack on 10% of nodes...")
    n_attack = max(1, graph.n_nodes // 10)
    attacked = list(graph.nodes.keys())[:n_attack]
    
    for nid in attacked:
        graph.nodes[nid].phi = 0.2
    
    # Detectar anomalías
    print(f"\nDetecting anomalies...")
    alerts = graph.detect_anomalies()
    for alert in alerts:
        print(f"  [{alert.severity.name}] {alert.alert_type.value}: {alert.message}")
    
    # Propagación post-ataque
    print(f"\nPost-attack propagation (20 cycles)...")
    for i in range(20):
        graph.propagate_coherence(dt=1.0)
        if (i + 1) % 5 == 0:
            metrics = graph.compute_metrics()
            print(f"  Cycle {i+1}: E_TTA={metrics.E_TTA:.2f}, "
                  f"Phi={metrics.phi_average:.4f}, "
                  f"Op={metrics.n_operational}, Iso={metrics.n_isolated}")
    
    # Estado final
    print(f"\nFinal state:")
    print(f"  {graph}")
    print(f"  Operational: {graph.is_operational}")
    print(f"  System level: {graph.system_level.value}")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
