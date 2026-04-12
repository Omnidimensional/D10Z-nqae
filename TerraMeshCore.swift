/*
 * ══════════════════════════════════════════════════════════════════════════════
 * TERRA MESH - Pyraclaw Nodal Network App
 * ══════════════════════════════════════════════════════════════════════════════
 * 
 * Core Engine para iOS - Implementación Pyraclaw-TTA
 * Usa MultipeerConnectivity para mesh P2P
 * 
 * Autor: Byron Callaghan / Pyraclaw
 * Licencia: CC BY-NC 4.0
 * ══════════════════════════════════════════════════════════════════════════════
 */

import Foundation
import MultipeerConnectivity
import CoreBluetooth
import Combine
import CoreLocation

// MARK: - Constantes Pyraclaw

struct PyraclawConstants {
    static let gmScale: Double = 1e-51
    
    // Ley Isis
    static let alphaDecay: Double = 0.05
    static let betaCoupling: Double = 0.2
    
    // Umbrales
    static let phiOptimal: Double = 0.9
    static let phiOperational: Double = 0.7
    static let phiDegraded: Double = 0.5
    static let phiCritical: Double = 0.3
    
    // Timing
    static let heartbeatInterval: TimeInterval = 0.1
    static let consensusInterval: TimeInterval = 5.0
    static let signalTimeout: TimeInterval = 3.0
    
    // Red
    static let maxNeighbors = 20
    static let maxHopCount = 10
    
    // Multipeer
    static let serviceType = "pyraclaw-terra"
}

// MARK: - Tipos Fundamentales

struct Vector3D: Codable, Equatable {
    var x: Double = 0
    var y: Double = 0
    var z: Double = 0
    
    var magnitude: Double {
        sqrt(x*x + y*y + z*z)
    }
    
    func distance(to other: Vector3D) -> Double {
        let dx = x - other.x
        let dy = y - other.y
        let dz = z - other.z
        return sqrt(dx*dx + dy*dy + dz*dz)
    }
    
    static func + (lhs: Vector3D, rhs: Vector3D) -> Vector3D {
        Vector3D(x: lhs.x + rhs.x, y: lhs.y + rhs.y, z: lhs.z + rhs.z)
    }
    
    static func - (lhs: Vector3D, rhs: Vector3D) -> Vector3D {
        Vector3D(x: lhs.x - rhs.x, y: lhs.y - rhs.y, z: lhs.z - rhs.z)
    }
}

enum CoherenceLevel: String, Codable {
    case optimal = "Óptimo"
    case operational = "Operativo"
    case degraded = "Degradado"
    case critical = "Crítico"
    case isolated = "Aislado"
    
    static func from(phi: Double) -> CoherenceLevel {
        switch phi {
        case PyraclawConstants.phiOptimal...: return .optimal
        case PyraclawConstants.phiOperational...: return .operational
        case PyraclawConstants.phiDegraded...: return .degraded
        case PyraclawConstants.phiCritical...: return .critical
        default: return .isolated
        }
    }
    
    var color: String {
        switch self {
        case .optimal: return "#22c55e"
        case .operational: return "#84cc16"
        case .degraded: return "#eab308"
        case .critical: return "#f97316"
        case .isolated: return "#ef4444"
        }
    }
}

// MARK: - Estado Nodal

struct NodalState: Codable {
    var position: Vector3D = Vector3D()
    var velocity: Vector3D = Vector3D()
    var altitude: Double = 0
    var energy: Double = 1.0
    var frequency: Double = 2.4e9
    var phi: Double = 0.5
    
    var magnitude: Double {
        sqrt(
            pow(position.magnitude, 2) +
            pow(velocity.magnitude, 2) +
            pow(altitude, 2) +
            pow(energy, 2) +
            pow(frequency / 1e9, 2) +
            pow(phi, 2)
        )
    }
    
    var level: CoherenceLevel {
        CoherenceLevel.from(phi: phi)
    }
    
    var isOperational: Bool {
        phi >= PyraclawConstants.phiOperational
    }
}

// MARK: - Vecino

enum ConnectionType: String, Codable {
    case multipeer
    case bluetooth
    case wifi
    case fallback
}

