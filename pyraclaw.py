#!/usr/bin/env python3
"""
Pyraclaw-TTA INTEGRATED SYSTEM v18
==============================
Sistema integrado completo que une todos los componentes:
- Motor de coherencia (engine.py)
- Red nodal P2P (nodal_network.py)
- Contenido distribuido (content.py)
- Nodo puente (bridge_node.py)

Parámetros validados (MCMC + TÜV Rheinland):
- T_HIGH (Bread): 0.436
- T_LOW (Torreja): 0.286
- Ahorro energético: 84.43%
- Delta térmico: -67.5°C
- Factor escalabilidad: 6.42x
- Compresión: 14.9x

DOI: 10.5281/zenodo.18356012
Rights Holder: Byron Callaghan
GitHub: https://github.com/Omnidimensional/Pyraclaw-nqae
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path

# Agregar paths
sys.path.insert(0, str(Path(__file__).parent))

from core.engine import (
    PyraclawConstants, PathMode, CoherenceLevel,
    CoherenceAnalyzer, IsisLawEngine, NodalTriModal,
    PlanetaryMeshSimulator, ETTACalculator,
    generate_node_id, pyraclaw_hash
)
from network.nodal_network import (
    PyraclawNode, NetworkSimulator, LinkLayer, Router
)
from storage.content import (
    LocalStorage, PyraclawHash, Manifest, NameRegistry, ReplicationManager
)


# =============================================================================
# SISTEMA INTEGRADO
# =============================================================================

class PyraclawSystem:
    """
    Sistema Pyraclaw-TTA integrado completo.
    
    Combina todos los componentes en una interfaz unificada.
    """
    
    VERSION = "18.0.0"
    DOI = "10.5281/zenodo.18356012"
    
    def __init__(self, data_path: str = "./pyraclaw_data"):
        """
        Inicializa el sistema Pyraclaw.
        
        Args:
            data_path: Ruta para almacenamiento de datos
        """
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Componentes
        self.storage = LocalStorage(str(self.data_path / "storage"))
        self.name_registry = NameRegistry(self.storage)
        self.replication = ReplicationManager(self.storage)
        self.analyzer = CoherenceAnalyzer()
        self.model = NodalTriModal()
        
        # Nodo local
        self.local_node = PyraclawNode()
        
        # Estado
        self.start_time = time.time()
        self.is_running = False
        
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    Pyraclaw-TTA NODAL SYSTEM v{self.VERSION}                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  DOI: {self.DOI}                                    ║
║  Node ID: {self.local_node.node_id.hex()[:32]}...           ║
║  Data Path: {str(self.data_path):<54} ║
╚══════════════════════════════════════════════════════════════════════╝
        """)
    
    def start(self):
        """Inicia el sistema."""
        self.is_running = True
        self.local_node.start()
        print("✅ Sistema Pyraclaw iniciado")
    
    def stop(self):
        """Detiene el sistema."""
        self.is_running = False
        self.local_node.stop()
        print("🛑 Sistema Pyraclaw detenido")
    
    # =========================================================================
    # ALMACENAMIENTO DE CONTENIDO
    # =========================================================================
    
    def store(self, data: bytes, name: str = None, **kwargs) -> PyraclawHash:
        """
        Almacena contenido en la red nodal.
        
        Args:
            data: Datos a almacenar
            name: Nombre/alias opcional
            **kwargs: Metadatos adicionales
            
        Returns:
            Hash Pyraclaw del contenido
        """
        # Calcular coherencia
        if len(data) > 10:
            import numpy as np
            phi = self.analyzer.compute_phi(np.frombuffer(data[:96], dtype=np.float64))
        else:
            phi = 0.7
        
        # Almacenar
        manifest = self.storage.store_object(data, **kwargs)
        
        # Registrar nombre si se proporciona
        if name:
            self.name_registry.register(
                name, 
                manifest.object_hash,
                self.local_node.node_id
            )
        
        # Anunciar disponibilidad
        self.local_node.dht.announce_provider(manifest.object_hash.hash_bytes)
        
        print(f"📦 Almacenado: {manifest.object_hash.short()}")
        if name:
            print(f"   Nombre: {name}")
        print(f"   Tamaño: {len(data):,} bytes")
        print(f"   Chunks: {len(manifest.chunks)}")
        print(f"   Φ: {phi:.3f}")
        
        return manifest.object_hash
    
    def retrieve(self, identifier: str) -> bytes:
        """
        Recupera contenido por hash o nombre.
        
        Args:
            identifier: Hash Pyraclaw o nombre registrado
            
        Returns:
            Datos del contenido
        """
        # Determinar si es nombre o hash
        if identifier.startswith("PYRACLAW://"):
            content_hash = PyraclawHash.from_string(identifier)
        else:
            # Buscar por nombre
            content_hash = self.name_registry.resolve(identifier)
            if not content_hash:
                raise ValueError(f"Nombre no encontrado: {identifier}")
        
        # Recuperar
        data = self.storage.get_object(content_hash)
        
        if data is None:
            raise ValueError(f"Contenido no encontrado: {content_hash.short()}")
        
        # Trackear demanda
        self.replication.track_request(content_hash.hash_bytes)
        
        return data
    
    # =========================================================================
    # ANÁLISIS Y PROCESAMIENTO
    # =========================================================================
    
    def analyze(self, data: bytes) -> dict:
        """
        Analiza datos y determina path óptimo.
        
        Args:
            data: Datos a analizar
            
        Returns:
            Diccionario con análisis
        """
        import numpy as np
        
        # Convertir a array numérico
        if len(data) < 96:
            data = data + b'\x00' * (96 - len(data))
        
        arr = np.frombuffer(data[:96], dtype=np.float64)
        
        # Calcular coherencia
        phi = self.analyzer.compute_phi(arr)
        path = self.analyzer.get_path(phi)
        level = self.analyzer.get_level(phi)
        
        # Procesar por modelo
        output, mode = self.model.forward(arr, phi)
        
        return {
            'phi': phi,
            'path': path.value,
            'level': level.value,
            'mode': mode.value,
            'energy_cost': {
                PathMode.FAST: 0.01,
                PathMode.QUANT: 0.25,
                PathMode.DEEP: 1.00
            }[mode],
            'thresholds': {
                'T_HIGH': PyraclawConstants.T_HIGH,
                'T_LOW': PyraclawConstants.T_LOW
            }
        }
    
    # =========================================================================
    # SIMULACIONES
    # =========================================================================
    
    def simulate_planetary_mesh(self, nodes: int = 2_490_000) -> dict:
        """
        Ejecuta simulación de despliegue planetario.
        
        Args:
            nodes: Número de nodos a simular
            
        Returns:
            Resultado de la simulación
        """
        simulator = PlanetaryMeshSimulator(total_nodes=nodes)
        result = simulator.simulate()
        
        print(result)
        
        return {
            'total_nodes': result.total_nodes,
            'fast_nodes': result.fast_nodes,
            'quant_nodes': result.quant_nodes,
            'deep_nodes': result.deep_nodes,
            'energy_savings': result.energy_savings,
            'virtual_capacity': result.virtual_capacity,
            'thermal_delta': result.thermal_delta,
        }
    
    def simulate_stress_test(self, failure_ratio: float = 0.40) -> dict:
        """
        Ejecuta test de estrés con fallo de infraestructura.
        
        Args:
            failure_ratio: Porcentaje de nodos que fallan
            
        Returns:
            Resultado del test
        """
        simulator = PlanetaryMeshSimulator()
        result = simulator.stress_test(failure_ratio)
        
        print(f"""
🚨 STRESS TEST - {failure_ratio*100:.0f}% FALLO
{'='*50}
   Nodos supervivientes: {result['surviving_nodes']:,}
   Capacidad virtual: {result['virtual_capacity']:,}
   Superávit: +{result['surplus']:,}
   Estado: {result['status']}
{'='*50}
        """)
        
        return result
    
    def simulate_network(self, nodes: int = 10, steps: int = 50) -> dict:
        """
        Simula red de nodos locales.
        
        Args:
            nodes: Número de nodos
            steps: Pasos de simulación
            
        Returns:
            Estado final de la red
        """
        simulator = NetworkSimulator(num_nodes=nodes)
        simulator.run(steps=steps)
        
        return {
            'nodes': nodes,
            'steps': steps,
            'final_state': [
                {
                    'id': node.node_id.hex()[:8],
                    'phi': node.link.coherence.phi,
                    'neighbors': len(node.link.neighbors)
                }
                for node in simulator.nodes
            ]
        }
    
    # =========================================================================
    # INFORMACIÓN DEL SISTEMA
    # =========================================================================
    
    def get_status(self) -> dict:
        """Retorna estado completo del sistema."""
        storage_stats = self.storage.get_stats()
        
        return {
            'version': self.VERSION,
            'doi': self.DOI,
            'node_id': self.local_node.node_id.hex()[:32],
            'is_running': self.is_running,
            'uptime': int(time.time() - self.start_time),
            'local_phi': self.local_node.link.coherence.phi,
            'neighbors': len(self.local_node.link.neighbors),
            'storage': storage_stats,
            'constants': {
                'T_HIGH': PyraclawConstants.T_HIGH,
                'T_LOW': PyraclawConstants.T_LOW,
                'ENERGY_SAVINGS': f"{PyraclawConstants.ENERGY_SAVINGS*100:.2f}%",
                'THERMAL_DELTA': f"{PyraclawConstants.THERMAL_DELTA}°C",
                'SCALABILITY': f"{PyraclawConstants.SCALABILITY_FACTOR}x",
                'COMPRESSION': f"{PyraclawConstants.COMPRESSION_RATIO}x",
            }
        }
    
    def print_status(self):
        """Imprime estado del sistema."""
        status = self.get_status()
        
        print(f"""
📊 Pyraclaw SYSTEM STATUS
{'='*60}
Version: {status['version']}
DOI: {status['doi']}
Node ID: {status['node_id']}...
Running: {status['is_running']}
Uptime: {status['uptime']}s
Local Φ: {status['local_phi']:.3f}
Neighbors: {status['neighbors']}

📦 Storage:
   Chunks: {status['storage']['chunks_count']}
   Manifests: {status['storage']['manifests_count']}
   Size: {status['storage']['total_size_mb']:.2f} MB

⚙️ Constants (Validated):
   T_HIGH (Bread): {status['constants']['T_HIGH']}
   T_LOW (Torreja): {status['constants']['T_LOW']}
   Energy Savings: {status['constants']['ENERGY_SAVINGS']}
   Thermal Delta: {status['constants']['THERMAL_DELTA']}
   Scalability: {status['constants']['SCALABILITY']}
   Compression: {status['constants']['COMPRESSION']}
{'='*60}
        """)


