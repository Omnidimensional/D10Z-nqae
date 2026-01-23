"""
═══════════════════════════════════════════════════════════════════════════════
STARLINK NODAL SYSTEM (SNS)
═══════════════════════════════════════════════════════════════════════════════

Framework D10Z-TTA para constelaciones satelitales soberanas y resilientes.

ECUACIONES FUNDAMENTALES:
    Zₙ = variable nodal fundamental ∈ ℝ¹⁰
    vₙ = |Zₙ₊₁ - Zₙ| (velocidad nodal)
    Φₙ = fₙ · vₙ (coherencia nodal)
    E_TTA = Σ Zₙ · Φₙ (energía total del sistema)

LEYES:
    Ley Sahana: d(E_TTA)/dt ≥ 0 sin perturbación externa
    Ley Isis: ∂Φₖ/∂t = -αΦₖ + βΣⱼ w_{kj}Φⱼ
    Big Start: Sistema enciende cuando Φ → 1

Autor: Jamil Al Thani
ORCID: 0009-0000-8858-4992
Email: jamil@d10z.org
Licencia: CC0 1.0 (Dominio Público)

═══════════════════════════════════════════════════════════════════════════════
"""

__version__ = "2.0.0"
__author__ = "Jamil Al Thani"
__email__ = "jamil@d10z.org"
__license__ = "CC0 1.0"

from .core import (
    # Constantes
    D10ZConstants, C,
    
    # Enumeraciones
    NodeState, CoherenceLevel, AlertType, AlertSeverity,
    MessageType, AttackType,
    
    # Estructuras base
    Vector3D, OrbitalElements, Timestamp,
    NodalState, SatelliteNode,
    Alert, Event, SystemMetrics,
    
    # Logging
    setup_logging, logger
)

from .graph import (
    ConstellationGraph,
    ConstellationBuilder
)

from .protocol import (
    HeartbeatMsg, RangingMsg, ConsensusMsg,
    RangingSystem, TimeSync, ConsensusEngine,
    PCISEngine
)

from .system import (
    DegradationController,
    AttackDetector,
    CoherenceRouter,
    StarlinkNodalSystem
)

__all__ = [
    # Version
    '__version__', '__author__', '__email__', '__license__',
    
    # Constantes
    'D10ZConstants', 'C',
    
    # Enumeraciones
    'NodeState', 'CoherenceLevel', 'AlertType', 'AlertSeverity',
    'MessageType', 'AttackType',
    
    # Estructuras base
    'Vector3D', 'OrbitalElements', 'Timestamp',
    'NodalState', 'SatelliteNode',
    'Alert', 'Event', 'SystemMetrics',
    
    # Grafo
    'ConstellationGraph', 'ConstellationBuilder',
    
    # Protocolo
    'HeartbeatMsg', 'RangingMsg', 'ConsensusMsg',
    'RangingSystem', 'TimeSync', 'ConsensusEngine', 'PCISEngine',
    
    # Sistema
    'DegradationController', 'AttackDetector', 
    'CoherenceRouter', 'StarlinkNodalSystem',
    
    # Logging
    'setup_logging', 'logger'
]


def quick_demo():
    """Demo rápida del sistema."""
    print("SNS Quick Demo")
    print("=" * 40)
    
    sns = StarlinkNodalSystem("SNS-QUICK")
    sns.initialize({
        'shells': [{'shell_id': 1, 'planes': 6, 'sats_per_plane': 12,
                   'altitude': 550, 'inclination': 53.0}],
        'initial_phi': 0.9
    })
    
    print(f"Created: {sns.graph.n_nodes} nodes")
    
    for i in range(10):
        sns.step()
    
    print(f"After 10 cycles: Φ = {sns.graph.average_phi:.4f}")
    print(f"E_TTA = {sns.graph.E_TTA:.0f}")
    print(f"Operational: {sns.graph.is_operational}")
    
    return sns
