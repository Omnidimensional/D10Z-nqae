#!/usr/bin/env python3
"""
Pyraclaw-TTA DISTRIBUTED CONTENT SYSTEM
====================================
Sistema de contenido distribuido con:
- Content-Addressable Storage (CAS)
- Fragmentación en chunks
- Replicación adaptativa por Φ de demanda
- Sistema de nombres/alias

Reemplaza el modelo cliente-servidor por
almacenamiento nodal distribuido.
"""

import numpy as np
import hashlib
import struct
import time
import json
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set
from enum import Enum
from pathlib import Path

import sys
sys.path.insert(0, '..')
from core.engine import PyraclawConstants, compute_hash, hash_to_base58


# =============================================================================
# CONSTANTES
# =============================================================================

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB
MAX_OBJECT_SIZE = 10 * 1024 ** 3  # 10 GB
HASH_PREFIX_CONTENT = b'Qm'
HASH_PREFIX_MANIFEST = b'Mn'
HASH_PREFIX_CHUNK = b'Ch'


class ContentType(Enum):
    """Tipos de contenido."""
    FILE = 0x01
    DIRECTORY = 0x02
    STREAM = 0x03
    DATABASE = 0x04


class ReplicationType(Enum):
    """Estrategias de replicación."""
    AUTOMATIC = 0x01    # Según demanda
    ON_DEMAND = 0x02    # Solo cuando se solicita
    PINNED = 0x03       # Siempre mantener


class EncryptionType(Enum):
    """Tipos de cifrado."""
    NONE = 0x00
    PERSONAL = 0x01     # Solo el dueño
    GROUP = 0x02        # Grupo de usuarios


# =============================================================================
# HASH Pyraclaw
# =============================================================================

@dataclass
class PyraclawHash:
    """
    Hash Pyraclaw con tipo y codificación Base58.
    
    Formato: PYRACLAW://<prefijo><hash_base58>
    """
    hash_bytes: bytes
    prefix: bytes = HASH_PREFIX_CONTENT
    
    @classmethod
    def from_content(cls, data: bytes) -> 'PyraclawHash':
        """Crea hash desde contenido."""
        h = hashlib.sha3_256(data).digest()
        return cls(hash_bytes=h, prefix=HASH_PREFIX_CONTENT)
    
    @classmethod
    def from_string(cls, s: str) -> 'PyraclawHash':
        """Parsea hash desde string."""
        if s.startswith('PYRACLAW://'):
            s = s[7:]
        
        prefix = s[:2].encode()
        hash_b58 = s[2:]
        
        # Decodificar Base58
        hash_bytes = cls._base58_decode(hash_b58)
        
        return cls(hash_bytes=hash_bytes, prefix=prefix)
    
    @staticmethod
    def _base58_decode(s: str) -> bytes:
        """Decodifica Base58."""
        ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        
        num = 0
        for char in s:
            num = num * 58 + ALPHABET.index(char)
        
        # Convertir a bytes
        result = []
        while num > 0:
            result.append(num & 0xff)
            num >>= 8
        
        return bytes(reversed(result))
    
    def to_string(self) -> str:
        """Convierte a string."""
        return f"PYRACLAW://{self.prefix.decode()}{hash_to_base58(self.hash_bytes)}"
    
    def short(self) -> str:
        """Versión corta."""
        full = self.to_string()
        return f"{full[:15]}...{full[-6:]}"
    
    def __eq__(self, other):
        if isinstance(other, PyraclawHash):
            return self.hash_bytes == other.hash_bytes
        return False
    
    def __hash__(self):
        return hash(self.hash_bytes)
    
    def __repr__(self):
        return self.short()


# =============================================================================
# CHUNKS
# =============================================================================