struct NeighborInfo: Codable, Identifiable {
    let nodeId: String
    var state: NodalState
    var distance: Double
    var signalStrength: Int
    var lastSeen: Date
    var connectionType: ConnectionType
    
    var id: String { nodeId }
    
    var isActive: Bool {
        Date().timeIntervalSince(lastSeen) < PyraclawConstants.signalTimeout
    }
    
    var weight: Double {
        1.0 / max(1.0, distance)
    }
}

// MARK: - Mensajes

struct HeartbeatMessage: Codable {
    let nodeId: String
    let timestamp: Date
    let state: NodalState
    let neighborCount: Int
    let localE_TTA: Double
}

struct DataPacket: Codable, Identifiable {
    let id: String
    let sourceId: String
    let destinationId: String
    let payload: Data
    var hopCount: Int = 0
    var path: [String] = []
    let timestamp: Date
    
    func withHop(_ nodeId: String) -> DataPacket {
        var copy = self
        copy.hopCount += 1
        copy.path.append(nodeId)
        return copy
    }
}

// MARK: - Nodo Pyraclaw

class PyraclawNode: ObservableObject {
    let nodeId: String
    
    @Published var state: NodalState = NodalState()
    @Published var neighbors: [String: NeighborInfo] = [:]
    @Published var localE_TTA: Double = 0
    
    // Callbacks
    var onStateChanged: ((NodalState) -> Void)?
    var onNeighborDiscovered: ((NeighborInfo) -> Void)?
    var onCoherenceAlert: ((CoherenceLevel) -> Void)?
    
    init(nodeId: String = UUID().uuidString) {
        self.nodeId = nodeId
    }
    
    func updateState(_ newState: NodalState) {
        let oldLevel = state.level
        state = newState
        
        if newState.level != oldLevel {
            onCoherenceAlert?(newState.level)
        }
        
        onStateChanged?(newState)
        computeLocalE_TTA()
    }
    
    func updatePhi(_ newPhi: Double) {
        var newState = state
        newState.phi = max(0, min(1, newPhi))
        updateState(newState)
    }
    
    func updatePosition(lat: Double, lon: Double, alt: Double) {
        let x = lon * 111320 * cos(lat * .pi / 180)
        let y = lat * 110540
        var newState = state
        newState.position = Vector3D(x: x, y: y, z: alt)
        newState.altitude = alt
        updateState(newState)
    }
    
    func registerNeighbor(_ neighbor: NeighborInfo) {
        // Limitar vecinos
        if neighbors.count >= PyraclawConstants.maxNeighbors && neighbors[neighbor.nodeId] == nil {
            if let oldest = neighbors.values.min(by: { $0.lastSeen < $1.lastSeen }) {
                neighbors.removeValue(forKey: oldest.nodeId)
            }
        }
        
        neighbors[neighbor.nodeId] = neighbor
        onNeighborDiscovered?(neighbor)
        computeLocalE_TTA()
    }
    
    func pruneInactiveNeighbors() {
        neighbors = neighbors.filter { $0.value.isActive }
    }
    
    private func computeLocalE_TTA() {
        var e_tta = state.magnitude * state.phi
        
        for neighbor in neighbors.values where neighbor.isActive {
            e_tta += neighbor.state.magnitude * neighbor.state.phi
        }
        
        localE_TTA = e_tta
    }
    
    func createHeartbeat() -> HeartbeatMessage {
        HeartbeatMessage(
            nodeId: nodeId,
            timestamp: Date(),
            state: state,
            neighborCount: neighbors.filter { $0.value.isActive }.count,
            localE_TTA: localE_TTA
        )
    }
    
    func processHeartbeat(_ heartbeat: HeartbeatMessage, distance: Double, signalStrength: Int, connectionType: ConnectionType) {
        registerNeighbor(NeighborInfo(
            nodeId: heartbeat.nodeId,
            state: heartbeat.state,
            distance: distance,
            signalStrength: signalStrength,
            lastSeen: Date(),
            connectionType: connectionType
        ))
    }
}

// MARK: - Ley Isis

