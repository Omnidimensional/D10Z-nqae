#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════════════════
STARLINK NODAL SYSTEM (SNS) - REST API
══════════════════════════════════════════════════════════════════════════════════

API REST para monitoreo y control del sistema SNS.

Endpoints:
    GET  /api/status           - Estado general del sistema
    GET  /api/metrics          - Métricas detalladas
    GET  /api/nodes            - Lista de nodos
    GET  /api/nodes/<id>       - Detalle de un nodo
    GET  /api/alerts           - Alertas activas
    GET  /api/E_TTA/history    - Historial de E_TTA
    POST /api/simulate/attack  - Simular ataque
    POST /api/simulate/step    - Ejecutar un paso

══════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import re

from core import (
    C, NodeState, CoherenceLevel, AlertType, AttackType,
    SatelliteNode, Alert, SystemMetrics, logger
)
from graph import ConstellationGraph, ConstellationBuilder
from system import StarlinkNodalSystem


# ═══════════════════════════════════════════════════════════════════════════════
# API RESPONSE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class APIResponse:
    """Respuesta estándar de la API."""
    success: bool
    data: Any = None
    error: str = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        return json.dumps({
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'timestamp': self.timestamp
        }, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# API HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class SNSAPIHandler(BaseHTTPRequestHandler):
    """Handler HTTP para la API del SNS."""
    
    # Referencia al sistema SNS (se asigna al crear el servidor)
    sns: StarlinkNodalSystem = None
    
    def log_message(self, format, *args):
        """Silenciar logs HTTP estándar."""
        pass
    
    def _send_response(self, response: APIResponse, status: int = 200) -> None:
        """Envía respuesta JSON."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(response.to_json().encode())
    
    def _send_error(self, message: str, status: int = 400) -> None:
        """Envía respuesta de error."""
        response = APIResponse(success=False, error=message)
        self._send_response(response, status)
    
    def _parse_body(self) -> Dict:
        """Parsea el body JSON de la request."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode())
    
    def do_OPTIONS(self):
        """Maneja preflight CORS."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Maneja requests GET."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        routes = {
            '/api/status': self._get_status,
            '/api/metrics': self._get_metrics,
            '/api/nodes': self._get_nodes,
            '/api/alerts': self._get_alerts,
            '/api/E_TTA/history': self._get_E_TTA_history,
            '/api/phi/field': self._get_phi_field,
            '/api/config': self._get_config,
        }
        
        # Rutas con parámetros
        node_match = re.match(r'/api/nodes/(.+)', path)
        if node_match:
            self._get_node(node_match.group(1))
            return
        
        if path in routes:
            routes[path](query)
        else:
            self._send_error(f"Unknown endpoint: {path}", 404)
    
    def do_POST(self):
        """Maneja requests POST."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            body = self._parse_body()
        except json.JSONDecodeError:
            self._send_error("Invalid JSON body")
            return
        
        routes = {
            '/api/simulate/step': self._post_step,
            '/api/simulate/attack': self._post_attack,
            '/api/simulate/recover': self._post_recover,
            '/api/nodes/isolate': self._post_isolate,
            '/api/nodes/reconnect': self._post_reconnect,
        }
        
        if path in routes:
            routes[path](body)
        else:
            self._send_error(f"Unknown endpoint: {path}", 404)
    
    # ─────────────────────────────────────────────────────────────────────────
    # GET Endpoints
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_status(self, query: Dict) -> None:
        """GET /api/status - Estado general."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        status = self.sns.get_status()
        response = APIResponse(success=True, data=status)
        self._send_response(response)
    
    def _get_metrics(self, query: Dict) -> None:
        """GET /api/metrics - Métricas detalladas."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        metrics = self.sns.graph.compute_metrics()
        response = APIResponse(success=True, data=metrics.to_dict())
        self._send_response(response)
    
    def _get_nodes(self, query: Dict) -> None:
        """GET /api/nodes - Lista de nodos."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        # Parámetros de filtro
        level = query.get('level', [None])[0]
        shell = query.get('shell', [None])[0]
        limit = int(query.get('limit', [100])[0])
        offset = int(query.get('offset', [0])[0])
        
        nodes = list(self.sns.graph.nodes.values())
        
        # Filtrar
        if level:
            level_enum = CoherenceLevel[level.upper()]
            nodes = [n for n in nodes if n.level == level_enum]
        
        if shell:
            shell_int = int(shell)
            nodes = [n for n in nodes if n.shell == shell_int]
        
        # Paginar
        total = len(nodes)
        nodes = nodes[offset:offset + limit]
        
        data = {
            'total': total,
            'offset': offset,
            'limit': limit,
            'nodes': [n.to_dict() for n in nodes]
        }
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    def _get_node(self, node_id: str) -> None:
        """GET /api/nodes/<id> - Detalle de un nodo."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        node = self.sns.graph.get_node(node_id)
        if node is None:
            self._send_error(f"Node not found: {node_id}", 404)
            return
        
        data = node.to_dict()
        data['neighbors'] = node.neighbors
        data['phi_history'] = list(node.phi_history)[-20:]
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    def _get_alerts(self, query: Dict) -> None:
        """GET /api/alerts - Alertas activas."""
        if self.sns is None or self.sns.detector is None:
            self._send_error("System not initialized", 503)
            return
        
        active_only = query.get('active', ['true'])[0].lower() == 'true'
        
        alerts = self.sns.detector.alerts
        if active_only:
            alerts = [a for a in alerts if a.is_active]
        
        data = {
            'total': len(alerts),
            'alerts': [a.to_dict() for a in alerts[-50:]]  # Últimas 50
        }
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    def _get_E_TTA_history(self, query: Dict) -> None:
        """GET /api/E_TTA/history - Historial de E_TTA."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        limit = int(query.get('limit', [100])[0])
        
        history = list(self.sns.graph.E_TTA_history)[-limit:]
        
        data = {
            'current': history[-1] if history else 0,
            'history': history,
            'count': len(history)
        }
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    def _get_phi_field(self, query: Dict) -> None:
        """GET /api/phi/field - Campo de coherencia."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        field = self.sns.graph.compute_phi_field()
        
        response = APIResponse(success=True, data=field)
        self._send_response(response)
    
    def _get_config(self, query: Dict) -> None:
        """GET /api/config - Configuración del sistema."""
        data = {
            'constants': {
                'PHI_THRESHOLD': C.PHI_THRESHOLD,
                'PHI_CRITICAL': C.PHI_CRITICAL,
                'PHI_DEGRADED': C.PHI_DEGRADED,
                'HEARTBEAT_INTERVAL': C.HEARTBEAT_INTERVAL,
                'CONSENSUS_INTERVAL': C.CONSENSUS_INTERVAL,
                'ALPHA_DECAY': C.ALPHA_DECAY,
                'BETA_COUPLING': C.BETA_COUPLING
            },
            'system': {
                'name': self.sns.name if self.sns else None,
                'n_nodes': self.sns.graph.n_nodes if self.sns and self.sns.graph else 0,
                'n_edges': self.sns.graph.n_edges if self.sns and self.sns.graph else 0
            }
        }
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    # ─────────────────────────────────────────────────────────────────────────
    # POST Endpoints
    # ─────────────────────────────────────────────────────────────────────────
    
    def _post_step(self, body: Dict) -> None:
        """POST /api/simulate/step - Ejecutar paso de simulación."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        n_steps = body.get('steps', 1)
        dt = body.get('dt', 1.0)
        
        for _ in range(n_steps):
            self.sns.step(dt=dt)
        
        metrics = self.sns.graph.compute_metrics()
        
        data = {
            'steps_executed': n_steps,
            'metrics': metrics.to_dict()
        }
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    def _post_attack(self, body: Dict) -> None:
        """POST /api/simulate/attack - Simular ataque."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        attack_type_str = body.get('type', 'jamming').upper()
        intensity = body.get('intensity', 0.5)
        targets = body.get('targets')
        coverage = body.get('coverage', 0.1)
        
        try:
            attack_type = AttackType[attack_type_str]
        except KeyError:
            self._send_error(f"Unknown attack type: {attack_type_str}")
            return
        
        # Si no hay targets específicos, usar coverage
        if targets is None:
            n_targets = max(1, int(self.sns.graph.n_nodes * coverage))
            import numpy as np
            targets = list(np.random.choice(
                list(self.sns.graph.nodes.keys()), n_targets, replace=False
            ))
        
        result = self.sns.inject_attack(attack_type, targets, intensity)
        
        response = APIResponse(success=True, data=result)
        self._send_response(response)
    
    def _post_recover(self, body: Dict) -> None:
        """POST /api/simulate/recover - Ejecutar ciclos de recuperación."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        cycles = body.get('cycles', 20)
        
        phi_before = self.sns.graph.average_phi
        
        for _ in range(cycles):
            self.sns.step()
        
        phi_after = self.sns.graph.average_phi
        
        data = {
            'cycles_executed': cycles,
            'phi_before': phi_before,
            'phi_after': phi_after,
            'recovered': phi_after > phi_before
        }
        
        response = APIResponse(success=True, data=data)
        self._send_response(response)
    
    def _post_isolate(self, body: Dict) -> None:
        """POST /api/nodes/isolate - Aislar un nodo."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        node_id = body.get('node_id')
        if not node_id:
            self._send_error("node_id required")
            return
        
        success = self.sns.graph.isolate_node(node_id)
        
        response = APIResponse(success=success, 
                              data={'node_id': node_id, 'isolated': success})
        self._send_response(response)
    
    def _post_reconnect(self, body: Dict) -> None:
        """POST /api/nodes/reconnect - Reconectar un nodo."""
        if self.sns is None or self.sns.graph is None:
            self._send_error("System not initialized", 503)
            return
        
        node_id = body.get('node_id')
        neighbors = body.get('neighbors', [])
        initial_phi = body.get('phi', 0.5)
        
        if not node_id:
            self._send_error("node_id required")
            return
        
        success = self.sns.graph.reconnect_node(node_id, neighbors, initial_phi)
        
        response = APIResponse(success=success,
                              data={'node_id': node_id, 'reconnected': success})
        self._send_response(response)


# ═══════════════════════════════════════════════════════════════════════════════
# API SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class SNSAPIServer:
    """
    Servidor API REST para el sistema SNS.
    """
    
    def __init__(self, sns: StarlinkNodalSystem, host: str = '0.0.0.0', port: int = 8080):
        self.sns = sns
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.running = False
    
    def start(self, background: bool = True) -> None:
        """Inicia el servidor."""
        # Asignar sistema al handler
        SNSAPIHandler.sns = self.sns
        
        self.server = HTTPServer((self.host, self.port), SNSAPIHandler)
        self.running = True
        
        logger.info(f"API Server starting on http://{self.host}:{self.port}")
        
        if background:
            self._thread = threading.Thread(target=self._serve, daemon=True)
            self._thread.start()
        else:
            self._serve()
    
    def _serve(self) -> None:
        """Loop de servicio."""
        while self.running:
            self.server.handle_request()
    
    def stop(self) -> None:
        """Detiene el servidor."""
        self.running = False
        if self.server:
            self.server.shutdown()
        logger.info("API Server stopped")
    
    def get_url(self) -> str:
        """Retorna URL base del servidor."""
        return f"http://{self.host}:{self.port}"


# ═══════════════════════════════════════════════════════════════════════════════
# CLI CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class APIClient:
    """Cliente simple para la API."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
    
    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Realiza una request."""
        import urllib.request
        import urllib.error
        
        url = f"{self.base_url}{endpoint}"
        
        if data:
            data = json.dumps(data).encode()
        
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> Dict:
        return self._request('GET', '/api/status')
    
    def get_metrics(self) -> Dict:
        return self._request('GET', '/api/metrics')
    
    def get_nodes(self, limit: int = 10) -> Dict:
        return self._request('GET', f'/api/nodes?limit={limit}')
    
    def get_node(self, node_id: str) -> Dict:
        return self._request('GET', f'/api/nodes/{node_id}')
    
    def get_alerts(self) -> Dict:
        return self._request('GET', '/api/alerts')
    
    def simulate_step(self, steps: int = 1) -> Dict:
        return self._request('POST', '/api/simulate/step', {'steps': steps})
    
    def simulate_attack(self, attack_type: str = 'jamming', 
                       intensity: float = 0.5,
                       coverage: float = 0.1) -> Dict:
        return self._request('POST', '/api/simulate/attack', {
            'type': attack_type,
            'intensity': intensity,
            'coverage': coverage
        })


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """Demo de la API REST."""
    
    print("=" * 70)
    print("SNS REST API DEMO")
    print("=" * 70)
    
    # Crear sistema
    sns = StarlinkNodalSystem("SNS-API-DEMO")
    sns.initialize({
        'shells': [{'shell_id': 1, 'planes': 6, 'sats_per_plane': 12,
                   'altitude': 550, 'inclination': 53.0}]
    })
    
    # Iniciar servidor
    server = SNSAPIServer(sns, port=8080)
    server.start(background=True)
    
    print(f"\nServer running at {server.get_url()}")
    print("\nEndpoints:")
    print("  GET  /api/status")
    print("  GET  /api/metrics")
    print("  GET  /api/nodes")
    print("  GET  /api/nodes/<id>")
    print("  GET  /api/alerts")
    print("  GET  /api/E_TTA/history")
    print("  POST /api/simulate/step")
    print("  POST /api/simulate/attack")
    
    # Dar tiempo a iniciar
    time.sleep(0.5)
    
    # Test con cliente
    print("\n[TESTING API]")
    client = APIClient(server.get_url())
    
    # Status
    print("\n1. GET /api/status")
    status = client.get_status()
    if status.get('success'):
        print(f"   Nodes: {status['data']['metrics']['n_nodes']}")
        print(f"   Φ avg: {status['data']['metrics']['phi']['average']:.4f}")
    
    # Metrics
    print("\n2. GET /api/metrics")
    metrics = client.get_metrics()
    if metrics.get('success'):
        print(f"   E_TTA: {metrics['data']['E_TTA']:.0f}")
        print(f"   Operational: {metrics['data']['is_operational']}")
    
    # Nodes
    print("\n3. GET /api/nodes?limit=3")
    nodes = client.get_nodes(limit=3)
    if nodes.get('success'):
        print(f"   Total: {nodes['data']['total']}")
        for n in nodes['data']['nodes']:
            print(f"   - {n['id']}: Φ={n['phi']:.3f}")
    
    # Step
    print("\n4. POST /api/simulate/step (10 steps)")
    step_result = client.simulate_step(10)
    if step_result.get('success'):
        print(f"   Steps: {step_result['data']['steps_executed']}")
        print(f"   Φ after: {step_result['data']['metrics']['phi']['average']:.4f}")
    
    # Attack
    print("\n5. POST /api/simulate/attack")
    attack_result = client.simulate_attack('jamming', 0.7, 0.1)
    if attack_result.get('success'):
        print(f"   Affected: {len(attack_result['data']['affected'])} nodes")
    
    # Metrics after attack
    print("\n6. GET /api/metrics (after attack)")
    metrics = client.get_metrics()
    if metrics.get('success'):
        print(f"   E_TTA: {metrics['data']['E_TTA']:.0f}")
        print(f"   Φ avg: {metrics['data']['phi_average']:.4f}")
    
    # Alerts
    print("\n7. GET /api/alerts")
    alerts = client.get_alerts()
    if alerts.get('success'):
        print(f"   Alerts: {alerts['data']['total']}")
    
    print("\n" + "=" * 70)
    print(f"API running at {server.get_url()}")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        server.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    demo()