@dataclass
class ChunkInfo:
    """Información de un chunk."""
    index: int
    hash: PyraclawHash
    size: int
    
    def to_dict(self) -> Dict:
        return {
            'index': self.index,
            'hash': self.hash.to_string(),
            'size': self.size,
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ChunkInfo':
        return cls(
            index=d['index'],
            hash=PyraclawHash.from_string(d['hash']),
            size=d['size']
        )


# =============================================================================
# MANIFEST
# =============================================================================

@dataclass
class Manifest:
    """
    Manifest de un objeto nodal Pyraclaw.
    
    Contiene metadatos y lista de chunks.
    """
    object_hash: PyraclawHash
    manifest_hash: Optional[PyraclawHash] = None
    content_type: ContentType = ContentType.FILE
    mime_type: str = "application/octet-stream"
    size: int = 0
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunks: List[ChunkInfo] = field(default_factory=list)
    created_at: int = 0
    creator_id: Optional[bytes] = None
    phi_minimum: float = 0.7
    replication: ReplicationType = ReplicationType.AUTOMATIC
    encryption: EncryptionType = EncryptionType.NONE
    tags: List[str] = field(default_factory=list)
    legacy_url: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time_ns() // 1_000_000
    
    @classmethod
    def from_data(cls, data: bytes, **kwargs) -> 'Manifest':
        """Crea manifest desde datos."""
        object_hash = PyraclawHash.from_content(data)
        chunk_size = kwargs.get('chunk_size', DEFAULT_CHUNK_SIZE)
        
        # Crear chunks
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunk_data = data[i:i + chunk_size]
            chunk_hash = PyraclawHash(
                hash_bytes=hashlib.sha3_256(chunk_data).digest(),
                prefix=HASH_PREFIX_CHUNK
            )
            chunks.append(ChunkInfo(
                index=len(chunks),
                hash=chunk_hash,
                size=len(chunk_data)
            ))
        
        manifest = cls(
            object_hash=object_hash,
            size=len(data),
            chunk_size=chunk_size,
            chunks=chunks,
            **{k: v for k, v in kwargs.items() if k != 'chunk_size'}
        )
        
        # Calcular hash del manifest
        manifest.manifest_hash = PyraclawHash(
            hash_bytes=hashlib.sha3_256(manifest.to_bytes()).digest(),
            prefix=HASH_PREFIX_MANIFEST
        )
        
        return manifest
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            'object_hash': self.object_hash.to_string(),
            'manifest_hash': self.manifest_hash.to_string() if self.manifest_hash else None,
            'content_type': self.content_type.value,
            'mime_type': self.mime_type,
            'size': self.size,
            'chunk_size': self.chunk_size,
            'chunk_count': len(self.chunks),
            'chunks': [c.to_dict() for c in self.chunks],
            'created_at': self.created_at,
            'creator_id': self.creator_id.hex() if self.creator_id else None,
            'phi_minimum': self.phi_minimum,
            'replication': self.replication.value,
            'encryption': self.encryption.value,
            'tags': self.tags,
            'legacy_url': self.legacy_url,
        }
    
    def to_bytes(self) -> bytes:
        """Serializa a bytes."""
        return json.dumps(self.to_dict()).encode()
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Manifest':
        """Deserializa desde bytes."""
        d = json.loads(data.decode())
        
        return cls(
            object_hash=PyraclawHash.from_string(d['object_hash']),
            manifest_hash=PyraclawHash.from_string(d['manifest_hash']) if d.get('manifest_hash') else None,
            content_type=ContentType(d['content_type']),
            mime_type=d['mime_type'],
            size=d['size'],
            chunk_size=d['chunk_size'],
            chunks=[ChunkInfo.from_dict(c) for c in d['chunks']],
            created_at=d['created_at'],
            creator_id=bytes.fromhex(d['creator_id']) if d.get('creator_id') else None,
            phi_minimum=d['phi_minimum'],
            replication=ReplicationType(d['replication']),
            encryption=EncryptionType(d['encryption']),
            tags=d.get('tags', []),
            legacy_url=d.get('legacy_url'),
        )


# =============================================================================
# ALMACENAMIENTO LOCAL
# =============================================================================

