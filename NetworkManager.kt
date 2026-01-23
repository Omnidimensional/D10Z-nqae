/*
 * ══════════════════════════════════════════════════════════════════════════════
 * TERRA MESH - Network Layer
 * ══════════════════════════════════════════════════════════════════════════════
 * 
 * Implementación de descubrimiento y comunicación P2P
 * - WiFi Direct (WifiP2pManager)
 * - WiFi Aware (WifiAwareManager)  
 * - Bluetooth LE Mesh
 * 
 * ══════════════════════════════════════════════════════════════════════════════
 */

package org.d10z.terramesh.network

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.aware.*
import android.net.wifi.p2p.*
import android.bluetooth.*
import android.bluetooth.le.*
import android.os.ParcelUuid
import androidx.annotation.RequiresPermission
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.d10z.terramesh.core.*
import java.io.*
import java.net.*
import java.nio.ByteBuffer
import java.util.UUID

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTES DE RED
// ═══════════════════════════════════════════════════════════════════════════════

object NetworkConstants {
    // WiFi Direct
    const val WIFI_DIRECT_SERVICE_NAME = "d10z_terra_mesh"
    const val WIFI_DIRECT_SERVICE_TYPE = "_d10z._tcp"
    const val WIFI_DIRECT_PORT = 8470
    
    // WiFi Aware
    const val WIFI_AWARE_SERVICE_NAME = "D10Z"
    const val WIFI_AWARE_MATCH_FILTER = "TERRA_MESH"
    
    // Bluetooth LE
    val BLE_SERVICE_UUID: UUID = UUID.fromString("d10z0001-0001-0001-0001-d10zterramesh")
    val BLE_CHAR_HEARTBEAT_UUID: UUID = UUID.fromString("d10z0001-0002-0001-0001-d10zterramesh")
    val BLE_CHAR_DATA_UUID: UUID = UUID.fromString("d10z0001-0003-0001-0001-d10zterramesh")
    
    // Timeouts
    const val DISCOVERY_TIMEOUT_MS = 30000L
    const val CONNECTION_TIMEOUT_MS = 10000L
}

// ═══════════════════════════════════════════════════════════════════════════════
// SERIALIZACIÓN DE MENSAJES
// ═══════════════════════════════════════════════════════════════════════════════

object MessageSerializer {
    private const val MSG_TYPE_HEARTBEAT: Byte = 0x01
    private const val MSG_TYPE_DATA: Byte = 0x02
    private const val MSG_TYPE_CONSENSUS: Byte = 0x03
    
    fun serializeHeartbeat(msg: HeartbeatMessage): ByteArray {
        val buffer = ByteBuffer.allocate(256)
        buffer.put(MSG_TYPE_HEARTBEAT)
        buffer.putLong(msg.timestamp)
        buffer.putDouble(msg.state.phi)
        buffer.putDouble(msg.state.energy)
        buffer.putDouble(msg.state.position.x)
        buffer.putDouble(msg.state.position.y)
        buffer.putDouble(msg.state.position.z)
        buffer.putInt(msg.neighborCount)
        buffer.putDouble(msg.localE_TTA)
        
        val nodeIdBytes = msg.nodeId.toByteArray()
        buffer.putInt(nodeIdBytes.size)
        buffer.put(nodeIdBytes)
        
        return buffer.array().copyOf(buffer.position())
    }
    
    fun deserializeHeartbeat(data: ByteArray): HeartbeatMessage? {
        return try {
            val buffer = ByteBuffer.wrap(data)
            val type = buffer.get()
            if (type != MSG_TYPE_HEARTBEAT) return null
            
            val timestamp = buffer.getLong()
            val phi = buffer.getDouble()
            val energy = buffer.getDouble()
            val x = buffer.getDouble()
            val y = buffer.getDouble()
            val z = buffer.getDouble()
            val neighborCount = buffer.getInt()
            val localE_TTA = buffer.getDouble()
            
            val nodeIdLen = buffer.getInt()
            val nodeIdBytes = ByteArray(nodeIdLen)
            buffer.get(nodeIdBytes)
            val nodeId = String(nodeIdBytes)
            
            HeartbeatMessage(
                nodeId = nodeId,
                timestamp = timestamp,
                state = NodalState(
                    position = Vector3D(x, y, z),
                    phi = phi,
                    energy = energy
                ),
                neighborCount = neighborCount,
                localE_TTA = localE_TTA
            )
        } catch (e: Exception) {
            null
        }
    }
    
