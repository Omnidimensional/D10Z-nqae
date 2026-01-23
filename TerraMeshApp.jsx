/*
 * ══════════════════════════════════════════════════════════════════════════════
 * TERRA MESH - Tu Teléfono es un Nodo Resonante
 * ══════════════════════════════════════════════════════════════════════════════
 * 
 * App que transforma cualquier smartphone en un nodo D10Z-TTA
 * Sin hardware adicional - usa WiFi Direct + Bluetooth existentes
 * 
 * "Resuena con tus vecinos, construye la red del futuro"
 * 
 * ══════════════════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTES D10Z
// ═══════════════════════════════════════════════════════════════════════════════

const D10Z = {
  ALPHA_DECAY: 0.05,
  BETA_COUPLING: 0.2,
  PHI_OPTIMAL: 0.9,
  PHI_OPERATIONAL: 0.7,
  PHI_DEGRADED: 0.5,
  PHI_CRITICAL: 0.3,
  HEARTBEAT_MS: 100,
};

const LEVELS = {
  optimal: { color: '#22c55e', glow: 'rgba(34, 197, 94, 0.5)', label: 'RESONANDO' },
  operational: { color: '#84cc16', glow: 'rgba(132, 204, 22, 0.4)', label: 'ACTIVO' },
  degraded: { color: '#eab308', glow: 'rgba(234, 179, 8, 0.4)', label: 'BUSCANDO' },
  critical: { color: '#f97316', glow: 'rgba(249, 115, 22, 0.4)', label: 'DÉBIL' },
  isolated: { color: '#ef4444', glow: 'rgba(239, 68, 68, 0.4)', label: 'AISLADO' },
};

// ═══════════════════════════════════════════════════════════════════════════════
// MOTOR D10Z (simplificado para demo)
// ═══════════════════════════════════════════════════════════════════════════════

const createNode = (id) => ({
  id,
  phi: 0.5,
  energy: 1.0,
  position: { x: 0, y: 0 },
  neighbors: [],
  e_tta: 0,
  packetsRx: 0,
  packetsTx: 0,
  uptime: 0,
});

const getLevel = (phi) => {
  if (phi >= D10Z.PHI_OPTIMAL) return 'optimal';
  if (phi >= D10Z.PHI_OPERATIONAL) return 'operational';
  if (phi >= D10Z.PHI_DEGRADED) return 'degraded';
  if (phi >= D10Z.PHI_CRITICAL) return 'critical';
  return 'isolated';
};

const propagateCoherence = (node, neighbors) => {
  if (neighbors.length === 0) {
    const decay = D10Z.ALPHA_DECAY * node.phi;
    return Math.max(0, node.phi - decay * 0.1);
  }
  
  const decay = D10Z.ALPHA_DECAY * node.phi;
  let coupling = 0;
  
  neighbors.forEach(n => {
    const weight = 1 / Math.max(1, n.distance);
    coupling += weight * n.phi;
  });
  
  coupling = D10Z.BETA_COUPLING * coupling / neighbors.length;
  const dPhi = -decay + coupling;
  
  return Math.max(0, Math.min(1, node.phi + dPhi * 0.1));
};

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENTE PRINCIPAL
// ═══════════════════════════════════════════════════════════════════════════════

export default function TerraMeshApp() {
  // Estado
  const [node, setNode] = useState(() => createNode('NODO-' + Math.random().toString(36).substr(2, 6).toUpperCase()));
  const [neighbors, setNeighbors] = useState([]);
  const [isActive, setIsActive] = useState(false);
  const [view, setView] = useState('main'); // main, map, stats, settings
  const [pulsePhase, setPulsePhase] = useState(0);
  const [messages, setMessages] = useState([]);
  
  const intervalRef = useRef(null);
  const startTimeRef = useRef(null);
  
  // Nivel actual
  const level = getLevel(node.phi);
  const levelInfo = LEVELS[level];
  
  // ─────────────────────────────────────────────────────────────────────────────
  // SIMULACIÓN (en producción: WiFi Direct + BLE reales)
  // ─────────────────────────────────────────────────────────────────────────────
  
  const simulateNeighbors = useCallback(() => {
    // Simular descubrimiento de vecinos
    const count = Math.floor(Math.random() * 5) + 1;
    const simulated = [];
    
    for (let i = 0; i < count; i++) {
      simulated.push({
        id: `VECINO-${String.fromCharCode(65 + i)}${Math.floor(Math.random() * 100)}`,
        phi: 0.6 + Math.random() * 0.4,
        distance: 5 + Math.random() * 95,
        signal: -30 - Math.random() * 40,
        lastSeen: Date.now(),
      });
    }
    
    return simulated;
  }, []);
  
  // ─────────────────────────────────────────────────────────────────────────────
  // CICLO PRINCIPAL D10Z
  // ─────────────────────────────────────────────────────────────────────────────
  
  useEffect(() => {
    if (!isActive) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    
    startTimeRef.current = Date.now();
    
    intervalRef.current = setInterval(() => {
      setNeighbors(prev => {
        // Actualizar o crear vecinos
        const updated = simulateNeighbors();
        return updated;
      });
      
      setNode(prev => {
        const newPhi = propagateCoherence(prev, neighbors);
        const magnitude = Math.sqrt(prev.position.x ** 2 + prev.position.y ** 2 + 1);
        
        return {
          ...prev,
          phi: newPhi,
          e_tta: magnitude * newPhi * 1000 + neighbors.reduce((sum, n) => sum + n.phi * 100, 0),
          uptime: Date.now() - startTimeRef.current,
          packetsRx: prev.packetsRx + Math.floor(Math.random() * 3),
          packetsTx: prev.packetsTx + 1,
        };
      });
      
      setPulsePhase(p => (p + 1) % 100);
    }, D10Z.HEARTBEAT_MS);
    
    return () => clearInterval(intervalRef.current);
  }, [isActive, neighbors, simulateNeighbors]);
  
  // ─────────────────────────────────────────────────────────────────────────────
  // HANDLERS
  // ─────────────────────────────────────────────────────────────────────────────
  
  const toggleActive = () => {
    setIsActive(!isActive);
    if (!isActive) {
      addMessage('🟢 Nodo activado - Buscando vecinos...');
    } else {
      addMessage('🔴 Nodo desactivado');
    }
  };
  
  const addMessage = (text) => {
    setMessages(prev => [{
      id: Date.now(),
      text,
      time: new Date().toLocaleTimeString(),
    }, ...prev.slice(0, 9)]);
  };
  
  const sendPing = () => {
    if (neighbors.length > 0) {
      const target = neighbors[Math.floor(Math.random() * neighbors.length)];
      addMessage(`📡 Ping enviado a ${target.id}`);
      setNode(prev => ({ ...prev, packetsTx: prev.packetsTx + 1 }));
    } else {
      addMessage('⚠️ No hay vecinos para enviar ping');
    }
  };
  
  // ═══════════════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════════════
  
  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logo}>
          <div style={{
            ...styles.logoIcon,
            background: isActive 
              ? `conic-gradient(from ${pulsePhase * 3.6}deg, ${levelInfo.color}, #6366f1, ${levelInfo.color})`
              : '#333',
          }} />
          <div>
            <h1 style={styles.logoText}>TERRA MESH</h1>
            <span style={styles.logoSubtext}>Nodo Resonante D10Z</span>
          </div>
        </div>
        <div style={{
          ...styles.statusBadge,
          background: isActive ? levelInfo.glow : 'rgba(100,100,100,0.2)',
          borderColor: isActive ? levelInfo.color : '#666',
          color: isActive ? levelInfo.color : '#666',
        }}>
          <div style={{
            ...styles.statusDot,
            background: isActive ? levelInfo.color : '#666',
            boxShadow: isActive ? `0 0 10px ${levelInfo.color}` : 'none',
          }} />
          {isActive ? levelInfo.label : 'INACTIVO'}
        </div>
      </header>
      
      {/* Main Content */}
      <main style={styles.main}>
        {/* Resonance Visualizer */}
        <div style={styles.resonanceContainer}>
          <svg viewBox="0 0 300 300" style={styles.resonanceSvg}>
            {/* Ondas de resonancia */}
            {isActive && [1, 2, 3, 4].map(i => (
              <circle
                key={i}
                cx="150"
                cy="150"
                r={30 + i * 25 + (pulsePhase % 25)}
                fill="none"
                stroke={levelInfo.color}
                strokeWidth="1"
                opacity={0.3 - i * 0.05}
                style={{
                  animation: `pulse ${2 + i * 0.5}s ease-in-out infinite`,
                }}
              />
            ))}
            
            {/* Conexiones a vecinos */}
            {isActive && neighbors.map((n, i) => {
              const angle = (i / neighbors.length) * Math.PI * 2 - Math.PI / 2;
              const distance = 50 + (100 - n.phi * 100) * 0.8;
              const x = 150 + Math.cos(angle) * distance;
              const y = 150 + Math.sin(angle) * distance;
              
              return (
                <g key={n.id}>
                  <line
                    x1="150"
                    y1="150"
                    x2={x}
                    y2={y}
                    stroke={levelInfo.color}
                    strokeWidth="2"
                    opacity={n.phi}
                    strokeDasharray={n.phi > 0.7 ? "none" : "5,5"}
                  />
                  <circle
                    cx={x}
                    cy={y}
                    r={8 + n.phi * 8}
                    fill={LEVELS[getLevel(n.phi)].color}
                    opacity={0.8}
                  />
                  <text
                    x={x}
                    y={y + 25}
                    fill="#888"
                    fontSize="10"
                    textAnchor="middle"
                  >
                    {n.id.split('-')[1]}
                  </text>
                </g>
              );
            })}
            
            {/* Nodo central (TÚ) */}
            <circle
              cx="150"
              cy="150"
              r={isActive ? 25 + node.phi * 15 : 20}
              fill={isActive ? levelInfo.color : '#333'}
              style={{
                filter: isActive ? `drop-shadow(0 0 20px ${levelInfo.glow})` : 'none',
                transition: 'all 0.3s ease',
              }}
            />
            <text
              x="150"
              y="155"
              fill="#fff"
              fontSize="12"
              fontWeight="bold"
              textAnchor="middle"
            >
              TÚ
            </text>
          </svg>
          
          {/* Phi central */}
          <div style={styles.phiDisplay}>
            <span style={{ 
              ...styles.phiValue, 
              color: levelInfo.color,
              textShadow: isActive ? `0 0 30px ${levelInfo.glow}` : 'none',
            }}>
              Φ {node.phi.toFixed(3)}
            </span>
            <span style={styles.phiLabel}>Coherencia</span>
          </div>
        </div>
        
        {/* Control Button */}
        <button
          onClick={toggleActive}
          style={{
            ...styles.mainButton,
            background: isActive 
              ? `linear-gradient(135deg, ${levelInfo.color}, #6366f1)`
              : 'linear-gradient(135deg, #333, #444)',
            boxShadow: isActive 
              ? `0 10px 40px ${levelInfo.glow}`
              : '0 5px 20px rgba(0,0,0,0.3)',
          }}
        >
          {isActive ? '■ DETENER' : '▶ ACTIVAR NODO'}
        </button>
        
        {/* Quick Stats */}
        <div style={styles.statsGrid}>
          <div style={styles.statCard}>
            <span style={styles.statValue}>{neighbors.length}</span>
            <span style={styles.statLabel}>Vecinos</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statValue}>{(node.e_tta / 1000).toFixed(1)}K</span>
            <span style={styles.statLabel}>E_TTA</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statValue}>{node.packetsTx}</span>
            <span style={styles.statLabel}>TX</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statValue}>{node.packetsRx}</span>
            <span style={styles.statLabel}>RX</span>
          </div>
        </div>
        
        {/* Neighbors List */}
        {neighbors.length > 0 && (
          <div style={styles.neighborsSection}>
            <h3 style={styles.sectionTitle}>Nodos Resonantes</h3>
            <div style={styles.neighborsList}>
              {neighbors.map(n => (
                <div key={n.id} style={styles.neighborCard}>
                  <div style={{
                    ...styles.neighborDot,
                    background: LEVELS[getLevel(n.phi)].color,
                  }} />
                  <div style={styles.neighborInfo}>
                    <span style={styles.neighborId}>{n.id}</span>
                    <span style={styles.neighborMeta}>
                      Φ {n.phi.toFixed(2)} · {n.distance.toFixed(0)}m · {n.signal.toFixed(0)}dBm
                    </span>
                  </div>
                  <div style={{
                    ...styles.neighborPhi,
                    color: LEVELS[getLevel(n.phi)].color,
                  }}>
                    {(n.phi * 100).toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Actions */}
        <div style={styles.actionsRow}>
          <button style={styles.actionButton} onClick={sendPing} disabled={!isActive}>
            📡 Ping
          </button>
          <button style={styles.actionButton} onClick={() => addMessage('🔄 Escaneando...')} disabled={!isActive}>
            🔍 Escanear
          </button>
          <button style={styles.actionButton} onClick={() => setView('stats')}>
            📊 Stats
          </button>
        </div>
        
        {/* Message Log */}
        <div style={styles.messageLog}>
          {messages.map(m => (
            <div key={m.id} style={styles.message}>
              <span style={styles.messageTime}>{m.time}</span>
              <span style={styles.messageText}>{m.text}</span>
            </div>
          ))}
          {messages.length === 0 && (
            <div style={styles.messageEmpty}>
              Activa el nodo para comenzar a resonar
            </div>
          )}
        </div>
      </main>
      
      {/* Footer */}
      <footer style={styles.footer}>
        <div style={styles.footerInfo}>
          <span style={styles.nodeId}>{node.id}</span>
          <span style={styles.footerText}>
            D10Z-TTA · Ley Isis: ∂Φ/∂t = -αΦ + βΣwΦⱼ/|N|
          </span>
        </div>
      </footer>
      
      {/* CSS Animations */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 0.1; transform: scale(1.05); }
        }
        
        @keyframes glow {
          0%, 100% { filter: brightness(1); }
          50% { filter: brightness(1.2); }
        }
        
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
        
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: #0a0a0f;
          color: #f0f0f5;
          overflow-x: hidden;
        }
        
        ::-webkit-scrollbar {
          width: 4px;
        }
        
        ::-webkit-scrollbar-track {
          background: #1a1a25;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #333;
          border-radius: 2px;
        }
      `}</style>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ESTILOS
// ═══════════════════════════════════════════════════════════════════════════════

const styles = {
  container: {
    minHeight: '100vh',
    background: 'linear-gradient(180deg, #0a0a0f 0%, #12121a 100%)',
    display: 'flex',
    flexDirection: 'column',
  },
  
  // Header
  header: {
    padding: '16px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #2a2a3a',
    background: 'rgba(10, 10, 15, 0.9)',
    backdropFilter: 'blur(10px)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  
  logoIcon: {
    width: '40px',
    height: '40px',
    borderRadius: '50%',
    transition: 'all 0.3s ease',
  },
  
  logoText: {
    fontSize: '18px',
    fontWeight: '700',
    letterSpacing: '2px',
    margin: 0,
    color: '#f0f0f5',
  },
  
  logoSubtext: {
    fontSize: '10px',
    color: '#666',
    letterSpacing: '1px',
  },
  
  statusBadge: {
    padding: '8px 16px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: '600',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    border: '1px solid',
    transition: 'all 0.3s ease',
  },
  
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    transition: 'all 0.3s ease',
  },
  
  // Main
  main: {
    flex: 1,
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    maxWidth: '500px',
    margin: '0 auto',
    width: '100%',
  },
  
  // Resonance Visualizer
  resonanceContainer: {
    position: 'relative',
    background: '#12121a',
    borderRadius: '20px',
    padding: '20px',
    border: '1px solid #2a2a3a',
  },
  
  resonanceSvg: {
    width: '100%',
    height: 'auto',
    maxHeight: '300px',
  },
  
  phiDisplay: {
    position: 'absolute',
    bottom: '20px',
    left: '50%',
    transform: 'translateX(-50%)',
    textAlign: 'center',
  },
  
  phiValue: {
    fontSize: '32px',
    fontWeight: '700',
    fontFamily: 'monospace',
    display: 'block',
    transition: 'all 0.3s ease',
  },
  
  phiLabel: {
    fontSize: '12px',
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '2px',
  },
  
  // Button
  mainButton: {
    padding: '18px 40px',
    borderRadius: '30px',
    border: 'none',
    color: '#fff',
    fontSize: '16px',
    fontWeight: '700',
    letterSpacing: '2px',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
  },
  
  // Stats Grid
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '12px',
  },
  
  statCard: {
    background: '#1a1a25',
    borderRadius: '12px',
    padding: '16px 8px',
    textAlign: 'center',
    border: '1px solid #2a2a3a',
  },
  
  statValue: {
    fontSize: '20px',
    fontWeight: '700',
    fontFamily: 'monospace',
    color: '#f0f0f5',
    display: 'block',
  },
  
  statLabel: {
    fontSize: '10px',
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
  
  // Neighbors
  neighborsSection: {
    background: '#1a1a25',
    borderRadius: '16px',
    padding: '16px',
    border: '1px solid #2a2a3a',
  },
  
  sectionTitle: {
    fontSize: '12px',
    fontWeight: '600',
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    marginBottom: '12px',
  },
  
  neighborsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  
  neighborCard: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px',
    background: '#12121a',
    borderRadius: '10px',
  },
  
  neighborDot: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  
  neighborInfo: {
    flex: 1,
  },
  
  neighborId: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#f0f0f5',
    display: 'block',
  },
  
  neighborMeta: {
    fontSize: '11px',
    color: '#666',
  },
  
  neighborPhi: {
    fontSize: '16px',
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  
  // Actions
  actionsRow: {
    display: 'flex',
    gap: '10px',
  },
  
  actionButton: {
    flex: 1,
    padding: '12px',
    borderRadius: '10px',
    border: '1px solid #2a2a3a',
    background: '#1a1a25',
    color: '#f0f0f5',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  
  // Message Log
  messageLog: {
    background: '#0a0a0f',
    borderRadius: '12px',
    padding: '12px',
    border: '1px solid #2a2a3a',
    maxHeight: '150px',
    overflowY: 'auto',
  },
  
  message: {
    padding: '8px 0',
    borderBottom: '1px solid #1a1a25',
    display: 'flex',
    gap: '10px',
    fontSize: '12px',
  },
  
  messageTime: {
    color: '#444',
    fontFamily: 'monospace',
    flexShrink: 0,
  },
  
  messageText: {
    color: '#888',
  },
  
  messageEmpty: {
    textAlign: 'center',
    color: '#444',
    padding: '20px',
    fontSize: '13px',
  },
  
  // Footer
  footer: {
    padding: '16px 20px',
    borderTop: '1px solid #2a2a3a',
    background: 'rgba(10, 10, 15, 0.9)',
  },
  
  footerInfo: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  
  nodeId: {
    fontFamily: 'monospace',
    fontSize: '12px',
    color: '#666',
    background: '#1a1a25',
    padding: '4px 8px',
    borderRadius: '4px',
  },
  
  footerText: {
    fontSize: '10px',
    color: '#444',
  },
};
