/*
 * ══════════════════════════════════════════════════════════════════════════════
 * TERRA MESH - Pyraclaw Nodal Network App
 * ══════════════════════════════════════════════════════════════════════════════
 * 
 * Core Engine para Android - Implementación Pyraclaw-TTA
 * 
 * Arquitectura:
 *   - PyraclawNode: Estado nodal Zₙ y coherencia Φₙ
 *   - IsisLaw: Propagación de coherencia
 *   - CoherenceRouter: Enrutamiento por Φ
 *   - NeighborDiscovery: WiFi Direct + BLE + mDNS
 *   - ConsensusEngine: E_TTA distribuido
 * 
 * Autor: Byron Callaghan / Pyraclaw
 * Licencia: CC BY-NC 4.0
 * ══════════════════════════════════════════════════════════════════════════════
 */

package org.pyraclaw.terramesh.core

import kotlin.math.*
import java.util.concurrent.ConcurrentHashMap
import java.util.UUID
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTES Pyraclaw
// ═══════════════════════════════════════════════════════════════════════════════

object PyraclawConstants {
    // Escala universal
    const val GM_SCALE = 1e-51
    
    // Ley Isis
    const val ALPHA_DECAY = 0.05        // Tasa de decaimiento
    const val BETA_COUPLING = 0.2       // Tasa de acoplamiento
    
    // Umbrales de coherencia
    const val PHI_OPTIMAL = 0.9
    const val PHI_OPERATIONAL = 0.7
    const val PHI_DEGRADED = 0.5
    const val PHI_CRITICAL = 0.3
    
    // Timing
    const val HEARTBEAT_INTERVAL_MS = 100L
    const val CONSENSUS_INTERVAL_MS = 5000L
    const val DISCOVERY_INTERVAL_MS = 1000L
    
    // Red
    const val MAX_NEIGHBORS = 20
    const val MAX_HOP_COUNT = 10
    const val SIGNAL_TIMEOUT_MS = 3000L
}

// ═══════════════════════════════════════════════════════════════════════════════
// TIPOS FUNDAMENTALES
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Vector 3D para posición/velocidad
 */
data class Vector3D(
    val x: Double = 0.0,
    val y: Double = 0.0,
    val z: Double = 0.0
) {
    val magnitude: Double get() = sqrt(x*x + y*y + z*z)
    
    operator fun plus(other: Vector3D) = Vector3D(x + other.x, y + other.y, z + other.z)
    operator fun minus(other: Vector3D) = Vector3D(x - other.x, y - other.y, z - other.z)
    operator fun times(scalar: Double) = Vector3D(x * scalar, y * scalar, z * scalar)
    
    fun distanceTo(other: Vector3D) = (this - other).magnitude
}

/**
 * Nivel de coherencia del nodo
 */
enum class CoherenceLevel(val minPhi: Double, val label: String) {
    OPTIMAL(0.9, "Óptimo"),
    OPERATIONAL(0.7, "Operativo"),
    DEGRADED(0.5, "Degradado"),
    CRITICAL(0.3, "Crítico"),
    ISOLATED(0.0, "Aislado");
    
    companion object {
        fun fromPhi(phi: Double): CoherenceLevel = when {
            phi >= OPTIMAL.minPhi -> OPTIMAL
            phi >= OPERATIONAL.minPhi -> OPERATIONAL
            phi >= DEGRADED.minPhi -> DEGRADED
            phi >= CRITICAL.minPhi -> CRITICAL
            else -> ISOLATED
        }
    }
}

/**
 * Estado nodal completo Zₙ ∈ ℝ¹⁰
 */
data class NodalState(
    val position: Vector3D = Vector3D(),      // r₁, r₂, r₃
    val velocity: Vector3D = Vector3D(),      // v₁, v₂, v₃
    val altitude: Double = 0.0,               // a (metros sobre nivel del mar)
    val energy: Double = 1.0,                 // E (nivel de batería/energía)
    val frequency: Double = 2.4e9,            // f (Hz, frecuencia de operación)
    val phi: Double = 0.5                     // Φ (coherencia)
) {
    /**
     * Magnitud del estado |Zₙ|
     */
    val magnitude: Double get() = sqrt(
        position.magnitude.pow(2) +
        velocity.magnitude.pow(2) +
        altitude.pow(2) +
        energy.pow(2) +
        (frequency / 1e9).pow(2) +
        phi.pow(2)
    )
    
    /**
     * Nivel de coherencia
     */
    val level: CoherenceLevel get() = CoherenceLevel.fromPhi(phi)
    
    /**
     * ¿Está operativo?
     */
    val isOperational: Boolean get() = phi >= PyraclawConstants.PHI_OPERATIONAL
}

