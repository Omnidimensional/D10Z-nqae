# TERRA MESH: Modelo de Acceso a Internet

## La Pregunta Clave

**¿Cómo accede un nodo Pyraclaw a internet si solo tiene conexiones P2P con vecinos?**

---

## Respuesta Corta

```
TU TELÉFONO → vecinos Pyraclaw → ... → NODO GATEWAY → INTERNET
     ↓
  (mesh P2P)                        (tiene conexión real)
```

**El internet NO desaparece. Se COMPARTE a través de la red nodal.**

---

## Modelo de Funcionamiento

### 1. Tipos de Nodos en TERRA MESH

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  NODO PURO (Leaf)           NODO GATEWAY              NODO HÍBRIDO         │
│  ─────────────────          ───────────               ────────────         │
│                                                                             │
│  📱 Solo mesh               📱🌐 Mesh + Internet      📱📶 Mesh + Móvil    │
│  Sin conexión propia        Router/Fibra/5G          4G/5G como backup     │
│                             Comparte a la red                               │
│                                                                             │
│  Usa internet de            ES el punto de           Puede ser gateway     │
│  vecinos gateway            salida a internet        cuando tiene datos    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Flujo de Datos

```
ESCENARIO: Quieres abrir google.com

TU TELÉFONO (sin internet propio)
     │
     │ WiFi Direct / BLE
     ▼
VECINO-A (Φ=0.85, sin internet)
     │
     │ WiFi Direct
     ▼
VECINO-B (Φ=0.92, sin internet)
     │
     │ WiFi Direct
     ▼
GATEWAY-1 (Φ=0.95, CON FIBRA 🌐)
     │
     │ Internet real
     ▼
═══════════════════════════════
        INTERNET
═══════════════════════════════
     │
     ▼
  google.com → respuesta → misma ruta inversa → TU TELÉFONO
```

### 3. ¿Quién es Gateway?

**Cualquier nodo que tenga conexión a internet puede ser gateway:**

| Dispositivo | Conexión | Puede ser Gateway |
|-------------|----------|-------------------|
| Router WiFi casa | Fibra/ADSL | ✅ SÍ (principal) |
| Teléfono con datos | 4G/5G | ✅ SÍ (móvil) |
| Laptop en café | WiFi público | ✅ SÍ (temporal) |
| Smart TV | Ethernet | ✅ SÍ |
| IoT con SIM | LTE-M | ✅ SÍ |
| Teléfono sin datos | Ninguna | ❌ Solo relay |

### 4. Selección Inteligente de Gateway

```python
def seleccionar_gateway(vecinos):
    """
    Selecciona el mejor gateway por coherencia y calidad.
    """
    gateways = [v for v in vecinos if v.tiene_internet]
    
    if not gateways:
        # Buscar en vecinos de vecinos (2 saltos)
        gateways = buscar_gateways_profundidad(vecinos, profundidad=3)
    
    if not gateways:
        return None  # Realmente aislado
    
    # Ordenar por: Φ × ancho_banda × (1/latencia)
    mejor = max(gateways, key=lambda g: 
        g.phi * g.bandwidth_mbps * (1 / g.latency_ms)
    )
    
    return mejor
```

### 5. Ejemplo Real: Edificio de Apartamentos

```
                    INTERNET (Fibra del edificio)
                           │
                    ┌──────┴──────┐
                    │   ROUTER    │  ← Gateway principal
                    │   Φ=0.98    │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │  APT 1  │      │  APT 2  │      │  APT 3  │
    │ Φ=0.92  │──────│ Φ=0.88  │──────│ Φ=0.91  │
    └────┬────┘      └────┬────┘      └────┬────┘
         │                │                │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │  APT 4  │      │  APT 5  │      │  APT 6  │
    │ Φ=0.85  │──────│ Φ=0.87  │──────│ Φ=0.84  │
    │ (TÚ)    │      │         │      │ 4G 📶   │ ← Gateway secundario
    └─────────┘      └─────────┘      └─────────┘

TÚ (APT 4) accedes a internet via:
- Ruta 1: APT 4 → APT 1 → ROUTER → Internet (3 saltos, fibra)
- Ruta 2: APT 4 → APT 5 → APT 6 → 4G (3 saltos, móvil, backup)
```