    fun serializePacket(packet: DataPacket): ByteArray {
        val buffer = ByteBuffer.allocate(4096)
        buffer.put(MSG_TYPE_DATA)
        
        val idBytes = packet.id.toByteArray()
        buffer.putInt(idBytes.size)
        buffer.put(idBytes)
        
        val srcBytes = packet.sourceId.toByteArray()
        buffer.putInt(srcBytes.size)
        buffer.put(srcBytes)
        
        val dstBytes = packet.destinationId.toByteArray()
        buffer.putInt(dstBytes.size)
        buffer.put(dstBytes)
        
        buffer.putInt(packet.hopCount)
        buffer.putLong(packet.timestamp)
        
        buffer.putInt(packet.payload.size)
        buffer.put(packet.payload)
        
        return buffer.array().copyOf(buffer.position())
    }
    
    fun deserializePacket(data: ByteArray): DataPacket? {
        return try {
            val buffer = ByteBuffer.wrap(data)
            val type = buffer.get()
            if (type != MSG_TYPE_DATA) return null
            
            fun readString(): String {
                val len = buffer.getInt()
                val bytes = ByteArray(len)
                buffer.get(bytes)
                return String(bytes)
            }
            
            val id = readString()
            val sourceId = readString()
            val destinationId = readString()
            val hopCount = buffer.getInt()
            val timestamp = buffer.getLong()
            
            val payloadLen = buffer.getInt()
            val payload = ByteArray(payloadLen)
            buffer.get(payload)
            
            DataPacket(
                id = id,
                sourceId = sourceId,
                destinationId = destinationId,
                hopCount = hopCount,
                timestamp = timestamp,
                payload = payload
            )
        } catch (e: Exception) {
            null
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// WIFI DIRECT MANAGER
// ═══════════════════════════════════════════════════════════════════════════════

class WifiDirectManager(
    private val context: Context,
    private val scope: CoroutineScope
) {
    private var wifiP2pManager: WifiP2pManager? = null
    private var channel: WifiP2pManager.Channel? = null
    private var receiver: BroadcastReceiver? = null
    
    private val _peers = MutableStateFlow<List<WifiP2pDevice>>(emptyList())
    val peers: StateFlow<List<WifiP2pDevice>> = _peers.asStateFlow()
    
    private val _connectionInfo = MutableStateFlow<WifiP2pInfo?>(null)
    val connectionInfo: StateFlow<WifiP2pInfo?> = _connectionInfo.asStateFlow()
    
    private var serverSocket: ServerSocket? = null
    private var isGroupOwner = false
    
    // Callbacks
    var onHeartbeatReceived: ((HeartbeatMessage, String) -> Unit)? = null
    var onPacketReceived: ((DataPacket, String) -> Unit)? = null
    
    @RequiresPermission(allOf = [
        Manifest.permission.ACCESS_FINE_LOCATION,
        Manifest.permission.NEARBY_WIFI_DEVICES
    ])
    fun initialize() {
        wifiP2pManager = context.getSystemService(Context.WIFI_P2P_SERVICE) as? WifiP2pManager
        channel = wifiP2pManager?.initialize(context, context.mainLooper, null)
        
        val intentFilter = IntentFilter().apply {
            addAction(WifiP2pManager.WIFI_P2P_STATE_CHANGED_ACTION)
            addAction(WifiP2pManager.WIFI_P2P_PEERS_CHANGED_ACTION)
            addAction(WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION)
            addAction(WifiP2pManager.WIFI_P2P_THIS_DEVICE_CHANGED_ACTION)
        }
        
        receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                when (intent.action) {
                    WifiP2pManager.WIFI_P2P_PEERS_CHANGED_ACTION -> {
                        requestPeers()
                    }
                    WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION -> {
                        requestConnectionInfo()
                    }
                }
            }
        }
        
        context.registerReceiver(receiver, intentFilter)
    }
    
    @RequiresPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
    fun startDiscovery() {
        channel?.let { ch ->
            wifiP2pManager?.discoverPeers(ch, object : WifiP2pManager.ActionListener {
                override fun onSuccess() {
                    // Discovery started
                }
                override fun onFailure(reason: Int) {
                    // Handle failure
                }
            })
        }
    }
    
    @RequiresPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
    fun stopDiscovery() {
        channel?.let { ch ->
            wifiP2pManager?.stopPeerDiscovery(ch, null)
        }
    }
    
    @RequiresPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
    private fun requestPeers() {
        channel?.let { ch ->
            wifiP2pManager?.requestPeers(ch) { peers ->
                _peers.value = peers.deviceList.toList()
            }
        }
    }
    
    @RequiresPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
    private fun requestConnectionInfo() {
        channel?.let { ch ->
            wifiP2pManager?.requestConnectionInfo(ch) { info ->
                _connectionInfo.value = info
                if (info.groupFormed) {
                    isGroupOwner = info.isGroupOwner
                    if (isGroupOwner) {
                        startServer()
                    } else {
                        connectToGroupOwner(info.groupOwnerAddress)
                    }
                }
            }
        }
    }
    
    @RequiresPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
    fun connectTo(device: WifiP2pDevice) {
        val config = WifiP2pConfig().apply {
            deviceAddress = device.deviceAddress
        }
        
        channel?.let { ch ->
            wifiP2pManager?.connect(ch, config, null)
        }
    }
    
    private fun startServer() {
        scope.launch(Dispatchers.IO) {
            try {
                serverSocket = ServerSocket(NetworkConstants.WIFI_DIRECT_PORT)
                while (isActive) {
                    val client = serverSocket?.accept() ?: break
                    handleClient(client)
                }
            } catch (e: Exception) {
                // Handle error
            }
        }
    }
    
    private fun connectToGroupOwner(address: InetAddress) {
        scope.launch(Dispatchers.IO) {
            try {
                val socket = Socket()
                socket.connect(
                    InetSocketAddress(address, NetworkConstants.WIFI_DIRECT_PORT),
                    NetworkConstants.CONNECTION_TIMEOUT_MS.toInt()
                )
                handleClient(socket)
            } catch (e: Exception) {
                // Handle error
            }
        }
    }
    
    private fun handleClient(socket: Socket) {
        scope.launch(Dispatchers.IO) {
            try {
                val input = DataInputStream(socket.getInputStream())
                val peerAddress = socket.inetAddress.hostAddress ?: "unknown"
                
                while (isActive && socket.isConnected) {
                    val len = input.readInt()
                    val data = ByteArray(len)
                    input.readFully(data)
                    
                    // Intentar deserializar como heartbeat
                    MessageSerializer.deserializeHeartbeat(data)?.let { heartbeat ->
                        onHeartbeatReceived?.invoke(heartbeat, peerAddress)
                    }
                    
                    // Intentar deserializar como packet
                    MessageSerializer.deserializePacket(data)?.let { packet ->
                        onPacketReceived?.invoke(packet, peerAddress)
                    }
                }
            } catch (e: Exception) {
                // Connection closed
            } finally {
                socket.close()
            }
        }
    }
    
    fun broadcast(data: ByteArray) {
        // Broadcast a todos los peers conectados
        scope.launch(Dispatchers.IO) {
            _connectionInfo.value?.let { info ->
                if (info.groupFormed) {
                    // Implementar broadcast a grupo
                }
            }
        }
    }
    
    fun sendTo(address: String, data: ByteArray) {
        scope.launch(Dispatchers.IO) {
            try {
                val socket = Socket()
                socket.connect(
                    InetSocketAddress(address, NetworkConstants.WIFI_DIRECT_PORT),
                    NetworkConstants.CONNECTION_TIMEOUT_MS.toInt()
                )
                val output = DataOutputStream(socket.getOutputStream())
                output.writeInt(data.size)
                output.write(data)
                output.flush()
                socket.close()
            } catch (e: Exception) {
                // Handle error
            }
        }
    }
    
    fun shutdown() {
        receiver?.let { context.unregisterReceiver(it) }
        serverSocket?.close()
        channel?.close()
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLUETOOTH LE MESH MANAGER
// ═══════════════════════════════════════════════════════════════════════════════

class BluetoothMeshManager(
    private val context: Context,
    private val scope: CoroutineScope
) {
    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bleScanner: BluetoothLeScanner? = null
    private var bleAdvertiser: BluetoothLeAdvertiser? = null
    private var gattServer: BluetoothGattServer? = null
    
    private val connectedDevices = mutableMapOf<String, BluetoothDevice>()
    
    private val _discoveredNodes = MutableStateFlow<List<BleNodeInfo>>(emptyList())
    val discoveredNodes: StateFlow<List<BleNodeInfo>> = _discoveredNodes.asStateFlow()
    
    // Callbacks
    var onHeartbeatReceived: ((HeartbeatMessage, Int) -> Unit)? = null
    var onPacketReceived: ((DataPacket) -> Unit)? = null
    
    data class BleNodeInfo(
        val address: String,
        val name: String?,
        val rssi: Int,
        val lastSeen: Long
    )
    
    @RequiresPermission(allOf = [
        Manifest.permission.BLUETOOTH_SCAN,
        Manifest.permission.BLUETOOTH_ADVERTISE,
        Manifest.permission.BLUETOOTH_CONNECT
    ])
    fun initialize() {
        val bluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
        bluetoothAdapter = bluetoothManager?.adapter
        bleScanner = bluetoothAdapter?.bluetoothLeScanner
        bleAdvertiser = bluetoothAdapter?.bluetoothLeAdvertiser
        
        setupGattServer(bluetoothManager)
    }
    
    @RequiresPermission(Manifest.permission.BLUETOOTH_CONNECT)
    private fun setupGattServer(bluetoothManager: BluetoothManager?) {
        val callback = object : BluetoothGattServerCallback() {
            override fun onConnectionStateChange(device: BluetoothDevice, status: Int, newState: Int) {
                if (newState == BluetoothProfile.STATE_CONNECTED) {
                    connectedDevices[device.address] = device
                } else {
                    connectedDevices.remove(device.address)
                }
            }
            
            override fun onCharacteristicWriteRequest(
                device: BluetoothDevice,
                requestId: Int,
                characteristic: BluetoothGattCharacteristic,
                preparedWrite: Boolean,
                responseNeeded: Boolean,
                offset: Int,
                value: ByteArray
            ) {
                when (characteristic.uuid) {
                    NetworkConstants.BLE_CHAR_HEARTBEAT_UUID -> {
                        MessageSerializer.deserializeHeartbeat(value)?.let { heartbeat ->
                            // RSSI no disponible aquí, usar -50 como estimación
                            onHeartbeatReceived?.invoke(heartbeat, -50)
                        }
                    }
                    NetworkConstants.BLE_CHAR_DATA_UUID -> {
                        MessageSerializer.deserializePacket(value)?.let { packet ->
                            onPacketReceived?.invoke(packet)
                        }
                    }
                }
                
                if (responseNeeded) {
                    gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, 0, null)
                }
            }
        }
        
        gattServer = bluetoothManager?.openGattServer(context, callback)
        
        // Configurar servicio D10Z
        val service = BluetoothGattService(
            NetworkConstants.BLE_SERVICE_UUID,
            BluetoothGattService.SERVICE_TYPE_PRIMARY
        )
        
        val heartbeatChar = BluetoothGattCharacteristic(
            NetworkConstants.BLE_CHAR_HEARTBEAT_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_WRITE
        )
        
        val dataChar = BluetoothGattCharacteristic(
            NetworkConstants.BLE_CHAR_DATA_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_WRITE
        )
        
        service.addCharacteristic(heartbeatChar)
        service.addCharacteristic(dataChar)
        gattServer?.addService(service)
    }
    
    @RequiresPermission(Manifest.permission.BLUETOOTH_SCAN)
    fun startScan() {
        val scanFilter = ScanFilter.Builder()
            .setServiceUuid(ParcelUuid(NetworkConstants.BLE_SERVICE_UUID))
            .build()
        
        val scanSettings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        
        val scanCallback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val device = result.device
                val nodeInfo = BleNodeInfo(
                    address = device.address,
                    name = device.name,
                    rssi = result.rssi,
                    lastSeen = System.currentTimeMillis()
                )
                
                val current = _discoveredNodes.value.toMutableList()
                val existing = current.indexOfFirst { it.address == device.address }
                if (existing >= 0) {
                    current[existing] = nodeInfo
                } else {
                    current.add(nodeInfo)
                }
                _discoveredNodes.value = current
            }
        }
        
        bleScanner?.startScan(listOf(scanFilter), scanSettings, scanCallback)
    }
    