class IsisLawEngine {
    let alpha: Double
    let beta: Double
    
    init(alpha: Double = PyraclawConstants.alphaDecay, beta: Double = PyraclawConstants.betaCoupling) {
        self.alpha = alpha
        self.beta = beta
    }
    
    func computeNewPhi(currentPhi: Double, neighbors: [NeighborInfo], dt: Double = 0.1) -> Double {
        guard !neighbors.isEmpty else {
            let decay = alpha * currentPhi
            return max(0, min(1, currentPhi - decay * dt))
        }
        
        let decay = alpha * currentPhi
        
        var coupling: Double = 0
        var totalWeight: Double = 0
        
        for neighbor in neighbors where neighbor.isActive {
            coupling += neighbor.weight * neighbor.state.phi
            totalWeight += neighbor.weight
        }
        
        if totalWeight > 0 {
            coupling = beta * coupling / totalWeight
        }
        
        let dPhi = -decay + coupling
        let newPhi = currentPhi + dPhi * dt
        
        return max(0, min(1, newPhi))
    }
    
    func propagate(_ node: PyraclawNode, dt: Double = 0.1) {
        let newPhi = computeNewPhi(
            currentPhi: node.state.phi,
            neighbors: Array(node.neighbors.values),
            dt: dt
        )
        node.updatePhi(newPhi)
    }
}

// MARK: - Router por Coherencia

enum RouteResult {
    case nextHop(neighborId: String, score: Double)
    case delivered
    case useFallback
    case failed(reason: String)
}

class CoherenceRouter {
    let minPhi: Double
    
    init(minPhi: Double = PyraclawConstants.phiOperational) {
        self.minPhi = minPhi
    }
    
    func route(_ packet: DataPacket, node: PyraclawNode) -> RouteResult {
        if packet.destinationId == node.nodeId {
            return .delivered
        }
        
        if packet.hopCount >= PyraclawConstants.maxHopCount {
            return .failed(reason: "Max hop count exceeded")
        }
        
        var bestNeighbor: String?
        var bestScore: Double = 0
        
        for (neighborId, info) in node.neighbors {
            guard info.isActive, info.state.phi >= minPhi else { continue }
            guard !packet.path.contains(neighborId) else { continue }
            
            let score = info.state.phi * Double(100 + info.signalStrength) / 100.0
            
            if score > bestScore {
                bestScore = score
                bestNeighbor = neighborId
            }
        }
        
        if let neighbor = bestNeighbor {
            return .nextHop(neighborId: neighbor, score: bestScore)
        }
        
        return .useFallback
    }
}

// MARK: - Engine Métricas

struct EngineMetrics {
    var phi: Double = 0.5
    var level: CoherenceLevel = .degraded
    var neighborCount: Int = 0
    var localE_TTA: Double = 0
    var consensusE_TTA: Double = 0
    var packetsReceived: Int = 0
    var packetsDelivered: Int = 0
    var packetsDropped: Int = 0
    var lastUpdate: Date = Date()
    
    var deliveryRate: Double {
        packetsReceived > 0 ? Double(packetsDelivered) / Double(packetsReceived) : 1.0
    }
}

// MARK: - Terra Mesh Engine

enum EngineState {
    case stopped, starting, running, paused, error
}

class TerraMeshEngine: ObservableObject {
    let node: PyraclawNode
    private let isisEngine: IsisLawEngine
    private let router: CoherenceRouter
    
    @Published var state: EngineState = .stopped
    @Published var metrics: EngineMetrics = EngineMetrics()
    
    private var heartbeatTimer: Timer?
    private var coherenceTimer: Timer?
    private var consensusTimer: Timer?
    
    // Callbacks
    var onSendHeartbeat: ((HeartbeatMessage) -> Void)?
    var onSendPacket: ((DataPacket, String) -> Void)?
    var onUseFallback: ((DataPacket) -> Void)?
    var onPacketDelivered: ((DataPacket) -> Void)?
    
    init() {
        self.node = PyraclawNode()
        self.isisEngine = IsisLawEngine()
        self.router = CoherenceRouter()
    }
    