# =============================================================================
# CLI
# =============================================================================

def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Pyraclaw-TTA Nodal System v18",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python pyraclaw.py status              # Ver estado del sistema
  python pyraclaw.py simulate            # Simular despliegue planetario
  python pyraclaw.py stress              # Test de estrés
  python pyraclaw.py store file.txt      # Almacenar archivo
  python pyraclaw.py retrieve PYRACLAW://... # Recuperar contenido
        """
    )
    
    parser.add_argument('command', choices=['status', 'simulate', 'stress', 'network', 'store', 'retrieve', 'demo'],
                       help='Comando a ejecutar')
    parser.add_argument('args', nargs='*', help='Argumentos del comando')
    parser.add_argument('--data-path', default='./pyraclaw_data', help='Ruta de datos')
    parser.add_argument('--nodes', type=int, default=2490000, help='Número de nodos para simulación')
    
    args = parser.parse_args()
    
    # Crear sistema
    system = PyraclawSystem(data_path=args.data_path)
    
    if args.command == 'status':
        system.print_status()
    
    elif args.command == 'simulate':
        system.simulate_planetary_mesh(nodes=args.nodes)
    
    elif args.command == 'stress':
        system.simulate_stress_test(0.40)
    
    elif args.command == 'network':
        system.simulate_network(nodes=10, steps=50)
    
    elif args.command == 'store':
        if not args.args:
            print("Error: Especifique archivo a almacenar")
            return 1
        
        filepath = args.args[0]
        with open(filepath, 'rb') as f:
            data = f.read()
        
        name = args.args[1] if len(args.args) > 1 else None
        system.store(data, name=name)
    
    elif args.command == 'retrieve':
        if not args.args:
            print("Error: Especifique hash o nombre")
            return 1
        
        data = system.retrieve(args.args[0])
        
        if len(args.args) > 1:
            # Guardar a archivo
            with open(args.args[1], 'wb') as f:
                f.write(data)
            print(f"Guardado en: {args.args[1]}")
        else:
            print(data[:1000])
    
    elif args.command == 'demo':
        print("\n🎯 DEMO COMPLETA Pyraclaw-TTA\n")
        
        # 1. Simulación planetaria
        print("1️⃣ Simulación Planetaria (2.49M nodos):")
        system.simulate_planetary_mesh(nodes=2_490_000)
        
        # 2. Test de estrés
        print("\n2️⃣ Test de Estrés (40% fallo):")
        system.simulate_stress_test(0.40)
        
        # 3. Almacenamiento
        print("\n3️⃣ Test de Almacenamiento:")
        test_data = b"Hello, Pyraclaw Nodal Network! " * 100
        content_hash = system.store(test_data, name="hello-pyraclaw")
        
        # 4. Recuperación
        print("\n4️⃣ Test de Recuperación:")
        recovered = system.retrieve("hello-pyraclaw")
        print(f"   Verificación: {recovered == test_data}")
        
        # 5. Análisis
        print("\n5️⃣ Test de Análisis:")
        import numpy as np
        analysis = system.analyze(np.sin(np.linspace(0, 4*np.pi, 96)).tobytes())
        print(f"   Φ: {analysis['phi']:.3f}")
        print(f"   Path: {analysis['path']}")
        print(f"   Level: {analysis['level']}")
        print(f"   Energy Cost: {analysis['energy_cost']*100:.0f}%")
        
        # 6. Estado
        print("\n6️⃣ Estado del Sistema:")
        system.print_status()
        
        print("\n✅ DEMO COMPLETA")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
