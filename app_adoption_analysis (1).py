#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════════════════
Pyraclaw-TTA: ADOPCIÓN INMEDIATA VÍA APP
══════════════════════════════════════════════════════════════════════════════════

Premisa:
    - NO se requiere cambiar hardware
    - Los dispositivos actuales YA tienen las frecuencias necesarias
    - Solo se necesita una APP que implemente el protocolo nodal Pyraclaw
    - La industria puede optimizar hardware DESPUÉS

Fases:
    1. App → Adopción masiva inmediata
    2. Firmware updates → Optimización
    3. Hardware nativo → Eficiencia máxima

══════════════════════════════════════════════════════════════════════════════════
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import math

# ═══════════════════════════════════════════════════════════════════════════════
# CAPACIDADES EXISTENTES EN DISPOSITIVOS ACTUALES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExistingDeviceCapabilities:
    """Lo que YA tienen los dispositivos actuales."""
    
    # WiFi
    wifi_24ghz: bool = True       # Todos los smartphones desde 2010
    wifi_5ghz: bool = True        # Todos desde 2015
    wifi_6ghz: bool = True        # Desde 2020 (WiFi 6E)
    wifi_direct: bool = True      # P2P sin router
    wifi_aware: bool = True       # Neighbor Awareness Networking
    
    # Bluetooth
    bluetooth_classic: bool = True
    bluetooth_le: bool = True     # Low Energy - ideal para mesh
    bluetooth_mesh: bool = True   # Desde BT 5.0
    
    # Otros
    nfc: bool = True              # Near Field Communication
    uwb: bool = True              # Ultra-Wideband (iPhones, Samsung flagship)
    lte_direct: bool = False      # Limitado pero existe
    
    # Capacidades de red
    hotspot: bool = True          # Crear AP
    mesh_capable: bool = True     # Via WiFi Direct + BT
    
    def list_available(self) -> List[str]:
        """Lista tecnologías disponibles."""
        available = []
        if self.wifi_direct: available.append("WiFi Direct (P2P)")
        if self.wifi_aware: available.append("WiFi Aware (NAN)")
        if self.bluetooth_mesh: available.append("Bluetooth Mesh")
        if self.uwb: available.append("Ultra-Wideband")
        if self.hotspot: available.append("Hotspot/Tethering")
        return available


