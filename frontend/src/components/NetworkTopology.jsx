import React from 'react'

const DEVICE_ICONS = {
  temperature_sensor_01: '🌡️',
  humidity_sensor_01: '💧',
  smoke_sensor_01: '🔥',
  camera_01: '📷',
  access_control_01: '🚪',
}

function FlowPath({ active, color, label }) {
  return (
    <div className={`topo-path ${active ? 'active' : ''}`} style={{ '--path-color': color }}>
      <div className="topo-path-line" />
      <span className="topo-path-label">{label}</span>
    </div>
  )
}

export default function NetworkTopology({ topology, metrics }) {
  const flow = topology?.recent_flow || metrics || { local: 0, edge: 0, cloud: 0 }
  const latest = topology?.latest_task
  const decision = latest?.decision || 'edge'
  const devices = topology?.devices || []
  const edge = topology?.edge || {}
  const cloud = topology?.cloud || {}

  const highlightLocal = decision === 'local'
  const highlightEdge = decision === 'edge'
  const highlightCloud = decision === 'cloud'

  return (
    <div className="topo-container">
      <div className="topo-layer">
        <div className="topo-layer-title">IoT Device Layer</div>
        <div className="topo-devices">
          {devices.map(d => (
            <div
              key={d.device_id}
              className={`topo-node device ${latest?.device_id === d.device_id ? 'highlight' : ''}`}
            >
              <span className="topo-icon">{DEVICE_ICONS[d.device_id] || '📡'}</span>
              <span className="topo-name">{d.device_id.replace(/_01$/, '')}</span>
              {highlightLocal && latest?.device_id === d.device_id && (
                <span className="topo-badge local">LOCAL</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="topo-flow-row">
        <FlowPath active={highlightEdge || highlightCloud} color="#1d9bf0" label={`edge: ${flow.edge || 0}`} />
        <FlowPath active={highlightCloud} color="#9b59b6" label={`cloud: ${flow.cloud || 0}`} />
        <FlowPath active={highlightLocal} color="#00ba7c" label={`local: ${flow.local || 0}`} />
      </div>

      <div className="topo-layer topo-nodes-row">
        <div className={`topo-node edge-node ${highlightEdge || highlightCloud ? 'highlight' : ''}`}>
          <div className="topo-node-title">⚡ Edge Server</div>
          <div className="topo-node-stat">CPU {edge.cpu_percent?.toFixed(0) || 0}%</div>
          <div className="topo-node-stat">Delay {edge.network_delay_ms?.toFixed(0) || 0} ms</div>
          {highlightEdge && <span className="topo-badge edge">PROCESSING</span>}
        </div>

        <div className={`topo-arrow ${highlightCloud ? 'active' : ''}`}>→</div>

        <div className={`topo-node cloud-node ${highlightCloud ? 'highlight' : ''}`}>
          <div className="topo-node-title">☁️ Cloud Server</div>
          <div className="topo-node-stat">CPU {cloud.cpu_percent?.toFixed(0) || 0}%</div>
          <div className="topo-node-stat">Delay {cloud.network_delay_ms?.toFixed(0) || 0} ms</div>
          {highlightCloud && <span className="topo-badge cloud">PROCESSING</span>}
        </div>
      </div>

      {latest && (
        <div className="topo-latest">
          Latest task: <strong>{latest.device_id}</strong> → <span className={`badge ${latest.decision}`}>{latest.decision}</span>
          <span className="topo-latest-type"> ({latest.task_type})</span>
        </div>
      )}
    </div>
  )
}
