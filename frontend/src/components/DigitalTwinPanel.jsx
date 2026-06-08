import React from 'react'

export default function DigitalTwinPanel({ twin }) {
  if (!twin) {
    return (
      <div className="card">
        <div className="card-title">Digital Twin Smart Park</div>
        <p style={{ fontSize: '0.72rem', color: '#71767b' }}>Loading twin status...</p>
      </div>
    )
  }

  const dt = twin.device_twin || {}
  const nt = twin.network_twin || {}
  const et = twin.edge_twin || {}
  const ct = twin.cloud_twin || {}
  const wt = twin.workload_twin || {}

  const row = (label, value) => (
    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', marginBottom: 4 }}>
      <span style={{ color: '#71767b' }}>{label}</span>
      <span style={{ color: '#e7e9ea' }}>{value}</span>
    </div>
  )

  return (
    <div className="card">
      <div className="card-title">Digital Twin Smart Park</div>
      <p style={{ fontSize: '0.68rem', color: '#71767b', marginBottom: 10 }}>
        IoT simulator + topology + scenario + metrics form the smart-campus digital twin lab
      </p>
      <div className="grid grid-2" style={{ gap: 8 }}>
        <div style={{ background: '#16181c', padding: 8, borderRadius: 8 }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, marginBottom: 6 }}>Device Twin</div>
          {row('devices', dt.device_count)}
          {row('types', (dt.device_types || []).join(', '))}
        </div>
        <div style={{ background: '#16181c', padding: 8, borderRadius: 8 }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, marginBottom: 6 }}>Network Twin</div>
          {row('cloud delay', `${nt.current_cloud_delay_ms ?? 0} ms`)}
          {row('bandwidth', `${nt.bandwidth_mbps ?? 0} Mbps`)}
        </div>
        <div style={{ background: '#16181c', padding: 8, borderRadius: 8 }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, marginBottom: 6 }}>Edge Twin</div>
          {row('CPU', `${et.cpu_percent ?? 0}%`)}
          {row('queue', et.queue_depth ?? 0)}
        </div>
        <div style={{ background: '#16181c', padding: 8, borderRadius: 8 }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, marginBottom: 6 }}>Cloud Twin</div>
          {row('CPU', `${ct.cpu_percent ?? 0}%`)}
          {row('delay', `${ct.cloud_delay_ms ?? 0} ms`)}
        </div>
      </div>
      <div style={{ marginTop: 8, background: '#16181c', padding: 8, borderRadius: 8 }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 600, marginBottom: 6 }}>Workload Twin</div>
        {row('recent tasks', wt.recent_task_count ?? 0)}
        {row('scenario', wt.scenario ?? 'normal')}
        {row('strategy', wt.current_strategy ?? 'dynamic')}
      </div>
    </div>
  )
}