class LocalStorage:
    """
    Almacenamiento local de chunks y manifests.
    """
    
    def __init__(self, path: str = "./pyraclaw_storage"):
        self.path = Path(path)
        self.chunks_path = self.path / "chunks"
        self.manifests_path = self.path / "manifests"
        
        # Crear directorios
        self.chunks_path.mkdir(parents=True, exist_ok=True)
        self.manifests_path.mkdir(parents=True, exist_ok=True)
        
        # Cache en memoria
        self._manifest_cache: Dict[bytes, Manifest] = {}
        
    def store_object(self, data: bytes, **kwargs) -> Manifest:
        """
        Almacena un objeto completo.
        
        Returns:
            Manifest del objeto almacenado
        """
        manifest = Manifest.from_data(data, **kwargs)
        
        # Almacenar chunks
        offset = 0
        for chunk_info in manifest.chunks:
            chunk_data = data[offset:offset + chunk_info.size]
            self._store_chunk(chunk_info.hash.hash_bytes, chunk_data)
            offset += chunk_info.size
        
        # Almacenar manifest
        self._store_manifest(manifest)
        
        return manifest
    
    def get_object(self, object_hash: PyraclawHash) -> Optional[bytes]:
        """
        Recupera un objeto completo.
        """
        manifest = self.get_manifest(object_hash)
        if not manifest:
            return None
        
        # Ensamblar chunks
        chunks = []
        for chunk_info in manifest.chunks:
            chunk_data = self._get_chunk(chunk_info.hash.hash_bytes)
            if chunk_data is None:
                return None  # Chunk faltante
            chunks.append(chunk_data)
        
        data = b''.join(chunks)
        
        # Verificar hash
        if PyraclawHash.from_content(data).hash_bytes != object_hash.hash_bytes:
            return None  # Hash no coincide
        
        return data
    
    def has_object(self, object_hash: PyraclawHash) -> bool:
        """Verifica si tenemos un objeto."""
        manifest = self.get_manifest(object_hash)
        if not manifest:
            return False
        
        # Verificar que tenemos todos los chunks
        for chunk_info in manifest.chunks:
            if not self._has_chunk(chunk_info.hash.hash_bytes):
                return False
        
        return True
    
    def get_manifest(self, object_hash: PyraclawHash) -> Optional[Manifest]:
        """Obtiene manifest por hash de objeto."""
        # Cache
        if object_hash.hash_bytes in self._manifest_cache:
            return self._manifest_cache[object_hash.hash_bytes]
        
        # Buscar en disco
        manifest_file = self.manifests_path / f"{object_hash.hash_bytes.hex()}.json"
        if manifest_file.exists():
            manifest = Manifest.from_bytes(manifest_file.read_bytes())
            self._manifest_cache[object_hash.hash_bytes] = manifest
            return manifest
        
        return None
    
    def _store_chunk(self, chunk_hash: bytes, data: bytes):
        """Almacena un chunk."""
        chunk_file = self.chunks_path / chunk_hash.hex()
        chunk_file.write_bytes(data)
    
    def _get_chunk(self, chunk_hash: bytes) -> Optional[bytes]:
        """Obtiene un chunk."""
        chunk_file = self.chunks_path / chunk_hash.hex()
        if chunk_file.exists():
            return chunk_file.read_bytes()
        return None
    
    def _has_chunk(self, chunk_hash: bytes) -> bool:
        """Verifica si tenemos un chunk."""
        chunk_file = self.chunks_path / chunk_hash.hex()
        return chunk_file.exists()
    
    def _store_manifest(self, manifest: Manifest):
        """Almacena un manifest."""
        manifest_file = self.manifests_path / f"{manifest.object_hash.hash_bytes.hex()}.json"
        manifest_file.write_bytes(manifest.to_bytes())
        self._manifest_cache[manifest.object_hash.hash_bytes] = manifest
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de almacenamiento."""
        chunks = list(self.chunks_path.glob('*'))
        manifests = list(self.manifests_path.glob('*.json'))
        
        total_size = sum(f.stat().st_size for f in chunks)
        
        return {
            'chunks_count': len(chunks),
            'manifests_count': len(manifests),
            'total_size_mb': total_size / (1024 * 1024),
        }


# =============================================================================
# REPLICACIÓN ADAPTATIVA
# =============================================================================

class ReplicationManager:
    """
    Gestor de replicación adaptativa.
    
    Replica contenido según Φ de demanda:
    - Viral (Φ ≥ 0.95): 1000 réplicas
    - Popular (Φ ≥ 0.85): 100 réplicas
    - Moderado (Φ ≥ 0.70): 20 réplicas
    - Bajo (Φ ≥ 0.50): 5 réplicas
    - Mínimo: 2 réplicas
    - Archivo: 1 réplica
    """
    
    REPLICATION_LEVELS = {
        0.95: 1000,
        0.85: 100,
        0.70: 20,
        0.50: 5,
        0.30: 2,
        0.00: 1,
    }
    
    def __init__(self, storage: LocalStorage):
        self.storage = storage
        self.demand_tracker: Dict[bytes, Dict] = {}
        
    def track_request(self, content_hash: bytes):
        """Registra una solicitud."""
        if content_hash not in self.demand_tracker:
            self.demand_tracker[content_hash] = {
                'requests_24h': 0,
                'last_request': 0,
                'first_seen': time.time_ns() // 1_000_000,
            }
        
        self.demand_tracker[content_hash]['requests_24h'] += 1
        self.demand_tracker[content_hash]['last_request'] = time.time_ns() // 1_000_000
    
    def calculate_phi_demand(self, content_hash: bytes) -> float:
        """
        Calcula Φ de demanda.
        
        Φ_demand = (requests_24h × importance) / (size_mb × age_factor)
        """
        if content_hash not in self.demand_tracker:
            return 0.0
        
        info = self.demand_tracker[content_hash]
        manifest = self.storage.get_manifest(PyraclawHash(content_hash, HASH_PREFIX_CONTENT))
        
        if not manifest:
            return 0.0
        
        requests = info['requests_24h']
        importance = 5.0  # Base importance
        size_mb = manifest.size / (1024 * 1024)
        
        age_ms = time.time_ns() // 1_000_000 - info['first_seen']
        age_days = age_ms / (86400 * 1000)
        age_factor = 1 + (age_days / 30)
        
        phi = (requests * importance) / (max(1, size_mb) * age_factor)
        return min(1.0, phi / 100)
    
    def get_target_replicas(self, content_hash: bytes) -> int:
        """Determina réplicas objetivo."""
        phi = self.calculate_phi_demand(content_hash)
        
        for threshold, replicas in sorted(
            self.REPLICATION_LEVELS.items(),
            reverse=True
        ):
            if phi >= threshold:
                return replicas
        
        return 1


# =============================================================================
# SISTEMA DE NOMBRES
# =============================================================================

@dataclass
class NameRecord:
    """Registro de nombre/alias."""
    name: str
    content_hash: PyraclawHash
    owner_pubkey: bytes
    created_at: int
    expires_at: int
    version: int = 1
    signature: Optional[bytes] = None
    previous_hash: Optional[PyraclawHash] = None
    
    def to_bytes(self) -> bytes:
        """Serializa para firma."""
        return json.dumps({
            'name': self.name,
            'content_hash': self.content_hash.to_string(),
            'owner_pubkey': self.owner_pubkey.hex(),
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'version': self.version,
        }).encode()


class NameRegistry:
    """
    Registro de nombres/alias distribuido.
    
    Mapea nombres legibles a hashes:
    - "wikipedia" → PYRACLAW://Qm...
    - "@pyraclaw" → PYRACLAW://Pk...
    """
    
    NAME_TTL_MS = 365 * 24 * 3600 * 1000  # 1 año
    
    def __init__(self, storage: LocalStorage):
        self.storage = storage
        self.local_names: Dict[str, NameRecord] = {}
        self._names_file = storage.path / "names.json"
        self._load_names()
    
    def _load_names(self):
        """Carga nombres del disco."""
        if self._names_file.exists():
            data = json.loads(self._names_file.read_text())
            for name, record_data in data.items():
                self.local_names[name] = NameRecord(
                    name=record_data['name'],
                    content_hash=PyraclawHash.from_string(record_data['content_hash']),
                    owner_pubkey=bytes.fromhex(record_data['owner_pubkey']),
                    created_at=record_data['created_at'],
                    expires_at=record_data['expires_at'],
                    version=record_data['version'],
                )
    
    def _save_names(self):
        """Guarda nombres al disco."""
        data = {}
        for name, record in self.local_names.items():
            data[name] = {
                'name': record.name,
                'content_hash': record.content_hash.to_string(),
                'owner_pubkey': record.owner_pubkey.hex(),
                'created_at': record.created_at,
                'expires_at': record.expires_at,
                'version': record.version,
            }
        self._names_file.write_text(json.dumps(data, indent=2))
    
    def register(self, name: str, content_hash: PyraclawHash, 
                 owner_pubkey: bytes) -> NameRecord:
        """Registra un nombre."""
        if not self._validate_name(name):
            raise ValueError(f"Invalid name: {name}")
        
        now = time.time_ns() // 1_000_000
        
        record = NameRecord(
            name=name,
            content_hash=content_hash,
            owner_pubkey=owner_pubkey,
            created_at=now,
            expires_at=now + self.NAME_TTL_MS,
        )
        
        self.local_names[name] = record
        self._save_names()
        
        return record
    
    def resolve(self, name: str) -> Optional[PyraclawHash]:
        """Resuelve nombre a hash."""
        if name in self.local_names:
            record = self.local_names[name]
            
            # Verificar expiración
            if record.expires_at < time.time_ns() // 1_000_000:
                return None
            
            return record.content_hash
        
        return None
    
    def _validate_name(self, name: str) -> bool:
        """Valida formato de nombre."""
        import re
        
        if len(name) < 3 or len(name) > 64:
            return False
        
        if name[0] in '.-' or name[-1] in '.-':
            return False
        
        return bool(re.match(r'^[a-z0-9@][a-z0-9\-\.]*[a-z0-9]$', name.lower()))


# =============================================================================
# DESCARGADOR DE CHUNKS
# =============================================================================

class ChunkDownloader:
    """
    Descargador de chunks en paralelo.
    
    Similar a BitTorrent pero integrado con Pyraclaw.
    """
    
    MAX_PARALLEL = 10
    
    def __init__(self, storage: LocalStorage):
        self.storage = storage
        self.active_downloads: Dict[bytes, Dict] = {}
    
    def download_object(self, manifest: Manifest, 
                        providers: Dict[bytes, List[bytes]]) -> Optional[bytes]:
        """
        Descarga objeto completo.
        
        Args:
            manifest: Manifest del objeto
            providers: Diccionario chunk_hash -> lista de node_ids
            
        Returns:
            Datos completos o None si falla
        """
        chunks = [None] * len(manifest.chunks)
        
        for chunk_info in manifest.chunks:
            # Intentar obtener localmente primero
            local_data = self.storage._get_chunk(chunk_info.hash.hash_bytes)
            if local_data:
                chunks[chunk_info.index] = local_data
                continue
            
            # TODO: Descargar de proveedores remotos
            # Por ahora retornamos None si falta algún chunk
            return None
        
        # Ensamblar
        data = b''.join(chunks)
        
        # Verificar
        if PyraclawHash.from_content(data).hash_bytes != manifest.object_hash.hash_bytes:
            return None
        
        return data


# =============================================================================
# MAIN - DEMO
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Pyraclaw-TTA DISTRIBUTED CONTENT SYSTEM - TEST")
    print("=" * 70)
    
    # Test almacenamiento
    print("\n💾 Test Almacenamiento Local:")
    storage = LocalStorage("./test_storage")
    
    # Crear contenido de prueba
    test_data = b"Hello, Pyraclaw! " * 1000  # ~13 KB
    print(f"   Datos de prueba: {len(test_data)} bytes")
    
    # Almacenar
    manifest = storage.store_object(
        test_data,
        mime_type="text/plain",
        tags=["test", "hello"]
    )
    
    print(f"   Object Hash: {manifest.object_hash.short()}")
    print(f"   Manifest Hash: {manifest.manifest_hash.short()}")
    print(f"   Chunks: {len(manifest.chunks)}")
    
    # Recuperar
    recovered = storage.get_object(manifest.object_hash)
    print(f"   Recovered: {recovered == test_data}")
    
    # Stats
    stats = storage.get_stats()
    print(f"   Storage Stats: {stats}")
    
    # Test nombres
    print("\n📛 Test Registro de Nombres:")
    registry = NameRegistry(storage)
    
    owner_key = b'\x00' * 32  # Clave dummy
    record = registry.register("test-content", manifest.object_hash, owner_key)
    print(f"   Registered: {record.name} → {record.content_hash.short()}")
    
    resolved = registry.resolve("test-content")
    print(f"   Resolved: {resolved.short() if resolved else 'Not found'}")
    
    # Test replicación
    print("\n📊 Test Replicación Adaptativa:")
    replication = ReplicationManager(storage)
    
    # Simular solicitudes
    for _ in range(100):
        replication.track_request(manifest.object_hash.hash_bytes)
    
    phi_demand = replication.calculate_phi_demand(manifest.object_hash.hash_bytes)
    target_replicas = replication.get_target_replicas(manifest.object_hash.hash_bytes)
    
    print(f"   Φ de demanda: {phi_demand:.3f}")
    print(f"   Réplicas objetivo: {target_replicas}")
    
    # Limpiar test
    import shutil
    shutil.rmtree("./test_storage", ignore_errors=True)
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETO")
    print("=" * 70)