# ═══════════════════════════════════════════════════════════════════════════════
# ESPECIFICACIÓN DE LA APP Pyraclaw
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PyraclawAppSpec:
    """Especificación de la app de conexión nodal."""
    
    name: str = "Pyraclaw Node"
    version: str = "1.0.0"
    
    # Plataformas
    platforms: List[str] = field(default_factory=lambda: [
        "Android 8+",      # 95% de Android activos
        "iOS 14+",         # 90% de iPhones activos
        "Windows 10+",     # Via WiFi Direct
        "macOS 11+",       # Via WiFi Direct
        "Linux",           # NetworkManager
        "Embedded/IoT"     # SDK ligero
    ])
    
    # Protocolos que usa
    protocols: List[str] = field(default_factory=lambda: [
        "WiFi Direct",
        "WiFi Aware (NAN)",
        "Bluetooth LE Mesh",
        "mDNS/DNS-SD",     # Descubrimiento
        "QUIC/UDP"         # Transporte
    ])
    
    # Tamaño estimado
    app_size_mb: float = 15.0
    sdk_size_mb: float = 2.0  # Para IoT
    
    # Recursos
    battery_impact_percent: float = 3.0  # Adicional
    ram_usage_mb: float = 50.0
    background_data_mb_day: float = 10.0
    
    # Funcionalidades core
    features: List[str] = field(default_factory=lambda: [
        "Descubrimiento automático de nodos vecinos",
        "Cálculo de Φ (coherencia) local",
        "Propagación de coherencia (Ley Isis)",
        "Enrutamiento por coherencia",
        "Consenso distribuido ligero",
        "Fallback a internet tradicional",
        "Dashboard de estado nodal",
        "Modo ahorro de batería"
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# MODELO DE ADOPCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AdoptionModel:
    """Modelo de adopción de la app."""
    
    # Dispositivos globales
    smartphones_global: int = 7_000_000_000
    tablets_global: int = 1_000_000_000
    laptops_global: int = 1_500_000_000
    iot_compatible: int = 5_000_000_000  # Con WiFi/BT
    vehicles_connected: int = 500_000_000
    routers_upgradeable: int = 800_000_000
    
    @property
    def total_addressable(self) -> int:
        return (self.smartphones_global + self.tablets_global + 
                self.laptops_global + self.iot_compatible +
                self.vehicles_connected + self.routers_upgradeable)
    
    def project_adoption(self, months: int, 
                        initial_users: int = 100_000,
                        viral_coefficient: float = 1.3,
                        retention_rate: float = 0.85) -> List[Dict]:
        """
        Proyecta adopción mes a mes.
        
        Modelo: Crecimiento viral con saturación
        N(t+1) = N(t) × viral_coefficient × (1 - N(t)/TAM) × retention
        """
        history = []
        users = initial_users
        tam = self.total_addressable
        
        for month in range(months):
            # Crecimiento viral con saturación
            growth_factor = viral_coefficient * (1 - users / tam)
            new_users = users * (growth_factor - 1) * retention_rate
            users = min(tam, users + max(0, new_users))
            
            # Nodos activos (70% de usuarios tienen app activa)
            active_nodes = int(users * 0.70)
            
            # Cobertura
            coverage = self._calculate_coverage(active_nodes)
            
            history.append({
                'month': month + 1,
                'users': int(users),
                'active_nodes': active_nodes,
                'coverage_percent': coverage * 100,
                'phi_potential': min(1.0, 0.5 + 0.5 * (users / tam))
            })
        
        return history
    
    def _calculate_coverage(self, active_nodes: int) -> float:
        """Calcula cobertura basada en nodos activos."""
        # Densidad mínima para operación: 10 nodos/km²
        # Área poblada: 50M km²
        populated_area = 50_000_000
        density = active_nodes / populated_area
        
        if density >= 100:
            return 0.99
        elif density >= 10:
            return 0.95
        elif density >= 1:
            return 0.70 + 0.25 * (density / 10)
        else:
            return 0.70 * density
        

# ═══════════════════════════════════════════════════════════════════════════════
# FASES DE IMPLEMENTACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def implementation_phases():
    """Define las fases de implementación."""
    
    phases = {
        'Fase 1 - App Pura': {
            'duración': '0-6 meses',
            'requisito_usuario': 'Descargar app',
            'cambio_hardware': 'NINGUNO',
            'tecnología': [
                'WiFi Direct entre smartphones',
                'Bluetooth LE Mesh',
                'WiFi Aware (NAN) para descubrimiento',
                'Internet como fallback'
            ],
            'limitaciones': [
                'Alcance ~100m (WiFi Direct)',
                'Latencia ~10-50ms entre nodos',
                'Consumo batería +3-5%',
                'Requiere app en foreground (Android) o background (iOS limitado)'
            ],
            'capacidades': [
                'Red mesh local (edificio, evento, barrio)',
                'Compartir conexión internet entre vecinos',
                'Comunicación P2P sin internet',
                'Backup para caídas de red'
            ],
            'phi_alcanzable': 0.7
        },
        
        'Fase 2 - Firmware Updates': {
            'duración': '6-18 meses',
            'requisito_usuario': 'Actualizar SO',
            'cambio_hardware': 'NINGUNO',
            'tecnología': [
                'Optimizaciones de kernel para mesh',
                'APIs nativas de coherencia',
                'Menor consumo batería',
                'Background operation mejorado'
            ],
            'limitaciones': [
                'Depende de fabricantes',
                'Fragmentación Android',
                'Aprobación Apple'
            ],
            'capacidades': [
                'Operación 24/7 en background',
                'Consumo batería <1%',
                'Alcance mejorado ~200m',
                'Integración con OS'
            ],
            'phi_alcanzable': 0.85
        },
        
        'Fase 3 - Hardware Nativo': {
            'duración': '18-36 meses',
            'requisito_usuario': 'Comprar nuevo dispositivo (ciclo natural)',
            'cambio_hardware': 'Nuevo chip Pyraclaw',
            'tecnología': [
                'Radio dedicada para mesh',
                'Coprocesador de coherencia',
                'Antena optimizada',
                'UWB de largo alcance'
            ],
            'limitaciones': [
                'Requiere ciclo de reemplazo natural',
                'Adopción gradual'
            ],
            'capacidades': [
                'Alcance 1-5 km',
                'Latencia <1ms',
                'Consumo negligible',
                'Φ = 1.0 alcanzable'
            ],
            'phi_alcanzable': 1.0
        }
    }
    
    return phases


# ═══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_app_adoption():
    """Análisis completo de adopción vía app."""
    
    print("=" * 80)
    print("Pyraclaw-TTA: ADOPCIÓN INMEDIATA VÍA APP")
    print("=" * 80)
    
    # ─────────────────────────────────────────────────────────────────────────
    # LO QUE YA EXISTE
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("1. CAPACIDADES EXISTENTES EN DISPOSITIVOS ACTUALES")
    print("─" * 40)
    
    caps = ExistingDeviceCapabilities()
    
    print(f"""
    Los smartphones, tablets y laptops ACTUALES ya tienen:
    
    ✓ WiFi Direct         → Conexión P2P sin router, hasta 200m
    ✓ WiFi Aware (NAN)    → Descubrimiento de vecinos sin conexión
    ✓ Bluetooth LE Mesh   → Red mesh de bajo consumo
    ✓ Hotspot/Tethering   → Crear punto de acceso
    ✓ UWB (flagships)     → Posicionamiento preciso
    
    CONCLUSIÓN: El hardware EXISTE. Solo falta el SOFTWARE.
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ESPECIFICACIÓN DE LA APP
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("2. ESPECIFICACIÓN DE LA APP")
    print("─" * 40)
    
    app = PyraclawAppSpec()
    
    print(f"""
    App: {app.name} v{app.version}
    
    Plataformas:
    {chr(10).join(f'    • {p}' for p in app.platforms)}
    
    Tamaño: ~{app.app_size_mb} MB (app) / ~{app.sdk_size_mb} MB (SDK IoT)
    
    Impacto:
    • Batería: +{app.battery_impact_percent}%
    • RAM: {app.ram_usage_mb} MB
    • Datos: {app.background_data_mb_day} MB/día
    
    Funcionalidades:
    {chr(10).join(f'    • {f}' for f in app.features)}
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # FASES DE IMPLEMENTACIÓN
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("3. FASES DE IMPLEMENTACIÓN")
    print("─" * 40)
    
    phases = implementation_phases()
    
    for name, phase in phases.items():
        print(f"""
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ {name:<71} │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ Duración: {phase['duración']:<61} │
    │ Requisito usuario: {phase['requisito_usuario']:<52} │
    │ Cambio hardware: {phase['cambio_hardware']:<54} │
    │ Φ alcanzable: {phase['phi_alcanzable']:<58} │
    └─────────────────────────────────────────────────────────────────────────┘
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PROYECCIÓN DE ADOPCIÓN
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("4. PROYECCIÓN DE ADOPCIÓN")
    print("─" * 40)
    
    model = AdoptionModel()
    projection = model.project_adoption(
        months=36,
        initial_users=100_000,
        viral_coefficient=1.4,
        retention_rate=0.90
    )
    
    print(f"\n    Dispositivos compatibles: {model.total_addressable:,}")
    print(f"\n    {'Mes':<6} {'Usuarios':<18} {'Nodos Activos':<18} {'Cobertura':<12} {'Φ Potencial':<10}")
    print(f"    {'-'*6} {'-'*18} {'-'*18} {'-'*12} {'-'*10}")
    
    milestones = [1, 3, 6, 12, 18, 24, 36]
    for p in projection:
        if p['month'] in milestones:
            print(f"    {p['month']:<6} {p['users']:>15,}   {p['active_nodes']:>15,}   {p['coverage_percent']:>9.1f}%   {p['phi_potential']:>8.2f}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # ESCENARIOS DE USO INMEDIATO (DÍA 1)
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("5. ESCENARIOS DE USO INMEDIATO (DÍA 1)")
    print("─" * 40)
    
    print("""
    Sin esperar adopción masiva, la app es útil INMEDIATAMENTE:
    
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ ESCENARIO                    │ USUARIOS MÍNIMOS │ BENEFICIO            │
    ├──────────────────────────────┼──────────────────┼──────────────────────┤
    │ Familia en casa              │ 3-5              │ Mesh local sin ISP   │
    │ Oficina                      │ 10-50            │ Red resiliente       │
    │ Evento/Concierto             │ 100-1000         │ Comunicación P2P     │
    │ Edificio residencial         │ 50-200           │ Internet compartido  │
    │ Campus universitario         │ 1000-10000       │ Red independiente    │
    │ Barrio                       │ 500-2000         │ Cobertura local      │
    │ Ciudad (distrito)            │ 10000+           │ Red alternativa      │
    │ Emergencia/Desastre          │ Cualquier #      │ Comunicación vital   │
    └─────────────────────────────────────────────────────────────────────────┘
    
    CLAVE: No necesita "masa crítica global" para ser útil.
           Funciona en CLUSTERS LOCALES desde el día 1.
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # COMPARACIÓN CON ALTERNATIVAS
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("6. COMPARACIÓN CON ALTERNATIVAS")
    print("─" * 40)
    
    print("""
    ┌────────────────────────────────────────────────────────────────────────────┐
    │                        │ Pyraclaw App    │ Hardware    │ Satélites  │ 5G/ISP  │
    ├────────────────────────┼─────────────┼─────────────┼────────────┼─────────┤
    │ Tiempo despliegue      │ Inmediato   │ 2-5 años    │ 5-10 años  │ Existe  │
    │ Costo usuario          │ $0          │ $200-500    │ $50-100/m  │ $30-80/m│
    │ Costo infraestructura  │ $0          │ Alto        │ $20B+      │ $100B+  │
    │ Dependencia externa    │ Ninguna     │ Fabricantes │ Operadores │ ISPs    │
    │ Resiliencia            │ Alta        │ Alta        │ Media      │ Baja    │
    │ Funciona sin internet  │ Sí          │ Sí          │ No*        │ No      │
    │ Cobertura rural        │ Por densidad│ Por densidad│ Global     │ Limitada│
    │ Privacidad             │ Alta        │ Alta        │ Media      │ Baja    │
    └────────────────────────────────────────────────────────────────────────────┘
    
    * Satélites requieren gateway terrestre para comunicación entre usuarios
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ARQUITECTURA TÉCNICA DE LA APP
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("7. ARQUITECTURA TÉCNICA DE LA APP")
    print("─" * 40)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         Pyraclaw NODE APP                                   │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                         │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
    │  │   UI/UX     │  │  Dashboard  │  │  Settings   │  │   Alerts    │   │
    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
    │         └─────────────────┴─────────────────┴─────────────────┘         │
    │                                   │                                     │
    │  ┌────────────────────────────────┴────────────────────────────────┐   │
    │  │                      Pyraclaw CORE ENGINE                            │   │
    │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
    │  │  │ Estado Zₙ│ │Coherencia│ │ Ley Isis │ │ Consenso │            │   │
    │  │  │          │ │    Φₙ    │ │∂Φ/∂t=... │ │ E_TTA    │            │   │
    │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │   │
    │  └────────────────────────────────┬────────────────────────────────┘   │
    │                                   │                                     │
    │  ┌────────────────────────────────┴────────────────────────────────┐   │
    │  │                      NETWORK LAYER                               │   │
    │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
    │  │  │  WiFi    │ │Bluetooth │ │ Routing  │ │ Fallback │            │   │
    │  │  │  Direct  │ │ LE Mesh  │ │   P2P    │ │ Internet │            │   │
    │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │   │
    │  └─────────────────────────────────────────────────────────────────┘   │
    │                                                                         │
    │  ┌─────────────────────────────────────────────────────────────────┐   │
    │  │                      OS ABSTRACTION                              │   │
    │  │  Android WifiP2pManager │ iOS MultipeerConnectivity │ etc.      │   │
    │  └─────────────────────────────────────────────────────────────────┘   │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # TIMELINE REALISTA
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "─" * 40)
    print("8. TIMELINE REALISTA")
    print("─" * 40)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────┐
    │ SEMANA    │ ACCIÓN                                                     │
    ├───────────┼─────────────────────────────────────────────────────────────┤
    │ 1-4       │ MVP Android (WiFi Direct + BT)                             │
    │ 5-8       │ MVP iOS (Multipeer Connectivity)                           │
    │ 9-12      │ Alpha testing (100 usuarios)                               │
    │ 13-16     │ Beta pública (1,000 usuarios)                              │
    │ 17-20     │ Release v1.0 en stores                                     │
    │ 21-24     │ SDK para IoT/routers                                       │
    └─────────────────────────────────────────────────────────────────────────┘
    
    Tiempo a v1.0: ~5 meses
    Tiempo a masa crítica local (10K users): ~8-12 meses
    Tiempo a adopción significativa (1M users): ~18-24 meses
    """)
    
    # ─────────────────────────────────────────────────────────────────────────
    # CONCLUSIÓN
    # ─────────────────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 80)
    print("CONCLUSIÓN")
    print("=" * 80)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                                                             │
    │  LA ADOPCIÓN DE Pyraclaw-TTA NO REQUIERE:                                      │
    │                                                                             │
    │  ✗ Cambiar teléfonos                                                       │
    │  ✗ Comprar hardware nuevo                                                  │
    │  ✗ Esperar a la industria                                                  │
    │  ✗ Infraestructura centralizada                                            │
    │  ✗ Permisos de operadores                                                  │
    │                                                                             │
    │  SOLO REQUIERE:                                                            │
    │                                                                             │
    │  ✓ Descargar una app (~15 MB)                                              │
    │  ✓ Activar WiFi + Bluetooth                                                │
    │  ✓ Tener vecinos con la app                                                │
    │                                                                             │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │                                                                             │
    │  FASES:                                                                     │
    │                                                                             │
    │  AHORA  → App descargable (hardware existente)                             │
    │  6 meses → Firmware optimizado (updates de SO)                             │
    │  2 años → Hardware nativo (ciclo natural de reemplazo)                     │
    │                                                                             │
    │  La red se construye MIENTRAS la industria se adapta, no DESPUÉS.          │
    │                                                                             │
    └─────────────────────────────────────────────────────────────────────────────┘
    """)
    
    return {
        'time_to_mvp_months': 5,
        'adoption_1M_users_months': 18,
        'hardware_required': False,
        'app_size_mb': 15,
        'battery_impact_percent': 3.0
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CÓDIGO DE EJEMPLO DE LA APP
# ═══════════════════════════════════════════════════════════════════════════════

def show_app_pseudocode():
    """Muestra pseudocódigo del core de la app."""
    
    print("\n" + "=" * 80)
    print("PSEUDOCÓDIGO DEL CORE (Pyraclaw Node Engine)")
    print("=" * 80)
    
    code = '''
    // ═══════════════════════════════════════════════════════════════════════
    // Pyraclaw NODE ENGINE - Core Loop
    // ═══════════════════════════════════════════════════════════════════════
    
    class PyraclawNode {
        state: NodalState       // Zₙ = [position, velocity, energy, phi, ...]
        neighbors: Map<NodeID, NeighborInfo>
        phi: float = 0.5        // Coherencia inicial
        
        // Constantes Pyraclaw
        ALPHA_DECAY = 0.05
        BETA_COUPLING = 0.2
        PHI_THRESHOLD = 0.7
        
        // ─────────────────────────────────────────────────────────────────
        // LOOP PRINCIPAL (cada 100ms)
        // ─────────────────────────────────────────────────────────────────
        
        func mainLoop() {
            while (running) {
                // 1. Descubrir vecinos
                discoverNeighbors()
                
                // 2. Intercambiar estado (heartbeat)
                broadcastState()
                receiveStates()
                
                // 3. Propagar coherencia (Ley Isis)
                updateCoherence()
                
                // 4. Enrutar por coherencia
                routePackets()
                
                // 5. Reportar métricas
                updateUI()
                
                sleep(100ms)
            }
        }
        
        // ─────────────────────────────────────────────────────────────────
        // DESCUBRIMIENTO DE VECINOS
        // ─────────────────────────────────────────────────────────────────
        
        func discoverNeighbors() {
            // WiFi Aware (NAN)
            wifiAware.startSubscribe("pyraclaw-node")
            
            // Bluetooth LE Scan
            bleScanner.startScan(filter: "Pyraclaw")
            
            // mDNS
            mdns.browse("_pyraclaw._udp.local")
        }
        
        // ─────────────────────────────────────────────────────────────────
        // LEY ISIS: PROPAGACIÓN DE COHERENCIA
        // ─────────────────────────────────────────────────────────────────
        
        func updateCoherence() {
            // ∂Φ/∂t = -αΦ + β × Σ(w_ij × Φ_j) / |N|
            
            decay = ALPHA_DECAY * phi
            
            coupling = 0
            for (neighbor in neighbors) {
                weight = 1.0 / neighbor.distance  // Peso por distancia
                coupling += weight * neighbor.phi
            }
            coupling = BETA_COUPLING * coupling / neighbors.size
            
            // Actualizar Φ
            delta_phi = -decay + coupling
            phi = clamp(phi + delta_phi * dt, 0, 1)
        }
        
        // ─────────────────────────────────────────────────────────────────
        // ENRUTAMIENTO POR COHERENCIA
        // ─────────────────────────────────────────────────────────────────
        
        func routePacket(packet: Packet) -> NodeID {
            if (packet.destination == self.id) {
                return self.id  // Llegó
            }
            
            // Seleccionar mejor vecino por coherencia
            bestNeighbor = null
            bestScore = 0
            
            for (neighbor in neighbors) {
                if (neighbor.phi < PHI_THRESHOLD) continue  // Skip degradados
                
                score = neighbor.phi * (1 / distanceTo(packet.destination))
                if (score > bestScore) {
                    bestScore = score
                    bestNeighbor = neighbor
                }
            }
            
            if (bestNeighbor == null) {
                // Fallback a internet tradicional
                return INTERNET_GATEWAY
            }
            
            return bestNeighbor.id
        }
        
        // ─────────────────────────────────────────────────────────────────
        // CÁLCULO DE E_TTA LOCAL
        // ─────────────────────────────────────────────────────────────────
        
        func computeLocalE_TTA() -> float {
            // E_TTA = Σ |Zₙ| × Φₙ
            e_tta = magnitude(state) * phi
            
            for (neighbor in neighbors) {
                e_tta += magnitude(neighbor.state) * neighbor.phi
            }
            
            return e_tta
        }
    }
    '''
    
    print(code)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    results = analyze_app_adoption()
    show_app_pseudocode()
    
    print("\n" + "=" * 80)
    print("RESUMEN EJECUTIVO")
    print("=" * 80)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                                                             │
    │  Pyraclaw-TTA: ADOPCIÓN INMEDIATA VÍA APP                                      │
    │                                                                             │
    │  • Tiempo a MVP: 5 meses                                                   │
    │  • Costo usuario: $0 (solo descargar app)                                  │
    │  • Hardware requerido: NINGUNO (usa WiFi Direct + Bluetooth existentes)    │
    │  • Tamaño app: 15 MB                                                       │
    │  • Impacto batería: +3%                                                    │
    │                                                                             │
    │  FUNCIONA DESDE EL DÍA 1:                                                  │
    │  - Familia/oficina: 5-50 dispositivos → mesh local                         │
    │  - Evento: 100-1000 dispositivos → comunicación P2P                        │
    │  - Barrio: 1000+ dispositivos → red alternativa                            │
    │                                                                             │
    │  LA INDUSTRIA SE ADAPTA DESPUÉS, NO ANTES.                                 │
    │                                                                             │
    └─────────────────────────────────────────────────────────────────────────────┘
    """)