---

## Casos de Uso

### Caso 1: Casa Normal
```
Tu teléfono ←→ Tu router (gateway) ←→ Internet
              WiFi Direct         Fibra

Beneficio: Si el WiFi falla, usas mesh de vecinos
```

### Caso 2: Sin Internet Propio
```
Tu teléfono ←→ Vecino 1 ←→ Vecino 2 ←→ Router vecino ←→ Internet
                mesh          mesh       (él comparte)

Beneficio: Internet gratis via comunidad
```

### Caso 3: Evento/Concierto
```
Miles de teléfonos ←→ mesh ←→ ... ←→ Pocos gateways 4G

Beneficio: No saturar las antenas, compartir conexión
```

### Caso 4: Zona Rural
```
Pueblo sin cobertura ←→ mesh largo ←→ Casa con antena satelital

Beneficio: Internet llega donde no hay infraestructura
```

### Caso 5: Emergencia/Desastre
```
Zona afectada ←→ mesh de supervivientes ←→ Vehículo de emergencia con Starlink

Beneficio: Comunicación cuando todo falla
```

---

## Configuración en la App

```
┌─────────────────────────────────────────────┐
│ TERRA MESH - Configuración de Red           │
├─────────────────────────────────────────────┤
│                                             │
│ Rol del nodo:                               │
│ ┌─────────────────────────────────────────┐ │
│ │ ○ Solo relay (no compartir mi internet) │ │
│ │ ● Gateway (compartir mi conexión)       │ │
│ │ ○ Automático (según disponibilidad)     │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ Si soy Gateway:                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Ancho de banda a compartir: [50%    ▼]  │ │
│ │ Límite de nodos: [10 ▼]                 │ │
│ │ Solo vecinos de confianza: [ ]          │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ Prioridad de conexión:                      │
│ 1. WiFi propio (si disponible)              │
│ 2. Gateway mesh con mejor Φ                 │
│ 3. Datos móviles propios (si habilitado)    │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Ecuaciones de Enrutamiento a Gateway

### Métrica de Selección de Gateway

```
Score(gateway) = Φ_gateway × BW × (1/RTT) × Hops^(-0.5)

Donde:
- Φ_gateway = Coherencia del gateway (0-1)
- BW = Ancho de banda disponible (Mbps)
- RTT = Latencia round-trip (ms)
- Hops = Número de saltos hasta el gateway
```

### Costo de Ruta

```
Costo(ruta) = Σᵢ (1/Φᵢ) × distanciaᵢ

Se elige la ruta con MENOR costo.
```

---

## Resumen Visual

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                           ☁️ INTERNET ☁️                                    │
│                                │                                            │
│                    ════════════╪════════════                                │
│                    ║  GATEWAYS (con conexión real)                         │
│                    ║     🏠 Router    📱 4G/5G    📡 Satélite              │
│                    ════════════╪════════════                                │
│                                │                                            │
│         ┌──────────────────────┼──────────────────────┐                    │
│         │                      │                      │                    │
│      ┌──┴──┐                ┌──┴──┐                ┌──┴──┐                 │
│      │NODE │────────────────│NODE │────────────────│NODE │                 │
│      └──┬──┘                └──┬──┘                └──┬──┘                 │
│         │                      │                      │                    │
│      ┌──┴──┐                ┌──┴──┐                ┌──┴──┐                 │
│      │NODE │────────────────│ TÚ  │────────────────│NODE │                 │
│      └─────┘                └─────┘                └─────┘                 │
│                                                                             │
│      CAPA MESH: Todos conectados P2P, comparten rutas a gateways           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Conclusión

**TERRA MESH no elimina internet. Lo DEMOCRATIZA.**

| Antes | Con TERRA MESH |
|-------|----------------|
| Cada uno paga su conexión | Comunidad comparte conexiones |
| Sin cobertura = sin internet | Mesh extiende la cobertura |
| Falla tu router = sin internet | Usas gateway de vecinos |
| Zonas rurales abandonadas | Mesh llega donde no hay infra |

**El internet fluye por la red nodal como agua por tuberías. Los gateways son los pozos.**
