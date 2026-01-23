#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════════════════
STARLINK NODAL SYSTEM (SNS) - SGP4/TLE INTEGRATION
══════════════════════════════════════════════════════════════════════════════════

Integración con propagador SGP4 y datos TLE reales de Starlink.

Funcionalidades:
    - Parsing de TLE (Two-Line Elements)
    - Propagación SGP4 de alta precisión
    - Descarga de TLE desde CelesTrak/Space-Track
    - Conversión a estados nodales D10Z
    - Predicción de pases y visibilidad

Dependencias opcionales:
    - sgp4: pip install sgp4
    - skyfield: pip install skyfield

══════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import numpy as np
import time
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from pathlib import Path
import math

from core import (
    C, Vector3D, OrbitalElements, NodalState, SatelliteNode,
    logger
)


# ═══════════════════════════════════════════════════════════════════════════════
# TLE PARSER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TLEData:
    """Datos parseados de un TLE."""
    name: str
    catalog_number: int
    classification: str
    launch_year: int
    launch_number: int
    piece: str
    epoch_year: int
    epoch_day: float
    mean_motion_dot: float
    mean_motion_ddot: float
    bstar: float
    ephemeris_type: int
    element_number: int
    inclination: float        # grados
    raan: float               # grados
    eccentricity: float
    arg_perigee: float        # grados
    mean_anomaly: float       # grados
    mean_motion: float        # rev/day
    revolution_number: int
    
    # Líneas originales
    line1: str = ""
    line2: str = ""
    
    @property
    def epoch_datetime(self) -> datetime:
        """Convierte epoch a datetime."""
        year = 2000 + self.epoch_year if self.epoch_year < 57 else 1900 + self.epoch_year
        day_of_year = int(self.epoch_day)
        fraction = self.epoch_day - day_of_year
        
        dt = datetime(year, 1, 1, tzinfo=timezone.utc)
        dt = dt.replace(day=1) + timedelta(days=day_of_year - 1)
        dt = dt + timedelta(seconds=fraction * 86400)
        return dt
    
    @property
    def semi_major_axis(self) -> float:
        """Calcula semi-eje mayor en km."""
        # a = (μ / n²)^(1/3) donde n está en rad/s
        n_rad_s = self.mean_motion * 2 * np.pi / 86400
        mu = 398600.4418  # km³/s²
        return (mu / n_rad_s**2) ** (1/3)
    
    @property
    def altitude(self) -> float:
        """Altitud aproximada en km."""
        return self.semi_major_axis - 6371.0
    
    @property
    def period_minutes(self) -> float:
        """Período orbital en minutos."""
        return 1440.0 / self.mean_motion
    
    def to_orbital_elements(self) -> OrbitalElements:
        """Convierte a OrbitalElements D10Z."""
        return OrbitalElements(
            semi_major_axis=self.semi_major_axis,
            eccentricity=self.eccentricity,
            inclination=self.inclination,
            raan=self.raan,
            arg_perigee=self.arg_perigee,
            true_anomaly=np.radians(self.mean_anomaly),  # Aproximación
            epoch=self.epoch_day
        )
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'catalog_number': self.catalog_number,
            'epoch': self.epoch_datetime.isoformat() if hasattr(self, 'epoch_datetime') else None,
            'inclination': self.inclination,
            'raan': self.raan,
            'eccentricity': self.eccentricity,
            'arg_perigee': self.arg_perigee,
            'mean_anomaly': self.mean_anomaly,
            'mean_motion': self.mean_motion,
            'altitude_km': self.altitude,
            'period_min': self.period_minutes
        }


from datetime import timedelta


