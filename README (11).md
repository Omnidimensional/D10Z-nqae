# STARLINK NODAL SYSTEM (SNS)
## Framework D10Z-TTA para Constelaciones Soberanas

[![License: CC0](https://img.shields.io/badge/License-CC0_1.0-lightgrey.svg)](https://creativecommons.org/publicdomain/zero/1.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Framework: D10Z-TTA](https://img.shields.io/badge/framework-D10Z--TTA-purple.svg)](https://d10z.org)

---

## Ecuaciones Fundamentales

```
Zₙ = variable nodal fundamental ∈ ℝ¹⁰
vₙ = |Zₙ₊₁ - Zₙ|           (velocidad nodal)
Φₙ = fₙ · vₙ               (coherencia nodal)
E_TTA = Σ Zₙ · Φₙ          (energía total)
```

## Leyes D10Z

| Ley | Ecuación | Significado |
|-----|----------|-------------|
| **Sahana** | d(E_TTA)/dt ≥ 0 | Sin perturbación, E_TTA no decrece |
| **Isis** | ∂Φₖ/∂t = -αΦₖ + βΣwΦⱼ | Coherencia se propaga por el grafo |
| **Big Start** | Φ → 1 | Sistema "enciende" al alcanzar coherencia |

---

## Instalación

```bash
# Clonar
git clone <repo>
cd sns

# Dependencias
pip install numpy scipy

# Ejecutar demo
python system.py

# Ejecutar benchmarks
python system.py --benchmark
```

---

## Quick Start

```python
from sns import StarlinkNodalSystem, AttackType

# Crear sistema
sns = StarlinkNodalSystem("MI-CONSTELACIÓN")

# Inicializar con 264 satélites
sns.initialize({
    'shells': [{
        'shell_id': 1, 
        'planes': 12, 
        'sats_per_plane': 22,
        'altitude': 550, 
        'inclination': 53.0
    }]
})

# Simular operación
for i in range(100):
    metrics = sns.step()
    if i % 20 == 0:
        print(f"Ciclo {i}: Φ={metrics.phi_average:.4f}, E_TTA={metrics.E_TTA:.0f}")

# Simular ataque
sns.inject_attack(AttackType.JAMMING, intensity=0.7)

# Detectar anomalías
alerts = sns.detector.analyze()
for alert in alerts:
    print(f"⚠️ {alert.alert_type.value}: {alert.severity.name}")

# Estado del sistema
status = sns.get_status()
print(f"Operativo: {status['metrics']['is_operational']}")
print(f"Servicios: {status['services']}")
```

---

## Estructura del Proyecto

```
sns/
├── __init__.py      # Package exports
├── core.py          # Estructuras base, constantes D10Z
├── graph.py         # Grafo de constelación, E_TTA, Ley Isis
├── protocol.py      # Protocolo PCIS, ranging, consenso
└── system.py        # Sistema completo integrado
```

---

## Módulos

### 1. Core (`core.py`)

Constantes y estructuras fundamentales:

```python
from sns import C, SatelliteNode, NodalState, CoherenceLevel

# Constantes D10Z
print(C.PHI_THRESHOLD)      # 0.7 - umbral operativo
print(C.GM_10_51)           # 1e-51 - constante de escala

# Crear nodo
node = SatelliteNode(
    id="SAT-001",
    state=NodalState(phi=0.9, energy=0.95)
)
print(f"Nivel: {node.level.value}")  # "optimal"
```

### 2. Graph (`graph.py`)

Grafo de constelación con E_TTA:

```python
from sns import ConstellationGraph, ConstellationBuilder

# Construir constelación
builder = ConstellationBuilder("MI-SNS")
builder.add_shell(shell_id=1, planes=6, sats_per_plane=12, 
                 altitude=550, inclination=53.0)
graph = builder.build()

# Calcular E_TTA
E = graph.compute_E_TTA()

# Propagar coherencia (Ley Isis)
graph.propagate_coherence(dt=1.0, alpha=0.05, beta=0.2)

# Detectar anomalías
alerts = graph.detect_anomalies()
```

### 3. Protocol (`protocol.py`)

Protocolo PCIS para comunicación inter-satélite:

```python
from sns import PCISEngine, HeartbeatMsg, ConsensusEngine

# Motor PCIS
engine = PCISEngine(node)
engine.start()

# Enviar heartbeat
hb = engine.send_heartbeat("SAT-002")

# Ranging para PNT
distance = engine.ranging.get_distance("SAT-002")

# Consenso de E_TTA
consensus = engine.propose_consensus(E_TTA=50000, phi_avg=0.9, n_nodes=72)
```

### 4. System (`system.py`)

Sistema integrado completo:

```python
from sns import StarlinkNodalSystem

sns = StarlinkNodalSystem("SNS")
sns.initialize(config)

# Routing por coherencia
route = sns.find_route("SAT-001", "SAT-099")

# Predicción de degradación
prediction = sns.degradation.predict_degradation(horizon=20)

# Estado completo
status = sns.get_status()
```

---

## Rendimiento

| Nodos | ISLs | Init | E_TTA | Propagación | Routing |
|-------|------|------|-------|-------------|---------|
| 72 | 144 | 25 ms | 0.23 ms | 0.14 ms | 0.001 ms |
| 264 | 528 | 12 ms | 0.86 ms | 0.45 ms | 0.004 ms |
| 792 | 1584 | 35 ms | 2.66 ms | 1.40 ms | 0.002 ms |
| 3888* | ~8000 | ~150 ms | ~12 ms | ~7 ms | ~0.01 ms |

*Estimado para constelación completa tipo Starlink

---

## Comparación: Arquitectura Actual vs SNS D10Z

| Aspecto | Actual | SNS D10Z |
|---------|--------|----------|
| Posicionamiento | GNSS dependiente | PNT nodal (sin GNSS) |
| Detección de ataque | Reactiva (minutos) | Proactiva (segundos) |
| Degradación | Caótica | Predecible f(Φ) |
| Métrica de salud | Cantidad | E_TTA = Σ Zₙ·Φₙ |
| Escalabilidad | Por cantidad | Por coherencia |
| Resiliencia | Redundancia | Coherencia |

---

## Caso de Uso: Detección de Ataque

```python
# Escenario: Jamming en 10% de nodos

# 1. Estado normal
print(f"Φ = {sns.graph.average_phi:.4f}")  # 1.0000

# 2. Ataque
sns.inject_attack(AttackType.JAMMING, intensity=0.8)

# 3. Detección inmediata
alerts = sns.detector.analyze()
# → [HIGH] phi_critical: 26 nodes below threshold
# → [MEDIUM] phi_divergence: 52 pairs divergent

# 4. Sistema identifica amenaza
print(f"Threat level: {sns.detector.get_threat_level()}")  # "HIGH"

# 5. Recuperación automática (Ley Isis)
for _ in range(20):
    sns.step()
print(f"Φ = {sns.graph.average_phi:.4f}")  # 1.0000 (recuperado)
```

---

## API Reference

### StarlinkNodalSystem

| Método | Descripción |
|--------|-------------|
| `initialize(config)` | Inicializa constelación |
| `start(background=True)` | Inicia simulación |
| `stop()` | Detiene simulación |
| `step(dt=1.0)` | Un paso de simulación |
| `inject_attack(type, targets, intensity)` | Simula ataque |
| `find_route(src, dst)` | Routing por Φ |
| `get_status()` | Estado completo |

### ConstellationGraph

| Método | Descripción |
|--------|-------------|
| `add_node(node)` | Agrega satélite |
| `add_edge(from, to, weight)` | Agrega ISL |
| `compute_E_TTA()` | Calcula energía TTA |
| `propagate_coherence(dt, α, β)` | Propaga Φ (Ley Isis) |
| `detect_anomalies()` | Detecta alertas |
| `average_phi` | Φ promedio |
| `is_operational` | ¿Φ ≥ 0.7? |

---

## Autor

**Jamil Al Thani**  
ORCID: 0009-0000-8858-4992  
Email: jamil@d10z.org

## Licencia

CC0 1.0 Universal (Dominio Público)

---

*"La resiliencia es función de la coherencia, no de la cantidad."*

**Framework D10Z-TTA**