// ═══════════════════════════════════════════════════════════════════════════════
// NODO Pyraclaw
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Información de un vecino
 */
data class NeighborInfo(
    val nodeId: String,
    val state: NodalState,
    val distance: Double,           // metros
    val signalStrength: Int,        // dBm
    val lastSeen: Long,             // timestamp ms
    val connectionType: ConnectionType
) {
    val isActive: Boolean get() = 
        System.currentTimeMillis() - lastSeen < PyraclawConstants.SIGNAL_TIMEOUT_MS
    
    /**
     * Peso del enlace (inversamente proporcional a distancia)
     */
    val weight: Double get() = 1.0 / max(1.0, distance)
}

enum class ConnectionType {
    WIFI_DIRECT,
    WIFI_AWARE,
    BLUETOOTH_LE,
    BLUETOOTH_MESH,
    HOTSPOT,
    INTERNET_FALLBACK
}

/**
 * Mensaje de heartbeat
 */
data class HeartbeatMessage(
    val nodeId: String,
    val timestamp: Long,
    val state: NodalState,
    val neighborCount: Int,
    val localE_TTA: Double
)

/**
 * Nodo Pyraclaw principal
 */
class PyraclawNode(
    val nodeId: String = UUID.randomUUID().toString()
) {
    // Estado actual
    private var _state = MutableStateFlow(NodalState())
    val state: StateFlow<NodalState> = _state.asStateFlow()
    
    // Vecinos conocidos
    private val _neighbors = ConcurrentHashMap<String, NeighborInfo>()
    val neighbors: Map<String, NeighborInfo> get() = _neighbors.toMap()
    
    // Métricas
    private var _localE_TTA = MutableStateFlow(0.0)
    val localE_TTA: StateFlow<Double> = _localE_TTA.asStateFlow()
    
    // Callbacks
    var onStateChanged: ((NodalState) -> Unit)? = null
    var onNeighborDiscovered: ((NeighborInfo) -> Unit)? = null
    var onCoherenceAlert: ((CoherenceLevel) -> Unit)? = null
    
    /**
     * Actualiza el estado del nodo
     */
    fun updateState(newState: NodalState) {
        val oldLevel = _state.value.level
        _state.value = newState
        
        // Alerta si cambió de nivel
        if (newState.level != oldLevel) {
            onCoherenceAlert?.invoke(newState.level)
        }
        
        onStateChanged?.invoke(newState)
        computeLocalE_TTA()
    }
    
    /**
     * Actualiza solo la coherencia
     */
    fun updatePhi(newPhi: Double) {
        updateState(_state.value.copy(phi = newPhi.coerceIn(0.0, 1.0)))
    }
    
    /**
     * Actualiza posición (desde GPS o sensores)
     */
    fun updatePosition(lat: Double, lon: Double, alt: Double) {
        // Convertir lat/lon a vector local (simplificado)
        val x = lon * 111320 * cos(Math.toRadians(lat))
        val y = lat * 110540
        updateState(_state.value.copy(
            position = Vector3D(x, y, alt),
            altitude = alt
        ))
    }
    
    /**
     * Registra un vecino descubierto
     */
    fun registerNeighbor(neighbor: NeighborInfo) {
        // Limitar número de vecinos
        if (_neighbors.size >= PyraclawConstants.MAX_NEIGHBORS && 
            !_neighbors.containsKey(neighbor.nodeId)) {
            // Remover el vecino más antiguo
            val oldest = _neighbors.values.minByOrNull { it.lastSeen }
            oldest?.let { _neighbors.remove(it.nodeId) }
        }
        
        _neighbors[neighbor.nodeId] = neighbor
        onNeighborDiscovered?.invoke(neighbor)
        computeLocalE_TTA()
    }
    
    /**
     * Remueve vecinos inactivos
     */
    fun pruneInactiveNeighbors() {
        val now = System.currentTimeMillis()
        _neighbors.entries.removeIf { (_, info) ->
            now - info.lastSeen > PyraclawConstants.SIGNAL_TIMEOUT_MS
        }
    }
    
    /**
     * Calcula E_TTA local (este nodo + vecinos)
     */
    private fun computeLocalE_TTA() {
        // E_TTA = Σ |Zₙ| · Φₙ
        var e_tta = _state.value.magnitude * _state.value.phi
        
        for (neighbor in _neighbors.values) {
            if (neighbor.isActive) {
                e_tta += neighbor.state.magnitude * neighbor.state.phi
            }
        }
        
        _localE_TTA.value = e_tta
    }
    
    /**
     * Genera mensaje de heartbeat
     */
    fun createHeartbeat(): HeartbeatMessage {
        return HeartbeatMessage(
            nodeId = nodeId,
            timestamp = System.currentTimeMillis(),
            state = _state.value,
            neighborCount = _neighbors.count { it.value.isActive },
            localE_TTA = _localE_TTA.value
        )
    }
    
    /**
     * Procesa heartbeat recibido
     */
    fun processHeartbeat(heartbeat: HeartbeatMessage, 
                        distance: Double, 
                        signalStrength: Int,
                        connectionType: ConnectionType) {
        registerNeighbor(NeighborInfo(
            nodeId = heartbeat.nodeId,
            state = heartbeat.state,
            distance = distance,
            signalStrength = signalStrength,
            lastSeen = System.currentTimeMillis(),
            connectionType = connectionType
        ))
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// LEY ISIS: PROPAGACIÓN DE COHERENCIA
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Motor de propagación de coherencia según Ley Isis
 * 
 * ∂Φₖ/∂t = -αΦₖ + β Σⱼ wₖⱼ Φⱼ / |Nₖ|
 */
class IsisLawEngine(
    private val alpha: Double = PyraclawConstants.ALPHA_DECAY,
    private val beta: Double = PyraclawConstants.BETA_COUPLING
) {
    /**
     * Calcula nuevo Φ para un nodo dado sus vecinos
     */
    fun computeNewPhi(currentPhi: Double, neighbors: Collection<NeighborInfo>, dt: Double = 0.1): Double {
        if (neighbors.isEmpty()) {
            // Sin vecinos, solo decaimiento
            val decay = alpha * currentPhi
            return (currentPhi - decay * dt).coerceIn(0.0, 1.0)
        }
        
        // Decaimiento
        val decay = alpha * currentPhi
        
        // Acoplamiento con vecinos
        var coupling = 0.0
        var totalWeight = 0.0
        
        for (neighbor in neighbors) {
            if (neighbor.isActive) {
                coupling += neighbor.weight * neighbor.state.phi
                totalWeight += neighbor.weight
            }
        }
        
        if (totalWeight > 0) {
            coupling = beta * coupling / totalWeight
        }
        
        // ∂Φ/∂t = -αΦ + β×(weighted average of neighbor Φ)
        val dPhi = -decay + coupling
        val newPhi = currentPhi + dPhi * dt
        
        return newPhi.coerceIn(0.0, 1.0)
    }
    
    /**
     * Propaga coherencia en todo el grafo local
     */
    fun propagate(node: PyraclawNode, dt: Double = 0.1) {
        val newPhi = computeNewPhi(
            currentPhi = node.state.value.phi,
            neighbors = node.neighbors.values,
            dt = dt
        )
        node.updatePhi(newPhi)
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// ENRUTAMIENTO POR COHERENCIA
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Paquete de datos
 */
data class DataPacket(
    val id: String = UUID.randomUUID().toString(),
    val sourceId: String,
    val destinationId: String,
    val payload: ByteArray,
    val hopCount: Int = 0,
    val path: List<String> = emptyList(),
    val timestamp: Long = System.currentTimeMillis()
) {
    fun withHop(nodeId: String) = copy(
        hopCount = hopCount + 1,
        path = path + nodeId
    )
}

/**
 * Resultado de enrutamiento
 */
sealed class RouteResult {
    data class NextHop(val neighborId: String, val score: Double) : RouteResult()
    object Delivered : RouteResult()
    object UseFallback : RouteResult()
    data class Failed(val reason: String) : RouteResult()
}

/**
 * Router basado en coherencia
 */
class CoherenceRouter(
    private val minPhi: Double = PyraclawConstants.PHI_OPERATIONAL
) {
    /**
     * Determina el siguiente salto para un paquete
     */
    fun route(packet: DataPacket, node: PyraclawNode): RouteResult {
        // ¿Llegó al destino?
        if (packet.destinationId == node.nodeId) {
            return RouteResult.Delivered
        }
        
        // ¿Excedió saltos máximos?
        if (packet.hopCount >= PyraclawConstants.MAX_HOP_COUNT) {
            return RouteResult.Failed("Max hop count exceeded")
        }
        
        // Buscar mejor vecino por coherencia
        var bestNeighbor: String? = null
        var bestScore = 0.0
        
        for ((neighborId, info) in node.neighbors) {
            // Skip inactivos o con baja coherencia
            if (!info.isActive || info.state.phi < minPhi) continue
            
            // Skip si ya está en el path (evitar loops)
            if (neighborId in packet.path) continue
            
            // Score = Φ × (1 / distancia al destino estimada)
            // Simplificado: usamos Φ × señal
            val score = info.state.phi * (100 + info.signalStrength) / 100.0
            
            if (score > bestScore) {
                bestScore = score
                bestNeighbor = neighborId
            }
        }
        
        return when {
            bestNeighbor != null -> RouteResult.NextHop(bestNeighbor, bestScore)
            else -> RouteResult.UseFallback
        }
    }
    
    /**
     * Encuentra la mejor ruta completa (si es posible)
     */
    fun findPath(
        sourceId: String,
        destinationId: String,
        nodes: Map<String, PyraclawNode>,
        maxDepth: Int = PyraclawConstants.MAX_HOP_COUNT
    ): List<String>? {
        // BFS con prioridad por coherencia
        val visited = mutableSetOf<String>()
        val queue = ArrayDeque<Pair<String, List<String>>>()
        queue.add(sourceId to listOf(sourceId))
        
        while (queue.isNotEmpty() && visited.size < maxDepth * 10) {
            val (currentId, path) = queue.removeFirst()
            
            if (currentId == destinationId) {
                return path
            }
            
            if (currentId in visited) continue
            visited.add(currentId)
            
            val node = nodes[currentId] ?: continue
            
            // Ordenar vecinos por coherencia descendente
            val sortedNeighbors = node.neighbors.values
                .filter { it.isActive && it.state.phi >= minPhi && it.nodeId !in visited }
                .sortedByDescending { it.state.phi }
            
            for (neighbor in sortedNeighbors) {
                queue.add(neighbor.nodeId to path + neighbor.nodeId)
            }
        }
        
        return null
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MOTOR DE CONSENSO E_TTA
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Propuesta de consenso
 */
data class ConsensusProposal(
    val proposerId: String,
    val timestamp: Long,
    val proposedE_TTA: Double,
    val nodeCount: Int,
    val round: Int
)

/**
 * Voto de consenso
 */
data class ConsensusVote(
    val voterId: String,
    val proposalId: String,
    val agree: Boolean,
    val localE_TTA: Double
)

/**
 * Motor de consenso distribuido
 */
class ConsensusEngine(
    private val node: PyraclawNode
) {
    private var currentRound = 0
    private val votes = ConcurrentHashMap<String, ConsensusVote>()
    private var lastConsensusE_TTA = 0.0
    
    /**
     * E_TTA consensuado
     */
    val consensusE_TTA: Double get() = lastConsensusE_TTA
    
    /**
     * Crea propuesta de consenso
     */
    fun createProposal(): ConsensusProposal {
        return ConsensusProposal(
            proposerId = node.nodeId,
            timestamp = System.currentTimeMillis(),
            proposedE_TTA = node.localE_TTA.value,
            nodeCount = node.neighbors.size + 1,
            round = ++currentRound
        )
    }
    
    /**
     * Vota sobre una propuesta
     */
    fun vote(proposal: ConsensusProposal): ConsensusVote {
        val localE_TTA = node.localE_TTA.value
        
        // Acepta si la diferencia es < 20%
        val diff = abs(proposal.proposedE_TTA - localE_TTA) / max(1.0, localE_TTA)
        val agree = diff < 0.2
        
        return ConsensusVote(
            voterId = node.nodeId,
            proposalId = "${proposal.proposerId}:${proposal.round}",
            agree = agree,
            localE_TTA = localE_TTA
        )
    }
    
    /**
     * Registra voto recibido
     */
    fun receiveVote(vote: ConsensusVote) {
        votes[vote.voterId] = vote
    }
    
    /**
     * Finaliza ronda y calcula consenso
     */
    fun finalizeRound(): Double {
        val allVotes = votes.values.toList()
        if (allVotes.isEmpty()) return lastConsensusE_TTA
        
        // Promedio de E_TTA de todos los votos
        val avgE_TTA = allVotes.map { it.localE_TTA }.average()
        
        // Si mayoría está de acuerdo, usar promedio
        val agreeCount = allVotes.count { it.agree }
        if (agreeCount > allVotes.size / 2) {
            lastConsensusE_TTA = avgE_TTA
        }
        
        votes.clear()
        return lastConsensusE_TTA
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TERRA MESH ENGINE (INTEGRACIÓN)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Estado del motor
 */
enum class EngineState {
    STOPPED,
    STARTING,
    RUNNING,
    PAUSED,
    ERROR
}

/**
 * Motor principal TERRA MESH
 */
class TerraMeshEngine(
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Default)
) {
    // Componentes
    val node = PyraclawNode()
    private val isisEngine = IsisLawEngine()
    private val router = CoherenceRouter()
    private val consensus = ConsensusEngine(node)
    
    // Estado
    private var _state = MutableStateFlow(EngineState.STOPPED)
    val state: StateFlow<EngineState> = _state.asStateFlow()
    
    // Jobs
    private var heartbeatJob: Job? = null
    private var coherenceJob: Job? = null
    private var consensusJob: Job? = null
    private var discoveryJob: Job? = null
    
    // Callbacks para capa de red
    var onSendHeartbeat: ((HeartbeatMessage) -> Unit)? = null
    var onSendPacket: ((DataPacket, String) -> Unit)? = null
    var onUseFallback: ((DataPacket) -> Unit)? = null
    
    // Métricas
    private var _metrics = MutableStateFlow(EngineMetrics())
    val metrics: StateFlow<EngineMetrics> = _metrics.asStateFlow()
    
    /**
     * Inicia el motor
     */
    fun start() {
        if (_state.value == EngineState.RUNNING) return
        
        _state.value = EngineState.STARTING
        
        // Job de heartbeat (cada 100ms)
        heartbeatJob = scope.launch {
            while (isActive) {
                val heartbeat = node.createHeartbeat()
                onSendHeartbeat?.invoke(heartbeat)
                delay(PyraclawConstants.HEARTBEAT_INTERVAL_MS)
            }
        }
        
        // Job de propagación de coherencia (cada 100ms)
        coherenceJob = scope.launch {
            while (isActive) {
                node.pruneInactiveNeighbors()
                isisEngine.propagate(node)
                updateMetrics()
                delay(PyraclawConstants.HEARTBEAT_INTERVAL_MS)
            }
        }
        
        // Job de consenso (cada 5s)
        consensusJob = scope.launch {
            while (isActive) {
                runConsensusRound()
                delay(PyraclawConstants.CONSENSUS_INTERVAL_MS)
            }
        }
        
        _state.value = EngineState.RUNNING
    }
    
    /**
     * Detiene el motor
     */
    fun stop() {
        heartbeatJob?.cancel()
        coherenceJob?.cancel()
        consensusJob?.cancel()
        discoveryJob?.cancel()
        _state.value = EngineState.STOPPED
    }
    
    /**
     * Pausa el motor
     */
    fun pause() {
        heartbeatJob?.cancel()
        coherenceJob?.cancel()
        _state.value = EngineState.PAUSED
    }
    
    /**
     * Procesa heartbeat recibido
     */
    fun onHeartbeatReceived(
        heartbeat: HeartbeatMessage,
        distance: Double,
        signalStrength: Int,
        connectionType: ConnectionType
    ) {
        node.processHeartbeat(heartbeat, distance, signalStrength, connectionType)
    }
    
    /**
     * Envía un paquete
     */
    fun sendPacket(destinationId: String, payload: ByteArray): Boolean {
        val packet = DataPacket(
            sourceId = node.nodeId,
            destinationId = destinationId,
            payload = payload
        )
        
        return routePacket(packet)
    }
    
    /**
     * Procesa paquete recibido
     */
    fun onPacketReceived(packet: DataPacket): Boolean {
        _metrics.value = _metrics.value.copy(
            packetsReceived = _metrics.value.packetsReceived + 1
        )
        
        return when (val result = router.route(packet, node)) {
            is RouteResult.Delivered -> {
                // Paquete para nosotros
                handleDeliveredPacket(packet)
                true
            }
            is RouteResult.NextHop -> {
                // Reenviar al siguiente salto
                onSendPacket?.invoke(packet.withHop(node.nodeId), result.neighborId)
                true
            }
            is RouteResult.UseFallback -> {
                // Usar internet tradicional
                onUseFallback?.invoke(packet)
                false
            }
            is RouteResult.Failed -> {
                _metrics.value = _metrics.value.copy(
                    packetsDropped = _metrics.value.packetsDropped + 1
                )
                false
            }
        }
    }
    
    private fun handleDeliveredPacket(packet: DataPacket) {
        // Override en subclase para manejar paquetes recibidos
        _metrics.value = _metrics.value.copy(
            packetsDelivered = _metrics.value.packetsDelivered + 1
        )
    }
    
    private suspend fun runConsensusRound() {
        val proposal = consensus.createProposal()
        // En implementación real, broadcast proposal y recolectar votos
        val e_tta = consensus.finalizeRound()
        _metrics.value = _metrics.value.copy(consensusE_TTA = e_tta)
    }
    
    private fun updateMetrics() {
        _metrics.value = _metrics.value.copy(
            phi = node.state.value.phi,
            level = node.state.value.level,
            neighborCount = node.neighbors.count { it.value.isActive },
            localE_TTA = node.localE_TTA.value,
            lastUpdate = System.currentTimeMillis()
        )
    }
}

/**
 * Métricas del motor
 */
data class EngineMetrics(
    val phi: Double = 0.5,
    val level: CoherenceLevel = CoherenceLevel.DEGRADED,
    val neighborCount: Int = 0,
    val localE_TTA: Double = 0.0,
    val consensusE_TTA: Double = 0.0,
    val packetsReceived: Long = 0,
    val packetsDelivered: Long = 0,
    val packetsDropped: Long = 0,
    val lastUpdate: Long = 0
) {
    val deliveryRate: Double get() = 
        if (packetsReceived > 0) packetsDelivered.toDouble() / packetsReceived else 1.0
}

// ═══════════════════════════════════════════════════════════════════════════════
// EJEMPLO DE USO
// ═══════════════════════════════════════════════════════════════════════════════

/*
 * Uso básico:
 * 
 * val engine = TerraMeshEngine()
 * 
 * // Configurar callbacks de red
 * engine.onSendHeartbeat = { heartbeat ->
 *     wifiDirectManager.broadcast(heartbeat.toBytes())
 *     bluetoothMesh.broadcast(heartbeat.toBytes())
 * }
 * 
 * engine.onSendPacket = { packet, neighborId ->
 *     connectionManager.sendTo(neighborId, packet.toBytes())
 * }
 * 
 * engine.onUseFallback = { packet ->
 *     internetGateway.send(packet)
 * }
 * 
 * // Iniciar
 * engine.start()
 * 
 * // Enviar datos
 * engine.sendPacket("destination-node-id", "Hello Pyraclaw".toByteArray())
 * 
 * // Observar métricas
 * engine.metrics.collect { metrics ->
 *     updateUI(metrics)
 * }
 * 
 * // Detener
 * engine.stop()
 */