    @RequiresPermission(Manifest.permission.BLUETOOTH_ADVERTISE)
    fun startAdvertising() {
        val advertiseSettings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
            .setConnectable(true)
            .setTimeout(0)
            .build()
        
        val advertiseData = AdvertiseData.Builder()
            .setIncludeDeviceName(true)
            .addServiceUuid(ParcelUuid(NetworkConstants.BLE_SERVICE_UUID))
            .build()
        
        val advertiseCallback = object : AdvertiseCallback() {
            override fun onStartSuccess(settingsInEffect: AdvertiseSettings) {
                // Advertising started
            }
            override fun onStartFailure(errorCode: Int) {
                // Handle failure
            }
        }
        
        bleAdvertiser?.startAdvertising(advertiseSettings, advertiseData, advertiseCallback)
    }
    
    fun broadcast(data: ByteArray) {
        // Notificar a todos los dispositivos conectados
        scope.launch(Dispatchers.IO) {
            connectedDevices.values.forEach { device ->
                // Implementar notificación GATT
            }
        }
    }
    
    @RequiresPermission(Manifest.permission.BLUETOOTH_ADVERTISE)
    fun shutdown() {
        bleAdvertiser?.stopAdvertising(object : AdvertiseCallback() {})
        gattServer?.close()
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK MANAGER UNIFICADO
// ═══════════════════════════════════════════════════════════════════════════════

class TerraMeshNetworkManager(
    private val context: Context,
    private val engine: TerraMeshEngine,
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Default)
) {
    private var wifiDirectManager: WifiDirectManager? = null
    private var bluetoothMeshManager: BluetoothMeshManager? = null
    
    private val _networkState = MutableStateFlow(NetworkState())
    val networkState: StateFlow<NetworkState> = _networkState.asStateFlow()
    
    data class NetworkState(
        val wifiDirectEnabled: Boolean = false,
        val bluetoothEnabled: Boolean = false,
        val wifiDirectPeers: Int = 0,
        val bluetoothPeers: Int = 0,
        val totalConnections: Int = 0
    )
    
    @RequiresPermission(allOf = [
        Manifest.permission.ACCESS_FINE_LOCATION,
        Manifest.permission.NEARBY_WIFI_DEVICES,
        Manifest.permission.BLUETOOTH_SCAN,
        Manifest.permission.BLUETOOTH_ADVERTISE,
        Manifest.permission.BLUETOOTH_CONNECT
    ])
    fun initialize() {
        // WiFi Direct
        wifiDirectManager = WifiDirectManager(context, scope).apply {
            initialize()
            
            onHeartbeatReceived = { heartbeat, address ->
                engine.onHeartbeatReceived(
                    heartbeat = heartbeat,
                    distance = estimateDistance(-50), // Estimación
                    signalStrength = -50,
                    connectionType = ConnectionType.WIFI_DIRECT
                )
            }
            
            onPacketReceived = { packet, _ ->
                engine.onPacketReceived(packet)
            }
        }
        
        // Bluetooth LE Mesh
        bluetoothMeshManager = BluetoothMeshManager(context, scope).apply {
            initialize()
            
            onHeartbeatReceived = { heartbeat, rssi ->
                engine.onHeartbeatReceived(
                    heartbeat = heartbeat,
                    distance = estimateDistance(rssi),
                    signalStrength = rssi,
                    connectionType = ConnectionType.BLUETOOTH_LE
                )
            }
            
            onPacketReceived = { packet ->
                engine.onPacketReceived(packet)
            }
        }
        
        // Configurar engine callbacks
        engine.onSendHeartbeat = { heartbeat ->
            val data = MessageSerializer.serializeHeartbeat(heartbeat)
            wifiDirectManager?.broadcast(data)
            bluetoothMeshManager?.broadcast(data)
        }
        
        engine.onSendPacket = { packet, neighborId ->
            val data = MessageSerializer.serializePacket(packet)
            // Determinar mejor ruta y enviar
            wifiDirectManager?.sendTo(neighborId, data)
        }
        
        // Monitorear estado
        scope.launch {
            while (isActive) {
                updateNetworkState()
                delay(1000)
            }
        }
    }
    
    @RequiresPermission(allOf = [
        Manifest.permission.NEARBY_WIFI_DEVICES,
        Manifest.permission.BLUETOOTH_SCAN,
        Manifest.permission.BLUETOOTH_ADVERTISE
    ])
    fun startDiscovery() {
        wifiDirectManager?.startDiscovery()
        bluetoothMeshManager?.startScan()
        bluetoothMeshManager?.startAdvertising()
    }
    
    @RequiresPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
    fun stopDiscovery() {
        wifiDirectManager?.stopDiscovery()
    }
    
    private fun updateNetworkState() {
        val wifiPeers = wifiDirectManager?.peers?.value?.size ?: 0
        val btPeers = bluetoothMeshManager?.discoveredNodes?.value?.size ?: 0
        
        _networkState.value = NetworkState(
            wifiDirectEnabled = wifiDirectManager != null,
            bluetoothEnabled = bluetoothMeshManager != null,
            wifiDirectPeers = wifiPeers,
            bluetoothPeers = btPeers,
            totalConnections = wifiPeers + btPeers
        )
    }
    
    /**
     * Estima distancia basada en RSSI
     * Fórmula simplificada: d = 10^((TxPower - RSSI) / (10 * n))
     */
    private fun estimateDistance(rssi: Int, txPower: Int = -59, n: Double = 2.0): Double {
        return Math.pow(10.0, (txPower - rssi) / (10.0 * n))
    }
    
    fun shutdown() {
        wifiDirectManager?.shutdown()
        bluetoothMeshManager?.shutdown()
    }
}