    func start() {
        guard state != .running else { return }
        state = .starting
        
        // Heartbeat timer
        heartbeatTimer = Timer.scheduledTimer(withTimeInterval: PyraclawConstants.heartbeatInterval, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            let heartbeat = self.node.createHeartbeat()
            self.onSendHeartbeat?(heartbeat)
        }
        
        // Coherence timer
        coherenceTimer = Timer.scheduledTimer(withTimeInterval: PyraclawConstants.heartbeatInterval, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            self.node.pruneInactiveNeighbors()
            self.isisEngine.propagate(self.node)
            self.updateMetrics()
        }
        
        // Consensus timer
        consensusTimer = Timer.scheduledTimer(withTimeInterval: PyraclawConstants.consensusInterval, repeats: true) { [weak self] _ in
            self?.runConsensusRound()
        }
        
        state = .running
    }
    
    func stop() {
        heartbeatTimer?.invalidate()
        coherenceTimer?.invalidate()
        consensusTimer?.invalidate()
        state = .stopped
    }
    
    func pause() {
        heartbeatTimer?.invalidate()
        coherenceTimer?.invalidate()
        state = .paused
    }
    
    func onHeartbeatReceived(_ heartbeat: HeartbeatMessage, distance: Double, signalStrength: Int, connectionType: ConnectionType) {
        node.processHeartbeat(heartbeat, distance: distance, signalStrength: signalStrength, connectionType: connectionType)
    }
    
    func sendPacket(destinationId: String, payload: Data) -> Bool {
        let packet = DataPacket(
            id: UUID().uuidString,
            sourceId: node.nodeId,
            destinationId: destinationId,
            payload: payload,
            timestamp: Date()
        )
        return routePacket(packet)
    }
    
    func onPacketReceived(_ packet: DataPacket) -> Bool {
        metrics.packetsReceived += 1
        
        switch router.route(packet, node: node) {
        case .delivered:
            onPacketDelivered?(packet)
            metrics.packetsDelivered += 1
            return true
            
        case .nextHop(let neighborId, _):
            onSendPacket?(packet.withHop(node.nodeId), neighborId)
            return true
            
        case .useFallback:
            onUseFallback?(packet)
            return false
            
        case .failed:
            metrics.packetsDropped += 1
            return false
        }
    }
    
    private func routePacket(_ packet: DataPacket) -> Bool {
        switch router.route(packet, node: node) {
        case .delivered:
            return true
        case .nextHop(let neighborId, _):
            onSendPacket?(packet, neighborId)
            return true
        case .useFallback:
            onUseFallback?(packet)
            return false
        case .failed:
            return false
        }
    }
    
    private func runConsensusRound() {
        metrics.consensusE_TTA = node.localE_TTA
    }
    
    private func updateMetrics() {
        metrics.phi = node.state.phi
        metrics.level = node.state.level
        metrics.neighborCount = node.neighbors.filter { $0.value.isActive }.count
        metrics.localE_TTA = node.localE_TTA
        metrics.lastUpdate = Date()
    }
}

// MARK: - Multipeer Network Manager

class MultipeerNetworkManager: NSObject, ObservableObject {
    private let serviceType = PyraclawConstants.serviceType
    private let myPeerId: MCPeerID
    private var session: MCSession?
    private var advertiser: MCNearbyServiceAdvertiser?
    private var browser: MCNearbyServiceBrowser?
    
    private weak var engine: TerraMeshEngine?
    
    @Published var connectedPeers: [MCPeerID] = []
    @Published var isAdvertising = false
    @Published var isBrowsing = false
    
    init(displayName: String, engine: TerraMeshEngine) {
        self.myPeerId = MCPeerID(displayName: displayName)
        self.engine = engine
        super.init()
        
        setupSession()
        setupCallbacks()
    }
    
    private func setupSession() {
        session = MCSession(peer: myPeerId, securityIdentity: nil, encryptionPreference: .required)
        session?.delegate = self
        
        advertiser = MCNearbyServiceAdvertiser(peer: myPeerId, discoveryInfo: nil, serviceType: serviceType)
        advertiser?.delegate = self
        
        browser = MCNearbyServiceBrowser(peer: myPeerId, serviceType: serviceType)
        browser?.delegate = self
    }
    
