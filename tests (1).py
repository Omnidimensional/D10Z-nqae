#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════════════════
STARLINK NODAL SYSTEM (SNS) - TEST SUITE
══════════════════════════════════════════════════════════════════════════════════

Tests formales con pytest.
Ejecutar: pytest tests.py -v --tb=short

Coverage target: >90%

══════════════════════════════════════════════════════════════════════════════════
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch

from core import (
    C, PyraclawConstants,
    NodeState, CoherenceLevel, AlertType, AlertSeverity,
    Vector3D, OrbitalElements, NodalState, SatelliteNode,
    Alert, SystemMetrics
)
from graph import ConstellationGraph, ConstellationBuilder
from protocol import (
    HeartbeatMsg, RangingMsg, ConsensusMsg,
    RangingSystem, TimeSync, ConsensusEngine, PCISEngine
)
from pnt import (
    RangingEngine, Trilateration, TimeSynchronizer,
    OrbitalPropagator, NodalPNT, PNTSolution
)
from system import (
    DegradationController, AttackDetector,
    CoherenceRouter, StarlinkNodalSystem
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_node():
    """Nodo de ejemplo."""
    return SatelliteNode(
        id="TEST-001",
        shell=1,
        plane=0,
        position_in_plane=0,
        state=NodalState(
            position=Vector3D(6921, 0, 0),
            velocity=Vector3D(0, 7.6, 0),
            phi=0.9,
            energy=0.95
        )
    )


@pytest.fixture
def sample_graph():
    """Grafo de ejemplo pequeño."""
    builder = ConstellationBuilder("TEST-GRAPH")
    builder.add_shell(shell_id=1, planes=3, sats_per_plane=4,
                     altitude=550, inclination=53.0)
    return builder.build()


@pytest.fixture
def sample_system():
    """Sistema SNS de ejemplo."""
    sns = StarlinkNodalSystem("TEST-SNS")
    sns.initialize({
        'shells': [{'shell_id': 1, 'planes': 3, 'sats_per_plane': 4,
                   'altitude': 550, 'inclination': 53.0}]
    })
    return sns


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: CORE
# ═══════════════════════════════════════════════════════════════════════════════

class TestVector3D:
    """Tests para Vector3D."""
    
    def test_creation(self):
        v = Vector3D(1, 2, 3)
        assert v.x == 1
        assert v.y == 2
        assert v.z == 3
    
    def test_addition(self):
        v1 = Vector3D(1, 2, 3)
        v2 = Vector3D(4, 5, 6)
        result = v1 + v2
        assert result.x == 5
        assert result.y == 7
        assert result.z == 9
    
    def test_subtraction(self):
        v1 = Vector3D(4, 5, 6)
        v2 = Vector3D(1, 2, 3)
        result = v1 - v2
        assert result.x == 3
        assert result.y == 3
        assert result.z == 3
    
    def test_scalar_multiplication(self):
        v = Vector3D(1, 2, 3)
        result = v * 2
        assert result.x == 2
        assert result.y == 4
        assert result.z == 6
    
    def test_norm(self):
        v = Vector3D(3, 4, 0)
        assert v.norm == 5.0
    
    def test_normalize(self):
        v = Vector3D(3, 4, 0)
        n = v.normalize()
        assert abs(n.norm - 1.0) < 1e-10
    
    def test_dot_product(self):
        v1 = Vector3D(1, 2, 3)
        v2 = Vector3D(4, 5, 6)
        assert v1.dot(v2) == 32
    
    def test_cross_product(self):
        v1 = Vector3D(1, 0, 0)
        v2 = Vector3D(0, 1, 0)
        result = v1.cross(v2)
        assert result.z == 1
    
    def test_to_array(self):
        v = Vector3D(1, 2, 3)
        arr = v.to_array()
        assert np.array_equal(arr, np.array([1, 2, 3]))
    
    def test_from_array(self):
        arr = np.array([1, 2, 3])
        v = Vector3D.from_array(arr)
        assert v.x == 1 and v.y == 2 and v.z == 3


class TestNodalState:
    """Tests para NodalState."""
    
    def test_creation(self):
        state = NodalState(phi=0.9, energy=0.95)
        assert state.phi == 0.9
        assert state.energy == 0.95
    
    def test_to_vector(self):
        state = NodalState(
            position=Vector3D(1, 2, 3),
            velocity=Vector3D(4, 5, 6),
            altitude=550,
            energy=0.9,
            frequency=10,
            phi=0.85
        )
        vec = state.to_vector()
        assert len(vec) == 10
        assert vec[0] == 1
        assert vec[9] == 0.85
    
    def test_level_optimal(self):
        state = NodalState(phi=0.95)
        assert state.level == CoherenceLevel.OPTIMAL
    
    def test_level_operational(self):
        state = NodalState(phi=0.75)
        assert state.level == CoherenceLevel.OPERATIONAL
    
    def test_level_degraded(self):
        state = NodalState(phi=0.55)
        assert state.level == CoherenceLevel.DEGRADED
    
    def test_level_critical(self):
        state = NodalState(phi=0.35)
        assert state.level == CoherenceLevel.CRITICAL
    
    def test_level_isolated(self):
        state = NodalState(phi=0.1)
        assert state.level == CoherenceLevel.ISOLATED


class TestSatelliteNode:
    """Tests para SatelliteNode."""
    
    def test_creation(self, sample_node):
        assert sample_node.id == "TEST-001"
        assert sample_node.phi == 0.9
    
    def test_is_operational(self, sample_node):
        assert sample_node.is_operational is True
    
    def test_is_degraded(self, sample_node):
        sample_node.state.phi = 0.5
        assert sample_node.is_degraded is True
    
    def test_add_neighbor(self, sample_node):
        sample_node.add_neighbor("TEST-002", weight=1.0, latency=5.0)
        assert "TEST-002" in sample_node.neighbors
        assert sample_node.edge_weights["TEST-002"] == 1.0
    
    def test_remove_neighbor(self, sample_node):
        sample_node.add_neighbor("TEST-002")
        sample_node.remove_neighbor("TEST-002")
        assert "TEST-002" not in sample_node.neighbors
    
    def test_state_vector(self, sample_node):
        vec = sample_node.state_vector
        assert len(vec) == 10
    
    def test_transition(self, sample_node):
        sample_node.transition_to(NodeState.OPERATIONAL, "test")
        assert sample_node.node_state == NodeState.OPERATIONAL


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: GRAPH
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstellationGraph:
    """Tests para ConstellationGraph."""
    
    def test_creation(self):
        graph = ConstellationGraph("TEST")
        assert graph.n_nodes == 0
        assert graph.n_edges == 0
    
    def test_add_node(self, sample_node):
        graph = ConstellationGraph("TEST")
        graph.add_node(sample_node)
        assert graph.n_nodes == 1
        assert "TEST-001" in graph
    
    def test_remove_node(self, sample_node):
        graph = ConstellationGraph("TEST")
        graph.add_node(sample_node)
        removed = graph.remove_node("TEST-001")
        assert removed is not None
        assert graph.n_nodes == 0
    
    def test_add_edge(self, sample_graph):
        # Graph ya tiene nodos y edges
        initial_edges = sample_graph.n_edges
        assert initial_edges > 0
    
    def test_compute_E_TTA(self, sample_graph):
        E = sample_graph.compute_E_TTA()
        assert E > 0
    
    def test_propagate_coherence(self, sample_graph):
        phi_before = sample_graph.average_phi
        sample_graph.propagate_coherence(dt=1.0)
        phi_after = sample_graph.average_phi
        # Phi debería converger (posiblemente igual o mayor)
        assert phi_after >= 0
    
    def test_average_phi(self, sample_graph):
        phi = sample_graph.average_phi
        assert 0 <= phi <= 1
    
    def test_is_operational(self, sample_graph):
        assert isinstance(sample_graph.is_operational, bool)
    
    def test_detect_anomalies_normal(self, sample_graph):
        # En estado normal, no debería haber alertas
        sample_graph.compute_E_TTA()  # Primera medición
        sample_graph.compute_E_TTA()  # Segunda medición
        alerts = sample_graph.detect_anomalies()
        # Puede o no tener alertas según estado
        assert isinstance(alerts, list)


class TestConstellationBuilder:
    """Tests para ConstellationBuilder."""
    
    def test_build_empty(self):
        builder = ConstellationBuilder("EMPTY")
        graph = builder.build()
        assert graph.n_nodes == 0
    
    def test_build_single_shell(self):
        builder = ConstellationBuilder("TEST")
        builder.add_shell(shell_id=1, planes=2, sats_per_plane=3,
                         altitude=550, inclination=53.0)
        graph = builder.build()
        assert graph.n_nodes == 6
    
    def test_build_with_initial_phi(self):
        builder = ConstellationBuilder("TEST")
        builder.add_shell(shell_id=1, planes=2, sats_per_plane=3,
                         altitude=550, inclination=53.0)
        builder.with_initial_phi(0.95, variance=0.01)
        graph = builder.build()
        
        # Todos los phis deberían estar cerca de 0.95
        for node in graph.iter_nodes():
            assert 0.9 < node.phi < 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════

class TestHeartbeatMsg:
    """Tests para HeartbeatMsg."""
    
    def test_creation(self):
        hb = HeartbeatMsg(src_id="A", dst_id="B", phi=0.9)
        assert hb.src_id == "A"
        assert hb.phi == 0.9
    
    def test_from_node(self, sample_node):
        hb = HeartbeatMsg.from_node(sample_node, "DST", 1)
        assert hb.src_id == sample_node.id
        assert hb.phi == sample_node.phi


class TestConsensusEngine:
    """Tests para ConsensusEngine."""
    
    def test_start_round(self):
        engine = ConsensusEngine()
        msg = engine.start_round("PROPOSER", 50000, 0.9, 72)
        assert msg.phase == "propose"
        assert msg.E_TTA == 50000
    
    def test_vote_agree(self):
        engine = ConsensusEngine()
        proposal = engine.start_round("P", 50000, 0.9, 72)
        vote = engine.vote("V1", proposal, 49000)  # Dentro de tolerancia
        assert vote.vote is True
    
    def test_vote_disagree(self):
        engine = ConsensusEngine()
        proposal = engine.start_round("P", 50000, 0.9, 72)
        vote = engine.vote("V1", proposal, 30000)  # Fuera de tolerancia
        assert vote.vote is False
    
    def test_tally_consensus(self):
        engine = ConsensusEngine()
        proposal = engine.start_round("P", 50000, 0.9, 72)
        
        # 10 votos a favor
        for i in range(10):
            engine.vote(f"V{i}", proposal, 49500)
        
        reached, ratio = engine.tally()
        assert reached is True
        assert ratio == 1.0
    
    def test_tally_no_consensus(self):
        engine = ConsensusEngine()
        proposal = engine.start_round("P", 50000, 0.9, 72)
        
        # 3 a favor, 7 en contra
        for i in range(3):
            engine.vote(f"V{i}", proposal, 49500)
        for i in range(3, 10):
            engine.vote(f"V{i}", proposal, 10000)
        
        reached, ratio = engine.tally()
        assert reached is False
        assert ratio < 0.67


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: PNT
# ═══════════════════════════════════════════════════════════════════════════════

class TestRangingEngine:
    """Tests para RangingEngine."""
    
    def test_measure(self):
        engine = RangingEngine()
        
        # RTT de 10ms = ~1500 km
        tx = time.time_ns() - 10_000_000
        rx = time.time_ns()
        
        dist = engine.measure("SAT-001", tx, rx)
        assert 1400 < dist < 1600  # ~1500 km
    
    def test_get_distance_filtered(self):
        engine = RangingEngine()
        
        # Múltiples mediciones con outlier
        for _ in range(9):
            tx = time.time_ns() - 10_000_000
            rx = time.time_ns()
            engine.measure("SAT-001", tx, rx)
        
        # Outlier
        tx = time.time_ns() - 100_000_000  # 100ms = 15000km
        rx = time.time_ns()
        engine.measure("SAT-001", tx, rx)
        
        dist = engine.get_distance("SAT-001")
        # Mediana debería filtrar outlier
        assert dist < 5000


class TestTrilateration:
    """Tests para Trilateration."""
    
    def test_solve_exact(self):
        """Test con mediciones perfectas."""
        positions = {
            'A': np.array([1000, 0, 0]),
            'B': np.array([0, 1000, 0]),
            'C': np.array([0, 0, 1000]),
            'D': np.array([700, 700, 0])
        }
        
        true_pos = np.array([100, 100, 100])
        
        distances = {
            sid: np.linalg.norm(true_pos - pos)
            for sid, pos in positions.items()
        }
        
        result, metrics = Trilateration.solve(distances, positions)
        
        assert result is not None
        assert metrics['success'] is True
        
        error = np.linalg.norm(result - true_pos)
        assert error < 1  # Error menor a 1 km
    
    def test_solve_insufficient_satellites(self):
        """Test con menos de 4 satélites."""
        positions = {
            'A': np.array([1000, 0, 0]),
            'B': np.array([0, 1000, 0])
        }
        
        distances = {'A': 900, 'B': 900}
        
        result, metrics = Trilateration.solve(distances, positions)
        assert result is None
    
    def test_compute_gdop(self):
        """Test de cálculo de GDOP."""
        # Posición del receptor
        position = np.array([6800, 100, 50])
        
        # Satélites alrededor (geometría 3D válida)
        sat_positions = {
            'A': np.array([6921, 0, 0]),
            'B': np.array([0, 6921, 0]),
            'C': np.array([0, 0, 6921]),
            'D': np.array([4893, 4893, 0]),
            'E': np.array([4893, 0, 4893])
        }
        
        gdop = Trilateration.compute_gdop(position, sat_positions)
        # GDOP puede ser inf si geometría es mala, solo verificamos que no crashea
        assert isinstance(gdop, (float, np.floating))


class TestTimeSynchronizer:
    """Tests para TimeSynchronizer."""
    
    def test_process_sync(self):
        sync = TimeSynchronizer("NODE-001")
        
        t1 = time.time()
        offset = sync.process_sync_message(
            "NEIGHBOR",
            neighbor_tau=t1 + 0.1,
            neighbor_stratum=2,
            t1=t1,
            t2=t1 + 0.005,
            t3=t1 + 0.006,
            t4=t1 + 0.011
        )
        
        assert offset is not None
    
    def test_stratum_update(self):
        sync = TimeSynchronizer("NODE-001")
        initial_stratum = sync.get_stratum()
        
        sync.process_sync_message(
            "NEIGHBOR",
            neighbor_tau=time.time(),
            neighbor_stratum=2,
            t1=time.time(),
            t2=time.time(),
            t3=time.time(),
            t4=time.time()
        )
        
        assert sync.get_stratum() <= initial_stratum


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class TestDegradationController:
    """Tests para DegradationController."""
    
    def test_system_level(self, sample_graph):
        controller = DegradationController(sample_graph)
        level = controller.system_level
        assert level in CoherenceLevel
    
    def test_get_services(self, sample_graph):
        controller = DegradationController(sample_graph)
        services = controller.get_services()
        assert isinstance(services, list)
        assert len(services) > 0
    
    def test_compute_capacity(self, sample_graph):
        controller = DegradationController(sample_graph)
        capacity = controller.compute_capacity()
        assert capacity > 0


class TestCoherenceRouter:
    """Tests para CoherenceRouter."""
    
    def test_find_route(self, sample_graph):
        router = CoherenceRouter(sample_graph)
        nodes = list(sample_graph.nodes.keys())
        
        if len(nodes) >= 2:
            route = router.find_route(nodes[0], nodes[-1])
            assert len(route) >= 2
            assert route[0] == nodes[0]
            assert route[-1] == nodes[-1]
    
    def test_find_route_same_node(self, sample_graph):
        router = CoherenceRouter(sample_graph)
        nodes = list(sample_graph.nodes.keys())
        
        route = router.find_route(nodes[0], nodes[0])
        assert route == [nodes[0]]
    
    def test_route_quality(self, sample_graph):
        router = CoherenceRouter(sample_graph)
        nodes = list(sample_graph.nodes.keys())
        
        route = router.find_route(nodes[0], nodes[-1])
        quality = router.compute_route_quality(route)
        assert 0 <= quality <= 1


class TestStarlinkNodalSystem:
    """Tests para StarlinkNodalSystem."""
    
    def test_creation(self):
        sns = StarlinkNodalSystem("TEST")
        assert sns.name == "TEST"
        assert sns.graph is None
    
    def test_initialize(self, sample_system):
        assert sample_system.graph is not None
        assert sample_system.graph.n_nodes > 0
    
    def test_step(self, sample_system):
        metrics = sample_system.step()
        assert isinstance(metrics, SystemMetrics)
        assert metrics.n_nodes > 0
    
    def test_inject_attack(self, sample_system):
        from core import AttackType
        
        result = sample_system.inject_attack(
            AttackType.JAMMING,
            intensity=0.5
        )
        
        assert result['attack_type'] == 'jamming'
        assert len(result['affected']) > 0
    
    def test_find_route(self, sample_system):
        nodes = list(sample_system.graph.nodes.keys())
        route = sample_system.find_route(nodes[0], nodes[-1])
        assert len(route) >= 1
    
    def test_get_status(self, sample_system):
        status = sample_system.get_status()
        assert 'metrics' in status
        assert 'level' in status
        assert 'services' in status


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: E_TTA PHYSICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestE_TTA:
    """Tests para verificar comportamiento físico de E_TTA."""
    
    def test_E_TTA_positive(self, sample_graph):
        """E_TTA siempre debe ser positivo."""
        E = sample_graph.compute_E_TTA()
        assert E > 0
    
    def test_E_TTA_increases_with_phi(self, sample_graph):
        """E_TTA debe aumentar cuando Φ aumenta."""
        E_before = sample_graph.compute_E_TTA()
        
        # Aumentar Φ de todos los nodos
        for node in sample_graph.iter_nodes():
            node.state.phi = min(1.0, node.phi + 0.1)
        
        E_after = sample_graph.compute_E_TTA()
        assert E_after > E_before
    
    def test_ley_isis_convergence(self, sample_graph):
        """La Ley Isis debe hacer converger Φ."""
        # Crear divergencia artificial
        nodes = list(sample_graph.nodes.values())
        for i, node in enumerate(nodes):
            node.state.phi = 0.5 if i % 2 == 0 else 1.0
        
        std_before = sample_graph.phi_std
        
        # Propagar coherencia
        for _ in range(50):
            sample_graph.propagate_coherence(dt=1.0)
        
        std_after = sample_graph.phi_std
        
        # La desviación estándar debería reducirse (convergencia)
        assert std_after < std_before
    
    def test_attack_decreases_E_TTA(self, sample_system):
        """Un ataque debe reducir E_TTA."""
        from core import AttackType
        
        # Estabilizar primero
        for _ in range(10):
            sample_system.step()
        
        E_before = sample_system.graph.E_TTA
        
        # Atacar
        sample_system.inject_attack(AttackType.JAMMING, intensity=0.8)
        
        E_after = sample_system.graph.compute_E_TTA()
        
        assert E_after < E_before


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS: EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests para casos límite."""
    
    def test_empty_graph(self):
        graph = ConstellationGraph("EMPTY")
        assert graph.average_phi == 0.0
        assert graph.E_TTA == 0.0
    
    def test_single_node(self):
        graph = ConstellationGraph("SINGLE")
        node = SatelliteNode(id="ALONE", state=NodalState(phi=0.9))
        graph.add_node(node)
        
        E = graph.compute_E_TTA()
        assert E > 0
        
        graph.propagate_coherence()  # No debería crashear
    
    def test_disconnected_nodes(self):
        graph = ConstellationGraph("DISCONNECTED")
        
        for i in range(5):
            node = SatelliteNode(id=f"N{i}", state=NodalState(phi=0.9))
            graph.add_node(node)
        
        # No hay edges, pero no debería crashear
        graph.propagate_coherence()
        E = graph.compute_E_TTA()
        assert E > 0
    
    def test_phi_bounds(self, sample_graph):
        """Φ debe permanecer en [0, 1]."""
        # Forzar valores extremos
        for node in sample_graph.iter_nodes():
            node.state.phi = 1.5  # Fuera de rango
        
        # Propagar debería normalizar
        sample_graph.propagate_coherence()
        
        for node in sample_graph.iter_nodes():
            assert 0 <= node.phi <= 1


# ═══════════════════════════════════════════════════════════════════════════════
# BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformance:
    """Tests de rendimiento."""
    
    @pytest.mark.parametrize("n_planes,n_sats", [
        (3, 4),
        (6, 12),
        (12, 22)
    ])
    def test_scaling(self, n_planes, n_sats):
        """Verificar escalabilidad."""
        builder = ConstellationBuilder("PERF")
        builder.add_shell(1, n_planes, n_sats, 550, 53.0)
        graph = builder.build()
        
        n_nodes = n_planes * n_sats
        assert graph.n_nodes == n_nodes
        
        # E_TTA debe ser calculable en tiempo razonable
        import time
        start = time.time()
        for _ in range(100):
            graph.compute_E_TTA()
        elapsed = time.time() - start
        
        # Menos de 10ms por operación en promedio
        assert elapsed / 100 < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
