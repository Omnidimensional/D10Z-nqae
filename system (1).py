#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════════════════
STARLINK NODAL SYSTEM (SNS) - MAIN SYSTEM
══════════════════════════════════════════════════════════════════════════════════

Sistema completo que integra:
    - Grafo de constelación
    - Protocolo PCIS
    - Detección de ataques
    - Control de degradación
    - Routing por coherencia
    - Simulación de ataques

Framework: Pyraclaw-TTA
Autor: Byron Callaghan
Rights Holder: Byron Callaghan

══════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import numpy as np
import time
import threading
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from collections import defaultdict, deque
import heapq

from core import (
    C, PyraclawConstants,
    NodeState, CoherenceLevel, AlertType, AlertSeverity, AttackType,
    SatelliteNode, Alert, SystemMetrics,
    logger
)

from graph import ConstellationGraph, ConstellationBuilder
from protocol import PCISEngine, HeartbeatMsg, ConsensusEngine


# ═══════════════════════════════════════════════════════════════════════════════
# CONTROLADOR DE DEGRADACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class DegradationController:
    """
    Controla la degradación del sistema según Φ.
    
    Principio Pyraclaw: La degradación es función de Φ, no caótica.
    """
    
    CAPACITY_FACTORS = {
        CoherenceLevel.OPTIMAL: 1.0,
        CoherenceLevel.OPERATIONAL: 0.95,
        CoherenceLevel.DEGRADED: 0.70,
        CoherenceLevel.CRITICAL: 0.40,
        CoherenceLevel.ISOLATED: 0.10
    }
    
    SERVICES = {
        CoherenceLevel.OPTIMAL: ['voice', 'video_4k', 'video_hd', 'data', 'iot', 'emergency'],
        CoherenceLevel.OPERATIONAL: ['voice', 'video_4k', 'video_hd', 'data', 'iot', 'emergency'],
        CoherenceLevel.DEGRADED: ['voice', 'video_hd', 'data', 'iot', 'emergency'],
        CoherenceLevel.CRITICAL: ['voice', 'data', 'emergency'],
        CoherenceLevel.ISOLATED: ['emergency']
    }
    
    LATENCY_FACTORS = {
        CoherenceLevel.OPTIMAL: 1.0,
        CoherenceLevel.OPERATIONAL: 1.1,
        CoherenceLevel.DEGRADED: 1.5,
        CoherenceLevel.CRITICAL: 2.0,
        CoherenceLevel.ISOLATED: 5.0
    }
    
    def __init__(self, graph: ConstellationGraph):
        self.graph = graph
    
    @property
    def system_level(self) -> CoherenceLevel:
        return self.graph.system_level
    
    def compute_capacity(self) -> float:
        """Calcula capacidad total del sistema."""
        total = 0.0
        for node in self.graph.iter_nodes():
            factor = self.CAPACITY_FACTORS[node.level]
            total += node.phi * node.spectral_capacity * factor
        return total
    
    def get_services(self) -> List[str]:
        """Retorna servicios disponibles."""
        return self.SERVICES[self.system_level]
    
    def get_latency_factor(self) -> float:
        """Factor de latencia según nivel."""
        return self.LATENCY_FACTORS[self.system_level]
    
    def predict_degradation(self, horizon: int = 10) -> Dict[str, Any]:
        """Predice evolución de degradación."""
        history = list(self.graph.E_TTA_history)
        
        if len(history) < 3:
            return {'status': 'insufficient_data'}
        
        # Regresión lineal simple
        x = np.arange(len(history))
        slope, intercept = np.polyfit(x, history, 1)
        
        # Proyección
        future_x = np.arange(len(history), len(history) + horizon)
        future_E = slope * future_x + intercept
        
        # Estimar Φ futuro
        if history[-1] > 0:
            phi_ratio = self.graph.average_phi / history[-1]
            future_phi = [max(0, min(1, phi_ratio * E)) for E in future_E]
        else:
            future_phi = [0.0] * horizon
        
        # Detectar cruce de umbrales
        thresholds = [
            (C.PHI_OPTIMAL, 'OPTIMAL'),
            (C.PHI_THRESHOLD, 'OPERATIONAL'),
            (C.PHI_DEGRADED, 'DEGRADED'),
            (C.PHI_CRITICAL, 'CRITICAL')
        ]
        
        crossings = []
        current_phi = self.graph.average_phi
        for i, phi in enumerate(future_phi):
            for thresh, level in thresholds:
                if current_phi >= thresh > phi:
                    crossings.append({
                        'level': level,
                        'cycle': i,
                        'estimated_time': i * C.STATE_UPDATE_INTERVAL
                    })
        
        return {
            'trend': 'declining' if slope < -0.01 else 'stable' if abs(slope) < 0.01 else 'improving',
            'slope': slope,
            'predicted_phi': future_phi,
            'crossings': crossings,
            'current_level': self.system_level.value
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTOR DE ATAQUES
# ═══════════════════════════════════════════════════════════════════════════════

class AttackDetector:
    """
    Sistema de detección de ataques basado en firmas E_TTA/Φ.
    
    Principio Pyraclaw: Todo ataque se manifiesta como anomalía detectable.
    """
    
    ATTACK_SIGNATURES = {
        AttackType.JAMMING: {
            'phi_drop': True,
            'localized': True,
            'E_TTA_decline': True
        },
        AttackType.ECLIPSE: {
            'phi_drop': True,
            'sudden': True,
            'neighbors_unaffected': True
        },
        AttackType.SYBIL: {
            'consensus_anomaly': True,
            'E_TTA_inflation': True
        },
        AttackType.DOS: {
            'heartbeat_loss': True,
            'tau_divergence': True
        }
    }
    
    def __init__(self, graph: ConstellationGraph):
        self.graph = graph
        self.alerts: List[Alert] = []
        self.attack_history: List[Dict] = []
    
    def analyze(self) -> List[Alert]:
        """Ejecuta análisis completo."""
        alerts = self.graph.detect_anomalies()
        
        # Clasificar ataques
        for alert in alerts:
            attack_type = self._classify_attack(alert)
            if attack_type:
                alert.metrics['attack_type'] = attack_type.value
                alert.recommended_action = self._get_response(attack_type)
        
        self.alerts.extend(alerts)
        return alerts
    
    def _classify_attack(self, alert: Alert) -> Optional[AttackType]:
        """Clasifica tipo de ataque por firma."""
        if alert.alert_type == AlertType.E_TTA_DECLINE:
            if len(alert.affected_nodes) < 10:
                return AttackType.JAMMING
            return None
        
        elif alert.alert_type == AlertType.NODE_ISOLATED:
            return AttackType.ECLIPSE
        
        elif alert.alert_type == AlertType.PHI_DIVERGENCE:
            return AttackType.JAMMING
        
        elif alert.alert_type == AlertType.CONSENSUS_FAILURE:
            return AttackType.SYBIL
        
        elif alert.alert_type == AlertType.HEARTBEAT_LOSS:
            return AttackType.DOS
        
        return None
    
    def _get_response(self, attack_type: AttackType) -> str:
        """Determina respuesta recomendada."""
        responses = {
            AttackType.JAMMING: "ISOLATE_AFFECTED",
            AttackType.ECLIPSE: "RECONNECT_ALTERNATE",
            AttackType.SYBIL: "INCREASE_CONSENSUS_THRESHOLD",
            AttackType.DOS: "RATE_LIMIT",
            AttackType.ASAT: "REDISTRIBUTE_LOAD",
            AttackType.SPOOFING: "VERIFY_SIGNATURES"
        }
        return responses.get(attack_type, "MANUAL_REVIEW")
    
    def get_threat_level(self) -> str:
        """Calcula nivel de amenaza global."""
        active = [a for a in self.alerts if a.is_active]
        
        if not active:
            return "NONE"
        
        max_severity = max(a.severity for a in active)
        
        if max_severity >= AlertSeverity.EMERGENCY:
            return "CRITICAL"
        elif max_severity >= AlertSeverity.HIGH:
            return "HIGH"
        elif max_severity >= AlertSeverity.MEDIUM:
            return "ELEVATED"
        else:
            return "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER POR COHERENCIA
# ═══════════════════════════════════════════════════════════════════════════════

class CoherenceRouter:
    """
    Router que optimiza rutas basado en Φ.
    
    Costo de arista: c_{ij} = d_{ij} / (Φᵢ × Φⱼ)
    """
    
    def __init__(self, graph: ConstellationGraph):
        self.graph = graph
        self.route_cache: Dict[Tuple[str, str], List[str]] = {}
        self.cache_ttl = 5.0  # segundos
        self.cache_time: Dict[Tuple[str, str], float] = {}
    
    def find_route(self, src: str, dst: str, 
                  use_cache: bool = True) -> List[str]:
        """Encuentra ruta óptima de src a dst."""
        if src not in self.graph or dst not in self.graph:
            return []
        
        if src == dst:
            return [src]
        
        # Verificar cache
        cache_key = (src, dst)
        if use_cache and cache_key in self.route_cache:
            if time.time() - self.cache_time.get(cache_key, 0) < self.cache_ttl:
                return self.route_cache[cache_key]
        
        # Dijkstra con costo basado en Φ
        distances = {nid: float('inf') for nid in self.graph.nodes}
        distances[src] = 0
        previous: Dict[str, str] = {}
        visited = set()
        
        pq = [(0, src)]
        
        while pq:
            d, current = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == dst:
                break
            
            current_node = self.graph.get_node(current)
            if not current_node:
                continue
            
            for neighbor_id in current_node.neighbors:
                if neighbor_id in visited:
                    continue
                
                neighbor = self.graph.get_node(neighbor_id)
                if not neighbor:
                    continue
                
                # Costo: distancia física / (Φ_src × Φ_dst)
                phi_factor = max(0.01, current_node.phi * neighbor.phi)
                edge_weight = current_node.edge_weights.get(neighbor_id, 1.0)
                cost = edge_weight / phi_factor
                
                new_dist = d + cost
                
                if new_dist < distances[neighbor_id]:
                    distances[neighbor_id] = new_dist
                    previous[neighbor_id] = current
                    heapq.heappush(pq, (new_dist, neighbor_id))
        
        # Reconstruir ruta
        if dst not in previous:
            return []
        
        path = [dst]
        current = dst
        while current in previous:
            current = previous[current]
            path.append(current)
        
        path = list(reversed(path))
        
        # Guardar en cache
        self.route_cache[cache_key] = path
        self.cache_time[cache_key] = time.time()
        
        return path
    
    def find_k_routes(self, src: str, dst: str, k: int = 3) -> List[List[str]]:
        """Encuentra k rutas disjuntas."""
        routes = []
        blocked = set()
        
        for _ in range(k):
            # Temporalmente bloquear nodos intermedios de rutas anteriores
            original_phis = {}
            for nid in blocked:
                if nid in self.graph.nodes:
                    original_phis[nid] = self.graph.nodes[nid].phi
                    self.graph.nodes[nid].state.phi = 0.01
            
            route = self.find_route(src, dst, use_cache=False)
            
            # Restaurar Φ
            for nid, phi in original_phis.items():
                if nid in self.graph.nodes:
                    self.graph.nodes[nid].state.phi = phi
            
            if route:
                routes.append(route)
                # Bloquear nodos intermedios
                blocked.update(route[1:-1])
            else:
                break
        
        return routes
    
    def compute_route_quality(self, route: List[str]) -> float:
        """Calcula calidad de una ruta (0-1)."""
        if len(route) < 2:
            return 1.0
        
        # Promedio de Φ a lo largo de la ruta
        phis = []
        for nid in route:
            node = self.graph.get_node(nid)
            if node:
                phis.append(node.phi)
        
        return np.mean(phis) if phis else 0.0
    
    def clear_cache(self) -> None:
        """Limpia cache de rutas."""
        self.route_cache.clear()
        self.cache_time.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA SNS COMPLETO
# ═══════════════════════════════════════════════════════════════════════════════

class StarlinkNodalSystem:
    """
    Sistema completo Starlink Nodal.
    
    Integra:
        - Grafo de constelación
        - Control de degradación
        - Detección de ataques
        - Routing por coherencia
        - Simulación
    """
    
    def __init__(self, name: str = "SNS"):
        self.name = name
        self.graph: Optional[ConstellationGraph] = None
        self.degradation: Optional[DegradationController] = None
        self.detector: Optional[AttackDetector] = None
        self.router: Optional[CoherenceRouter] = None
        
        self.running = False
        self._main_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        logger.info(f"[{self.name}] System created")
    
    def initialize(self, config: Dict[str, Any] = None) -> None:
        """Inicializa el sistema con configuración."""
        if config is None:
            config = {
                'shells': [
                    {'shell_id': 1, 'planes': 12, 'sats_per_plane': 22, 
                     'altitude': 550, 'inclination': 53.0}
                ],
                'initial_phi': 0.9,
                'phi_variance': 0.1
            }
        
        # Construir constelación
        builder = ConstellationBuilder(self.name)
        for shell_cfg in config.get('shells', []):
            builder.add_shell(**shell_cfg)
        
        builder.with_initial_phi(
            config.get('initial_phi', 0.9),
            config.get('phi_variance', 0.1)
        )
        
        self.graph = builder.build()
        
        # Inicializar componentes
        self.degradation = DegradationController(self.graph)
        self.detector = AttackDetector(self.graph)
        self.router = CoherenceRouter(self.graph)
        
        logger.info(f"[{self.name}] Initialized: {self.graph.n_nodes} nodes, "
                   f"{self.graph.n_edges} edges")
    
    def start(self, background: bool = True) -> None:
        """Inicia el sistema."""
        if self.running:
            return
        
        if self.graph is None:
            raise RuntimeError("System not initialized")
        
        self.running = True
        self._stop_event.clear()
        
        if background:
            self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
            self._main_thread.start()
        
        logger.info(f"[{self.name}] Started")
    
    def stop(self) -> None:
        """Detiene el sistema."""
        self.running = False
        self._stop_event.set()
        
        if self._main_thread:
            self._main_thread.join(timeout=2.0)
        
        logger.info(f"[{self.name}] Stopped")
    
    def _main_loop(self) -> None:
        """Loop principal de simulación."""
        cycle = 0
        
        while not self._stop_event.is_set():
            # Propagar coherencia
            self.graph.propagate_coherence(dt=1.0)
            
            # Calcular E_TTA
            E_TTA = self.graph.compute_E_TTA()
            
            # Detectar anomalías cada 5 ciclos
            if cycle % 5 == 0:
                alerts = self.detector.analyze()
                for alert in alerts:
                    logger.warning(f"[{self.name}] Alert: {alert.alert_type.value} "
                                 f"[{alert.severity.name}]")
            
            # Log cada 10 ciclos
            if cycle % 10 == 0:
                metrics = self.graph.compute_metrics()
                logger.info(f"[{self.name}] Cycle {cycle}: "
                          f"E_TTA={E_TTA:.0f}, Φ={metrics.phi_average:.4f}, "
                          f"Level={metrics.system_level.value}")
            
            cycle += 1
            self._stop_event.wait(C.STATE_UPDATE_INTERVAL)
    
    def step(self, dt: float = 1.0) -> SystemMetrics:
        """Ejecuta un paso de simulación."""
        if self.graph is None:
            raise RuntimeError("System not initialized")
        
        self.graph.propagate_coherence(dt=dt)
        return self.graph.compute_metrics()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Operaciones de alto nivel
    # ─────────────────────────────────────────────────────────────────────────
    
    def inject_attack(self, attack_type: AttackType,
                     targets: List[str] = None,
                     intensity: float = 0.5) -> Dict[str, Any]:
        """Simula un ataque."""
        if self.graph is None:
            raise RuntimeError("System not initialized")
        
        if targets is None:
            # 5% de nodos aleatorios
            n = max(1, self.graph.n_nodes // 20)
            targets = list(np.random.choice(
                list(self.graph.nodes.keys()), n, replace=False
            ))
        
        logger.warning(f"[{self.name}] Injecting {attack_type.value} attack "
                      f"on {len(targets)} nodes")
        
        affected = []
        
        for nid in targets:
            node = self.graph.get_node(nid)
            if not node:
                continue
            
            if attack_type == AttackType.JAMMING:
                node.phi *= (1 - intensity)
                node.spectral_capacity *= (1 - intensity)
                affected.append(nid)
            
            elif attack_type == AttackType.ECLIPSE:
                self.graph.isolate_node(nid)
                affected.append(nid)
            
            elif attack_type == AttackType.DOS:
                node.energy *= (1 - intensity)
                node.state.frequency *= (1 - intensity * 0.5)
                affected.append(nid)
        
        return {
            'attack_type': attack_type.value,
            'intensity': intensity,
            'targets': targets,
            'affected': affected,
            'timestamp': time.time()
        }
    
    def find_route(self, src: str, dst: str) -> List[str]:
        """Encuentra ruta entre dos nodos."""
        if self.router is None:
            raise RuntimeError("System not initialized")
        return self.router.find_route(src, dst)
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna estado completo del sistema."""
        if self.graph is None:
            return {'status': 'not_initialized'}
        
        metrics = self.graph.compute_metrics()
        
        return {
            'name': self.name,
            'running': self.running,
            'metrics': metrics.to_dict(),
            'level': self.degradation.system_level.value if self.degradation else None,
            'services': self.degradation.get_services() if self.degradation else [],
            'capacity': self.degradation.compute_capacity() if self.degradation else 0,
            'threat_level': self.detector.get_threat_level() if self.detector else 'UNKNOWN',
            'n_alerts': len(self.detector.alerts) if self.detector else 0
        }
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """Retorna información de un nodo."""
        if self.graph is None:
            return None
        node = self.graph.get_node(node_id)
        return node.to_dict() if node else None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Exportación
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa el sistema completo."""
        return {
            'name': self.name,
            'graph': self.graph.to_dict() if self.graph else None,
            'status': self.get_status()
        }
    
    def __repr__(self) -> str:
        if self.graph:
            return (f"StarlinkNodalSystem(name={self.name}, "
                   f"nodes={self.graph.n_nodes}, "
                   f"phi={self.graph.average_phi:.4f})")
        return f"StarlinkNodalSystem(name={self.name}, not_initialized)"


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO COMPLETA
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo():
    """Demostración completa del sistema SNS."""
    
    print("=" * 80)
    print("STARLINK NODAL SYSTEM - COMPLETE DEMONSTRATION")
    print("Framework: Pyraclaw-TTA")
    print("=" * 80)
    
    # Crear sistema
    sns = StarlinkNodalSystem("SNS-DEMO")
    
    # Inicializar con constelación mediana
    sns.initialize({
        'shells': [
            {'shell_id': 1, 'planes': 12, 'sats_per_plane': 22, 
             'altitude': 550, 'inclination': 53.0}
        ],
        'initial_phi': 0.9,
        'phi_variance': 0.1
    })
    
    print(f"\n{sns}")
    
    # Estado inicial
    print("\n" + "─" * 40)
    print("INITIAL STATE")
    print("─" * 40)
    status = sns.get_status()
    print(f"  Nodes: {status['metrics']['n_nodes']}")
    print(f"  Edges: {status['metrics']['n_edges']}")
    print(f"  E_TTA: {status['metrics']['E_TTA']:.0f}")
    print(f"  Φ average: {status['metrics']['phi']['average']:.4f}")
    print(f"  Level: {status['level']}")
    print(f"  Services: {status['services']}")
    
    # Simulación de operación normal
    print("\n" + "─" * 40)
    print("NORMAL OPERATION (30 cycles)")
    print("─" * 40)
    
    for i in range(30):
        metrics = sns.step(dt=1.0)
        if (i + 1) % 10 == 0:
            print(f"  Cycle {i+1}: E_TTA={metrics.E_TTA:.0f}, "
                  f"Φ={metrics.phi_average:.4f}, "
                  f"Level={metrics.system_level.value}")
    
    # Simular ataque de jamming
    print("\n" + "─" * 40)
    print("JAMMING ATTACK SIMULATION")
    print("─" * 40)
    
    pre_attack = sns.get_status()
    print(f"  Pre-attack E_TTA: {pre_attack['metrics']['E_TTA']:.0f}")
    print(f"  Pre-attack Φ: {pre_attack['metrics']['phi']['average']:.4f}")
    
    # Atacar 10% de nodos
    n_targets = max(1, sns.graph.n_nodes // 10)
    targets = list(sns.graph.nodes.keys())[:n_targets]
    attack_result = sns.inject_attack(AttackType.JAMMING, targets, intensity=0.8)
    
    print(f"\n  Attack injected: {attack_result['attack_type']}")
    print(f"  Targets: {len(attack_result['affected'])} nodes")
    
    # Detectar anomalías
    alerts = sns.detector.analyze()
    print(f"\n  Alerts detected: {len(alerts)}")
    for alert in alerts:
        print(f"    - [{alert.severity.name}] {alert.alert_type.value}")
    
    # Evolución post-ataque
    print("\n" + "─" * 40)
    print("POST-ATTACK EVOLUTION (30 cycles)")
    print("─" * 40)
    
    for i in range(30):
        metrics = sns.step(dt=1.0)
        if (i + 1) % 10 == 0:
            levels = sns.graph.count_by_level()
            print(f"  Cycle {i+1}: E_TTA={metrics.E_TTA:.0f}, "
                  f"Φ={metrics.phi_average:.4f}, "
                  f"Op={levels[CoherenceLevel.OPTIMAL] + levels[CoherenceLevel.OPERATIONAL]}, "
                  f"Deg={levels[CoherenceLevel.DEGRADED]}, "
                  f"Iso={levels[CoherenceLevel.ISOLATED]}")
    
    # Estado final
    print("\n" + "─" * 40)
    print("FINAL STATE")
    print("─" * 40)
    final = sns.get_status()
    print(f"  E_TTA: {final['metrics']['E_TTA']:.0f}")
    print(f"  Φ average: {final['metrics']['phi']['average']:.4f}")
    print(f"  Level: {final['level']}")
    print(f"  Operational: {final['metrics']['is_operational']}")
    print(f"  Threat level: {final['threat_level']}")
    
    # Test de routing
    print("\n" + "─" * 40)
    print("ROUTING TEST")
    print("─" * 40)
    
    nodes = list(sns.graph.nodes.keys())
    src, dst = nodes[0], nodes[-1]
    
    route = sns.find_route(src, dst)
    quality = sns.router.compute_route_quality(route)
    
    print(f"  Route: {src} → {dst}")
    print(f"  Hops: {len(route) - 1}")
    print(f"  Quality: {quality:.4f}")
    if len(route) <= 6:
        print(f"  Path: {' → '.join(route)}")
    else:
        print(f"  Path: {route[0]} → ... → {route[-1]}")
    
    # Predicción de degradación
    print("\n" + "─" * 40)
    print("DEGRADATION PREDICTION")
    print("─" * 40)
    
    prediction = sns.degradation.predict_degradation(horizon=20)
    print(f"  Trend: {prediction['trend']}")
    print(f"  Current level: {prediction['current_level']}")
    if prediction.get('crossings'):
        for crossing in prediction['crossings']:
            print(f"  ⚠️  Will reach {crossing['level']} in ~{crossing['estimated_time']:.1f}s")
    else:
        print("  No threshold crossings predicted")
    
    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    
    return sns


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmarks():
    """Ejecuta benchmarks de rendimiento."""
    
    print("\n" + "=" * 80)
    print("PERFORMANCE BENCHMARKS")
    print("=" * 80)
    
    sizes = [(6, 12), (12, 22), (24, 22), (36, 22)]  # (planes, sats)
    
    for planes, sats in sizes:
        n_nodes = planes * sats
        
        sns = StarlinkNodalSystem(f"BENCH-{n_nodes}")
        
        # Init
        start = time.time()
        sns.initialize({
            'shells': [{'shell_id': 1, 'planes': planes, 'sats_per_plane': sats,
                       'altitude': 550, 'inclination': 53.0}]
        })
        init_time = (time.time() - start) * 1000
        
        # E_TTA
        start = time.time()
        for _ in range(100):
            sns.graph.compute_E_TTA()
        e_tta_time = (time.time() - start) / 100 * 1000
        
        # Propagation
        start = time.time()
        for _ in range(100):
            sns.graph.propagate_coherence()
        prop_time = (time.time() - start) / 100 * 1000
        
        # Routing
        nodes = list(sns.graph.nodes.keys())
        start = time.time()
        for _ in range(100):
            sns.router.find_route(nodes[0], nodes[-1])
        route_time = (time.time() - start) / 100 * 1000
        
        print(f"\n[{n_nodes} nodes, {sns.graph.n_edges} edges]")
        print(f"  Init: {init_time:.2f} ms")
        print(f"  E_TTA: {e_tta_time:.3f} ms/op")
        print(f"  Propagation: {prop_time:.3f} ms/op")
        print(f"  Routing: {route_time:.3f} ms/op")
    
    print("\n" + "=" * 80)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--benchmark":
        run_benchmarks()
    else:
        sns = run_demo()