    private func setupCallbacks() {
        engine?.onSendHeartbeat = { [weak self] heartbeat in
            self?.broadcast(heartbeat)
        }
        
        engine?.onSendPacket = { [weak self] packet, neighborId in
            self?.send(packet, to: neighborId)
        }
    }
    
    func startAdvertising() {
        advertiser?.startAdvertisingPeer()
        isAdvertising = true
    }
    
    func stopAdvertising() {
        advertiser?.stopAdvertisingPeer()
        isAdvertising = false
    }
    
    func startBrowsing() {
        browser?.startBrowsingForPeers()
        isBrowsing = true
    }
    
    func stopBrowsing() {
        browser?.stopBrowsingForPeers()
        isBrowsing = false
    }
    
    func broadcast(_ heartbeat: HeartbeatMessage) {
        guard let session = session, !session.connectedPeers.isEmpty else { return }
        
        do {
            let data = try JSONEncoder().encode(heartbeat)
            try session.send(data, toPeers: session.connectedPeers, with: .unreliable)
        } catch {
            print("Broadcast error: \(error)")
        }
    }
    
    func send(_ packet: DataPacket, to neighborId: String) {
        guard let session = session else { return }
        
        if let peer = session.connectedPeers.first(where: { $0.displayName == neighborId }) {
            do {
                let data = try JSONEncoder().encode(packet)
                try session.send(data, toPeers: [peer], with: .reliable)
            } catch {
                print("Send error: \(error)")
            }
        }
    }
    
    func disconnect() {
        session?.disconnect()
        stopAdvertising()
        stopBrowsing()
    }
}

// MARK: - MCSession Delegate

extension MultipeerNetworkManager: MCSessionDelegate {
    func session(_ session: MCSession, peer peerID: MCPeerID, didChange state: MCSessionState) {
        DispatchQueue.main.async {
            self.connectedPeers = session.connectedPeers
        }
    }
    
    func session(_ session: MCSession, didReceive data: Data, fromPeer peerID: MCPeerID) {
        // Intentar decodificar como heartbeat
        if let heartbeat = try? JSONDecoder().decode(HeartbeatMessage.self, from: data) {
            DispatchQueue.main.async {
                self.engine?.onHeartbeatReceived(
                    heartbeat,
                    distance: 10.0, // Estimación
                    signalStrength: -50,
                    connectionType: .multipeer
                )
            }
            return
        }
        
        // Intentar decodificar como packet
        if let packet = try? JSONDecoder().decode(DataPacket.self, from: data) {
            DispatchQueue.main.async {
                _ = self.engine?.onPacketReceived(packet)
            }
        }
    }
    
    func session(_ session: MCSession, didReceive stream: InputStream, withName streamName: String, fromPeer peerID: MCPeerID) {}
    func session(_ session: MCSession, didStartReceivingResourceWithName resourceName: String, fromPeer peerID: MCPeerID, with progress: Progress) {}
    func session(_ session: MCSession, didFinishReceivingResourceWithName resourceName: String, fromPeer peerID: MCPeerID, at localURL: URL?, withError error: Error?) {}
}

// MARK: - Advertiser Delegate

extension MultipeerNetworkManager: MCNearbyServiceAdvertiserDelegate {
    func advertiser(_ advertiser: MCNearbyServiceAdvertiser, didReceiveInvitationFromPeer peerID: MCPeerID, withContext context: Data?, invitationHandler: @escaping (Bool, MCSession?) -> Void) {
        invitationHandler(true, session)
    }
}

// MARK: - Browser Delegate

extension MultipeerNetworkManager: MCNearbyServiceBrowserDelegate {
    func browser(_ browser: MCNearbyServiceBrowser, foundPeer peerID: MCPeerID, withDiscoveryInfo info: [String : String]?) {
        browser.invitePeer(peerID, to: session!, withContext: nil, timeout: 10)
    }
    
    func browser(_ browser: MCNearbyServiceBrowser, lostPeer peerID: MCPeerID) {
        // Peer lost
    }
}