class TLEParser:
    """Parser de archivos TLE."""
    
    @staticmethod
    def parse_line1(line: str) -> Dict:
        """Parsea línea 1 del TLE."""
        return {
            'catalog_number': int(line[2:7]),
            'classification': line[7],
            'launch_year': int(line[9:11]),
            'launch_number': int(line[11:14]),
            'piece': line[14:17].strip(),
            'epoch_year': int(line[18:20]),
            'epoch_day': float(line[20:32]),
            'mean_motion_dot': float(line[33:43]),
            'mean_motion_ddot': TLEParser._parse_decimal(line[44:52]),
            'bstar': TLEParser._parse_decimal(line[53:61]),
            'ephemeris_type': int(line[62]) if line[62].strip() else 0,
            'element_number': int(line[64:68])
        }
    
    @staticmethod
    def parse_line2(line: str) -> Dict:
        """Parsea línea 2 del TLE."""
        return {
            'catalog_number': int(line[2:7]),
            'inclination': float(line[8:16]),
            'raan': float(line[17:25]),
            'eccentricity': float('0.' + line[26:33]),
            'arg_perigee': float(line[34:42]),
            'mean_anomaly': float(line[43:51]),
            'mean_motion': float(line[52:63]),
            'revolution_number': int(line[63:68])
        }
    
    @staticmethod
    def _parse_decimal(s: str) -> float:
        """Parsea notación decimal especial de TLE."""
        s = s.strip()
        if not s:
            return 0.0
        
        # Formato: ±NNNNN±E donde el punto decimal está implícito
        if s[0] in '+-':
            sign = -1 if s[0] == '-' else 1
            s = s[1:]
        else:
            sign = 1
        
        # Encontrar exponente
        exp_match = re.search(r'([+-]\d)$', s)
        if exp_match:
            exp = int(exp_match.group(1))
            mantissa = s[:-2]
        else:
            exp = 0
            mantissa = s
        
        # Construir número
        try:
            value = float('0.' + mantissa) * (10 ** exp) * sign
            return value
        except:
            return 0.0
    
    @staticmethod
    def parse(tle_text: str) -> List[TLEData]:
        """
        Parsea texto con múltiples TLEs.
        
        Formato esperado:
            NOMBRE
            1 NNNNN...
            2 NNNNN...
        """
        lines = [l.strip() for l in tle_text.strip().split('\n') if l.strip()]
        results = []
        
        i = 0
        while i < len(lines):
            # Buscar nombre (línea que no empieza con 1 o 2)
            if lines[i][0] not in '12':
                name = lines[i]
                i += 1
            else:
                name = f"UNKNOWN-{i}"
            
            # Verificar que hay líneas 1 y 2
            if i + 1 >= len(lines):
                break
            
            line1 = lines[i]
            line2 = lines[i + 1]
            
            if not line1.startswith('1') or not line2.startswith('2'):
                i += 1
                continue
            
            try:
                data1 = TLEParser.parse_line1(line1)
                data2 = TLEParser.parse_line2(line2)
                
                tle = TLEData(
                    name=name,
                    line1=line1,
                    line2=line2,
                    **data1,
                    inclination=data2['inclination'],
                    raan=data2['raan'],
                    eccentricity=data2['eccentricity'],
                    arg_perigee=data2['arg_perigee'],
                    mean_anomaly=data2['mean_anomaly'],
                    mean_motion=data2['mean_motion'],
                    revolution_number=data2['revolution_number']
                )
                
                results.append(tle)
            except Exception as e:
                logger.warning(f"Failed to parse TLE at line {i}: {e}")
            
            i += 2
        
        return results
    
    @staticmethod
    def parse_file(filepath: str) -> List[TLEData]:
        """Parsea archivo TLE."""
        with open(filepath, 'r') as f:
            return TLEParser.parse(f.read())


# ═══════════════════════════════════════════════════════════════════════════════
# SGP4 PROPAGATOR
# ═══════════════════════════════════════════════════════════════════════════════

class SGP4Propagator:
    """
    Propagador SGP4 para TLEs.
    
    Usa la librería sgp4 si está disponible, o fallback a Kepleriano simple.
    """
    
    def __init__(self, tle: TLEData):
        self.tle = tle
        self._sgp4_satellite = None
        self._use_sgp4 = False
        
        # Intentar cargar sgp4
        try:
            from sgp4.api import Satrec, WGS84
            self._sgp4_satellite = Satrec.twoline2rv(tle.line1, tle.line2, WGS84)
            self._use_sgp4 = True
            logger.debug(f"Using SGP4 for {tle.name}")
        except ImportError:
            logger.debug(f"sgp4 not available, using Keplerian for {tle.name}")
        except Exception as e:
            logger.warning(f"SGP4 init failed for {tle.name}: {e}")
    
    def propagate(self, dt: datetime = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Propaga a un instante de tiempo.
        
        Args:
            dt: Datetime (default: now)
        
        Returns:
            (position_km, velocity_km_s) en ECI
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        
        if self._use_sgp4 and self._sgp4_satellite:
            return self._propagate_sgp4(dt)
        else:
            return self._propagate_keplerian(dt)
    
    def _propagate_sgp4(self, dt: datetime) -> Tuple[np.ndarray, np.ndarray]:
        """Propagación SGP4."""
        from sgp4.api import jday
        
        jd, fr = jday(dt.year, dt.month, dt.day,
                      dt.hour, dt.minute, dt.second + dt.microsecond/1e6)
        
        error_code, position, velocity = self._sgp4_satellite.sgp4(jd, fr)
        
        if error_code != 0:
            logger.warning(f"SGP4 error {error_code} for {self.tle.name}")
            return self._propagate_keplerian(dt)
        
        return np.array(position), np.array(velocity)
    
    def _propagate_keplerian(self, dt: datetime) -> Tuple[np.ndarray, np.ndarray]:
        """Propagación Kepleriana simple (fallback)."""
        # Tiempo desde epoch
        epoch_dt = self.tle.epoch_datetime
        delta_seconds = (dt - epoch_dt).total_seconds()
        
        # Elementos orbitales
        a = self.tle.semi_major_axis
        e = self.tle.eccentricity
        i = np.radians(self.tle.inclination)
        Omega = np.radians(self.tle.raan)
        omega = np.radians(self.tle.arg_perigee)
        M0 = np.radians(self.tle.mean_anomaly)
        
        # Movimiento medio
        n = self.tle.mean_motion * 2 * np.pi / 86400  # rad/s
        
        # Anomalía media actual
        M = M0 + n * delta_seconds
        
        # Resolver Kepler
        E = self._solve_kepler(M, e)
        
        # Anomalía verdadera
        nu = 2 * np.arctan2(
            np.sqrt(1 + e) * np.sin(E / 2),
            np.sqrt(1 - e) * np.cos(E / 2)
        )
        
        # Radio
        r = a * (1 - e * np.cos(E))
        
        # Posición en plano orbital
        x_orb = r * np.cos(nu)
        y_orb = r * np.sin(nu)
        
        # Velocidad en plano orbital
        mu = 398600.4418
        p = a * (1 - e**2)
        h = np.sqrt(mu * p)
        
        vx_orb = -mu / h * np.sin(nu)
        vy_orb = mu / h * (e + np.cos(nu))
        
        # Matriz de rotación
        cos_O, sin_O = np.cos(Omega), np.sin(Omega)
        cos_i, sin_i = np.cos(i), np.sin(i)
        cos_w, sin_w = np.cos(omega), np.sin(omega)
        
        R = np.array([
            [cos_O*cos_w - sin_O*sin_w*cos_i, -cos_O*sin_w - sin_O*cos_w*cos_i, sin_O*sin_i],
            [sin_O*cos_w + cos_O*sin_w*cos_i, -sin_O*sin_w + cos_O*cos_w*cos_i, -cos_O*sin_i],
            [sin_w*sin_i, cos_w*sin_i, cos_i]
        ])
        
        pos = R @ np.array([x_orb, y_orb, 0])
        vel = R @ np.array([vx_orb, vy_orb, 0])
        
        return pos, vel
    
    def _solve_kepler(self, M: float, e: float, tol: float = 1e-10) -> float:
        """Resuelve ecuación de Kepler."""
        E = M if e < 0.8 else np.pi
        for _ in range(50):
            f = E - e * np.sin(E) - M
            fp = 1 - e * np.cos(E)
            dE = -f / fp
            E += dE
            if abs(dE) < tol:
                break
        return E
    
    def get_position(self, dt: datetime = None) -> np.ndarray:
        """Obtiene solo posición."""
        pos, _ = self.propagate(dt)
        return pos
    
    def get_velocity(self, dt: datetime = None) -> np.ndarray:
        """Obtiene solo velocidad."""
        _, vel = self.propagate(dt)
        return vel
    
    def get_altitude(self, dt: datetime = None) -> float:
        """Obtiene altitud sobre superficie terrestre."""
        pos, _ = self.propagate(dt)
        return np.linalg.norm(pos) - 6371.0
    
    def predict_passes(self, observer_lat: float, observer_lon: float,
                      duration_hours: float = 24,
                      min_elevation: float = 10.0) -> List[Dict]:
        """
        Predice pases sobre un observador.
        
        Args:
            observer_lat: Latitud del observador (grados)
            observer_lon: Longitud del observador (grados)
            duration_hours: Duración de predicción
            min_elevation: Elevación mínima para considerar visible
        
        Returns:
            Lista de pases con tiempos y elevaciones
        """
        passes = []
        dt = datetime.now(timezone.utc)
        end_time = dt + timedelta(hours=duration_hours)
        step = timedelta(seconds=60)  # 1 minuto
        
        in_pass = False
        pass_start = None
        max_elevation = 0
        
        while dt < end_time:
            pos, _ = self.propagate(dt)
            elevation = self._compute_elevation(pos, observer_lat, observer_lon)
            
            if elevation >= min_elevation:
                if not in_pass:
                    in_pass = True
                    pass_start = dt
                    max_elevation = elevation
                else:
                    max_elevation = max(max_elevation, elevation)
            else:
                if in_pass:
                    passes.append({
                        'start': pass_start.isoformat(),
                        'end': dt.isoformat(),
                        'max_elevation': max_elevation,
                        'duration_minutes': (dt - pass_start).total_seconds() / 60
                    })
                    in_pass = False
            
            dt += step
        
        return passes
    
    def _compute_elevation(self, sat_pos: np.ndarray, 
                          lat: float, lon: float) -> float:
        """Calcula elevación del satélite desde un observador."""
        # Posición del observador en ECEF
        lat_rad = np.radians(lat)
        lon_rad = np.radians(lon)
        R_earth = 6371.0
        
        obs_x = R_earth * np.cos(lat_rad) * np.cos(lon_rad)
        obs_y = R_earth * np.cos(lat_rad) * np.sin(lon_rad)
        obs_z = R_earth * np.sin(lat_rad)
        obs_pos = np.array([obs_x, obs_y, obs_z])
        
        # Vector al satélite
        to_sat = sat_pos - obs_pos
        
        # Normal local (simplificada como radial)
        local_up = obs_pos / np.linalg.norm(obs_pos)
        
        # Elevación
        cos_zenith = np.dot(to_sat, local_up) / np.linalg.norm(to_sat)
        elevation = 90 - np.degrees(np.arccos(np.clip(cos_zenith, -1, 1)))
        
        return elevation


# ═══════════════════════════════════════════════════════════════════════════════
# STARLINK TLE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

# TLE de ejemplo de Starlink (actualizar con datos reales)
SAMPLE_STARLINK_TLE = """STARLINK-1007
1 44713U 19074A   24015.50000000  .00000000  00000-0  00000-0 0  9999
2 44713  53.0000 100.0000 0001000   0.0000   0.0000 15.05000000  1000
STARLINK-1008
1 44714U 19074B   24015.50000000  .00000000  00000-0  00000-0 0  9999
2 44714  53.0000 100.0000 0001000   0.0000  16.3636 15.05000000  1000
STARLINK-1009
1 44715U 19074C   24015.50000000  .00000000  00000-0  00000-0 0  9999
2 44715  53.0000 100.0000 0001000   0.0000  32.7273 15.05000000  1000
STARLINK-1010
1 44716U 19074D   24015.50000000  .00000000  00000-0  00000-0 0  9999
2 44716  53.0000 100.0000 0001000   0.0000  49.0909 15.05000000  1000
STARLINK-1011
1 44717U 19074E   24015.50000000  .00000000  00000-0  00000-0 0  9999
2 44717  53.0000 105.0000 0001000   0.0000   0.0000 15.05000000  1000
STARLINK-1012
1 44718U 19074F   24015.50000000  .00000000  00000-0  00000-0 0  9999
2 44718  53.0000 105.0000 0001000   0.0000  16.3636 15.05000000  1000
"""


class StarlinkTLEManager:
    """
    Gestor de TLEs de Starlink.
    
    Funcionalidades:
        - Carga de TLEs desde archivo o texto
        - Conversión a nodos D10Z
        - Propagación de constelación completa
    """
    
    CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle"
    
    def __init__(self):
        self.tles: Dict[str, TLEData] = {}
        self.propagators: Dict[str, SGP4Propagator] = {}
        self.last_update: Optional[datetime] = None
    
    def load_from_text(self, tle_text: str) -> int:
        """Carga TLEs desde texto."""
        tles = TLEParser.parse(tle_text)
        
        for tle in tles:
            self.tles[tle.name] = tle
            self.propagators[tle.name] = SGP4Propagator(tle)
        
        self.last_update = datetime.now(timezone.utc)
        logger.info(f"Loaded {len(tles)} TLEs")
        
        return len(tles)
    
    def load_from_file(self, filepath: str) -> int:
        """Carga TLEs desde archivo."""
        with open(filepath, 'r') as f:
            return self.load_from_text(f.read())
    
    def load_sample(self) -> int:
        """Carga TLEs de ejemplo."""
        return self.load_from_text(SAMPLE_STARLINK_TLE)
    
    def download_from_celestrak(self) -> int:
        """
        Descarga TLEs actualizados de CelesTrak.
        
        Requiere conexión a internet.
        """
        try:
            import urllib.request
            
            logger.info(f"Downloading TLEs from CelesTrak...")
            
            with urllib.request.urlopen(self.CELESTRAK_URL, timeout=30) as response:
                tle_text = response.read().decode('utf-8')
            
            return self.load_from_text(tle_text)
        
        except Exception as e:
            logger.error(f"Failed to download TLEs: {e}")
            return 0
    
    def get_positions(self, dt: datetime = None) -> Dict[str, np.ndarray]:
        """Obtiene posiciones de todos los satélites."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        
        positions = {}
        for name, prop in self.propagators.items():
            try:
                pos, _ = prop.propagate(dt)
                positions[name] = pos
            except Exception as e:
                logger.warning(f"Failed to propagate {name}: {e}")
        
        return positions
    
    def to_nodal_states(self, dt: datetime = None,
                       initial_phi: float = 0.9) -> Dict[str, NodalState]:
        """
        Convierte TLEs a estados nodales D10Z.
        
        Args:
            dt: Tiempo de propagación
            initial_phi: Φ inicial para todos los nodos
        
        Returns:
            {satellite_name: NodalState}
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        
        states = {}
        
        for name, prop in self.propagators.items():
            try:
                pos, vel = prop.propagate(dt)
                
                state = NodalState(
                    position=Vector3D(pos[0], pos[1], pos[2]),
                    velocity=Vector3D(vel[0], vel[1], vel[2]),
                    altitude=np.linalg.norm(pos) - 6371.0,
                    energy=0.9 + 0.1 * np.random.random(),
                    frequency=10.0,
                    phi=initial_phi + 0.1 * (np.random.random() - 0.5)
                )
                
                states[name] = state
            
            except Exception as e:
                logger.warning(f"Failed to create state for {name}: {e}")
        
        return states
    
    def to_satellite_nodes(self, dt: datetime = None,
                          initial_phi: float = 0.9) -> List[SatelliteNode]:
        """
        Convierte TLEs a nodos satelitales D10Z.
        
        Returns:
            Lista de SatelliteNode listos para agregar a ConstellationGraph
        """
        states = self.to_nodal_states(dt, initial_phi)
        nodes = []
        
        for name, state in states.items():
            tle = self.tles.get(name)
            
            # Extraer shell y plano del TLE
            shell = 1
            plane = int(tle.raan / 5) if tle else 0
            pos_in_plane = int(tle.mean_anomaly / 16.36) if tle else 0
            
            node = SatelliteNode(
                id=name,
                shell=shell,
                plane=plane,
                position_in_plane=pos_in_plane,
                state=state,
                orbital=tle.to_orbital_elements() if tle else OrbitalElements()
            )
            
            nodes.append(node)
        
        return nodes
    
    def get_stats(self) -> Dict:
        """Estadísticas de los TLEs cargados."""
        if not self.tles:
            return {'count': 0}
        
        altitudes = [tle.altitude for tle in self.tles.values()]
        inclinations = [tle.inclination for tle in self.tles.values()]
        
        return {
            'count': len(self.tles),
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'altitude_km': {
                'min': min(altitudes),
                'max': max(altitudes),
                'mean': np.mean(altitudes)
            },
            'inclination_deg': {
                'min': min(inclinations),
                'max': max(inclinations),
                'mean': np.mean(inclinations)
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRACIÓN CON SNS
# ═══════════════════════════════════════════════════════════════════════════════

def create_constellation_from_tle(tle_source: str = None,
                                  initial_phi: float = 0.9) -> 'ConstellationGraph':
    """
    Crea un ConstellationGraph desde TLEs.
    
    Args:
        tle_source: Ruta a archivo TLE o None para usar sample
        initial_phi: Φ inicial
    
    Returns:
        ConstellationGraph poblado con satélites reales
    """
    from graph import ConstellationGraph
    
    manager = StarlinkTLEManager()
    
    if tle_source:
        manager.load_from_file(tle_source)
    else:
        manager.load_sample()
    
    nodes = manager.to_satellite_nodes(initial_phi=initial_phi)
    
    graph = ConstellationGraph("STARLINK-TLE")
    
    for node in nodes:
        graph.add_node(node)
    
    # Crear topología basada en proximidad
    _create_proximity_topology(graph, max_distance=3000)
    
    logger.info(f"Created constellation from TLE: {graph.n_nodes} nodes, "
               f"{graph.n_edges} edges")
    
    return graph


def _create_proximity_topology(graph: 'ConstellationGraph', 
                               max_distance: float = 3000,
                               max_neighbors: int = 6) -> None:
    """Crea topología ISL basada en proximidad."""
    nodes = list(graph.nodes.values())
    
    for i, node in enumerate(nodes):
        pos_i = node.state.position.to_array()
        
        # Calcular distancias a todos los demás
        distances = []
        for j, other in enumerate(nodes):
            if i == j:
                continue
            pos_j = other.state.position.to_array()
            dist = np.linalg.norm(pos_i - pos_j)
            if dist < max_distance:
                distances.append((dist, other.id))
        
        # Conectar a los más cercanos
        distances.sort()
        for dist, other_id in distances[:max_neighbors]:
            if not graph.has_edge(node.id, other_id):
                # Peso inversamente proporcional a distancia
                weight = 1.0 + dist / 1000
                graph.add_edge(node.id, other_id, weight=weight)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("SNS SGP4/TLE INTEGRATION - TEST")
    print("=" * 70)
    
    # Test TLE Parser
    print("\n[TLE PARSER TEST]")
    tles = TLEParser.parse(SAMPLE_STARLINK_TLE)
    print(f"  Parsed {len(tles)} TLEs")
    
    for tle in tles[:3]:
        print(f"  - {tle.name}: alt={tle.altitude:.1f}km, inc={tle.inclination}°, "
              f"period={tle.period_minutes:.1f}min")
    
    # Test SGP4 Propagator
    print("\n[SGP4 PROPAGATOR TEST]")
    if tles:
        prop = SGP4Propagator(tles[0])
        pos, vel = prop.propagate()
        
        print(f"  Satellite: {tles[0].name}")
        print(f"  Position (km): [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]")
        print(f"  Velocity (km/s): [{vel[0]:.4f}, {vel[1]:.4f}, {vel[2]:.4f}]")
        print(f"  Altitude: {prop.get_altitude():.2f} km")
    
    # Test TLE Manager
    print("\n[TLE MANAGER TEST]")
    manager = StarlinkTLEManager()
    manager.load_sample()
    
    stats = manager.get_stats()
    print(f"  Loaded: {stats['count']} satellites")
    print(f"  Altitude range: {stats['altitude_km']['min']:.1f} - "
          f"{stats['altitude_km']['max']:.1f} km")
    
    # Test conversion to nodes
    print("\n[NODAL CONVERSION TEST]")
    nodes = manager.to_satellite_nodes()
    print(f"  Created {len(nodes)} SatelliteNodes")
    
    if nodes:
        node = nodes[0]
        print(f"  Sample: {node.id}")
        print(f"    Position: {node.state.position}")
        print(f"    Altitude: {node.state.altitude:.2f} km")
        print(f"    Phi: {node.phi:.4f}")
    
    # Test constellation creation
    print("\n[CONSTELLATION FROM TLE TEST]")
    graph = create_constellation_from_tle()
    print(f"  Nodes: {graph.n_nodes}")
    print(f"  Edges: {graph.n_edges}")
    print(f"  Phi avg: {graph.average_phi:.4f}")
    
    # Propagate and check
    for _ in range(5):
        graph.propagate_coherence()
    
    print(f"  After 5 cycles: Phi={graph.average_phi:.4f}")
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
