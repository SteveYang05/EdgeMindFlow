import React, { useState, useEffect, useCallback } from 'react'
import {
  fetchMetrics, fetchRecentTasks, fetchDevices,
  fetchAlerts, fetchScenario, fetchTopology, setScenario, setStrategy,
  fetchMlStatus, fetchRlStatus, fetchDigitalTwinStatus,
  DATA_SCOPES,
} from './api'
import LatencyChart from './charts/LatencyChart'
import LoadChart from './charts/LoadChart'
import StrategyChart from './charts/StrategyChart'
import DistributionChart from './charts/DistributionChart'
import NetworkTopology from './components/NetworkTopology'
import DemoModePanel from './components/DemoModePanel'
import DigitalTwinPanel from './components/DigitalTwinPanel'
import AgentIntentPanel from './components/AgentIntentPanel'
import StrategyScenarioIllustration from './components/StrategyScenarioIllustration'

const SCENARIOS = [
  { id: 'normal', label: 'Normal' },
  { id: 'cloud_delay', label: 'Cloud Delay↑' },
  { id: 'edge_overload', label: 'Edge Overload' },
  { id: 'emergency', label: 'Emergency' },
]

const STRATEGIES = [
  { id: 'local_only', label: 'Local-Only', desc: 'All tasks are processed locally.' },
  { id: 'cloud_only', label: 'Cloud-Only', desc: 'All tasks are sent to cloud.' },
  { id: 'edge_only', label: 'Edge-Only', desc: 'All tasks are processed at edge.' },
  { id: 'static_rule', label: 'Static-Rule', desc: 'Fixed task-type-based mapping.' },
  { id: 'dynamic', label: 'LATE-Offload', desc: 'State-aware LATE-Offload: latency-aware, task-priority enhanced, scenario-adaptive.' },
  { id: 'learned_late', label: 'LATE-Learn', desc: 'Oracle-labeled trace learning (CPU RandomForest); teacher mode available for ablation.' },
  { id: 'late_rl', label: 'LATE-RL', desc: 'Reinforcement-learning enhanced offloading policy for long-term latency, deadline, load, and safety reward optimization.' },
]

function StatusBadge({ status }) {
  const map = {
    healthy: { cls: 'healthy', text: 'Network Healthy' },
    cloud_link_degraded: { cls: 'warning', text: 'Cloud Link Degraded' },
    edge_overloaded: { cls: 'warning', text: 'Edge Overloaded' },
    emergency_active: { cls: 'danger', text: 'Emergency Active' },
  }
  const s = map[status] || map.healthy
  return (
    <span className={`status-badge ${s.cls}`}>
      <span className="status-dot" />{s.text}
    </span>
  )
}

export default function App() {
  const [metrics, setMetrics] = useState(null)
  const [tasks, setTasks] = useState([])
  const [devices, setDevices] = useState([])
  const [alerts, setAlerts] = useState([])
  const [topology, setTopology] = useState(null)
  const [scenario, setScenarioState] = useState(null)
  const [dataScope, setDataScope] = useState('recent_100')
  const [mlStatus, setMlStatus] = useState(null)
  const [rlStatus, setRlStatus] = useState(null)
  const [twinStatus, setTwinStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  const taskLimit = dataScope === 'recent_300' ? 300 : dataScope === 'all' ? 100 : 100

  const refresh = useCallback(async () => {
    try {
      const [m, t, d, a, s, topo, ml, rl, twin] = await Promise.all([
        fetchMetrics(dataScope), fetchRecentTasks(taskLimit), fetchDevices(),
        fetchAlerts(), fetchScenario(), fetchTopology(dataScope),
        fetchMlStatus(), fetchRlStatus(), fetchDigitalTwinStatus(),
      ])
      setMetrics(m)
      setTasks(t)
      setDevices(d)
      setAlerts(a)
      setScenarioState(s)
      setTopology(topo)
      setMlStatus(ml)
      setRlStatus(rl)
      setTwinStatus(twin)
    } catch (e) {
      console.error('Refresh failed:', e)
    } finally {
      setLoading(false)
    }
  }, [dataScope, taskLimit])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 3000)
    return () => clearInterval(timer)
  }, [refresh])

  const handleScenario = async (id) => {
    await setScenario(id)
    refresh()
  }

  const handleStrategy = async (id) => {
    await setStrategy(id)
    refresh()
  }

  const m = metrics || {}
  const edgeM = m.edge_metrics || {}
  const cloudM = m.cloud_metrics || {}

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>EdgeMindFlow Smart Campus System</h1>
          <p className="subtitle">Network-intent-driven multi-agent edge offloading with low-latency self-optimization (LATE + AgentNet)</p>
        </div>
        <StatusBadge status={m.network_status} />
      </header>

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Data View Scope</div>
          <select
            className="scope-select"
            value={dataScope}
            onChange={e => setDataScope(e.target.value)}
          >
            {DATA_SCOPES.map(s => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
          {m.scope_hint && (
            <p style={{ fontSize: '0.72rem', color: '#ffad1f', marginTop: 8 }}>{m.scope_hint}</p>
          )}
          <p style={{ fontSize: '0.68rem', color: '#555', marginTop: 4 }}>
            Current scope: {m.data_scope || dataScope} · Recommended: Recent 100 or Latest Experiment
          </p>
        </div>
        <DemoModePanel onRefresh={refresh} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <AgentIntentPanel onRefresh={refresh} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <DigitalTwinPanel twin={twinStatus} />
      </div>

      <div className="grid grid-5" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Avg Task Latency</div>
          <div className="stat-value">{m.avg_latency_ms?.toFixed(1) || '0'}<span className="stat-unit">ms</span></div>
          <div className="stat-change">P95: {m.p95_latency_ms?.toFixed(1) || '0'} ms</div>
        </div>
        <div className="card">
          <div className="card-title">Total Tasks</div>
          <div className="stat-value">{m.total_tasks || 0}</div>
          <div className="stat-change good">Success rate {m.success_rate?.toFixed(1) || 100}%</div>
        </div>
        <div className="card">
          <div className="card-title">QoS Satisfaction</div>
          <div className="stat-value">{(m.qos_satisfaction_rate || 0).toFixed(1)}<span className="stat-unit">%</span></div>
          <div className="stat-change">Deadline + Urgent + Success</div>
        </div>
        <div className="card">
          <div className="card-title">Deadline Violation Rate</div>
          <div className="stat-value">{(m.deadline_violation_rate || 0).toFixed(1)}<span className="stat-unit">%</span></div>
          <div className="stat-change">Emergency avg latency {m.emergency_avg_latency_ms?.toFixed(0) || 0} ms</div>
        </div>
        <div className="card">
          <div className="card-title">Alerts</div>
          <div className="stat-value" style={{ color: m.alert_count > 0 ? '#f4212e' : '#e7e9ea' }}>
            {m.alert_count || 0}
          </div>
          <div className="stat-change">Strategy: {m.current_strategy === 'dynamic' ? 'LATE-Offload' : (m.current_strategy || 'dynamic')}</div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">
            Experiment Scenario
            <span style={{ color: '#1d9bf0' }}>{scenario?.scenario || m.current_scenario}</span>
          </div>
          <p style={{ fontSize: '0.78rem', color: '#71767b', marginBottom: 8 }}>
            {scenario?.description || 'Normal network, dynamic offloading'}
          </p>
          <div className="btn-group">
            {SCENARIOS.map(s => (
              <button
                key={s.id}
                className={`btn ${(m.current_scenario === s.id) ? 'active' : ''} ${s.id === 'emergency' ? 'danger' : ''}`}
                onClick={() => handleScenario(s.id)}
              >{s.label}</button>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-title">Offloading Strategy</div>
          <div className="btn-group">
            {STRATEGIES.map(s => (
              <button
                key={s.id}
                className={`btn ${(m.current_strategy === s.id) ? 'active' : ''} ${s.id === 'dynamic' ? '' : ''}`}
                onClick={() => handleStrategy(s.id)}
              >{s.label}</button>
            ))}
          </div>
          <div style={{ marginTop: 10, fontSize: '0.68rem', color: '#71767b', lineHeight: 1.6 }}>
            {STRATEGIES.map(s => (
              <div key={s.id}><strong>{s.label}</strong>: {s.desc}</div>
            ))}
          </div>
          <p style={{ fontSize: '0.72rem', color: '#71767b', marginTop: 10 }}>
            Network delay: {edgeM.network_delay_ms?.toFixed(0) || 0} ms |
            Bandwidth usage: {edgeM.bandwidth_usage_mbps?.toFixed(1) || 0} Mbps
          </p>
          {mlStatus && (
            <div style={{ marginTop: 10, padding: 8, background: '#16181c', borderRadius: 8, fontSize: '0.68rem', color: '#aaa' }}>
              <strong style={{ color: '#e7e9ea' }}>Learned Policy (LATE-Learn)</strong>
              <div>label source: {mlStatus.label_source || mlStatus.meta?.label_source || 'N/A'}</div>
              <div>oracle agreement: {mlStatus.oracle_agreement ?? mlStatus.meta?.oracle_agreement ?? 'N/A'}</div>
              <div>avg regret: {mlStatus.avg_regret ?? mlStatus.meta?.avg_regret ?? 'N/A'}</div>
              <div>public trace: {String(mlStatus.public_trace_used ?? mlStatus.meta?.public_trace_used ?? 'N/A')}</div>
              <div>fallback: {String(mlStatus.fallback_used ?? mlStatus.meta?.fallback_used ?? 'N/A')}</div>
            </div>
          )}
          {rlStatus && (
            <div style={{ marginTop: 10, padding: 8, background: '#16181c', borderRadius: 8, fontSize: '0.68rem', color: '#aaa' }}>
              <strong style={{ color: '#e7e9ea' }}>RL Policy (LATE-RL)</strong>
              <div>model available: {String(rlStatus.late_rl_available ?? false)}</div>
              <div>episodes: {rlStatus.episodes ?? 'N/A'}</div>
              <div>avg_reward_last_10: {rlStatus.avg_reward_last_10 ?? 'N/A'}</div>
              <div>epsilon_final: {rlStatus.epsilon_final ?? 'N/A'}</div>
              <div>fallback enabled: {String(rlStatus.fallback_enabled ?? true)}</div>
              {!rlStatus.late_rl_available && (
                <div style={{ color: '#ffad1f' }}>LATE-RL fallback enabled.</div>
              )}
            </div>
          )}
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <StrategyScenarioIllustration
          scenarioId={m.current_scenario || scenario?.scenario || 'normal'}
          strategyId={m.current_strategy || 'dynamic'}
        />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">Network Topology & Task Flow</div>
        <NetworkTopology topology={topology} metrics={{
          local: m.local_task_count,
          edge: m.edge_task_count,
          cloud: m.cloud_task_count,
        }} />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Task Completion Latency</div>
          <div className="chart-container"><LatencyChart tasks={tasks} /></div>
        </div>
        <div className="card">
          <div className="card-title">Edge / Cloud Node Load</div>
          <div className="chart-container"><LoadChart edgeMetrics={edgeM} cloudMetrics={cloudM} /></div>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">Live Task Stream & Offload Decisions</div>
          <div className="task-list">
            {loading && <p style={{ color: '#71767b' }}>Loading...</p>}
            {tasks.map(t => (
              <div key={t.task_id} className="task-item">
                <div className="task-header">
                  <span><strong>{t.device_id}</strong> · {t.task_type}</span>
                  <span>
                    <span className={`badge ${t.execution_location}`}>{t.execution_location}</span>
                    {' '}
                    <span className={`badge ${t.priority}`}>{t.priority}</span>
                  </span>
                </div>
                <div className="task-id">{t.task_id}</div>
                <div>
                  Latency: <strong>{t.total_latency_ms?.toFixed(0)}</strong> ms
                  <span className={t.deadline_met ? 'deadline-ok' : ' deadline-violation'}>
                    {t.deadline_met ? ' ✓' : ' ✗ deadline missed'}
                  </span>
                </div>
                <div className="reason-text">{t.reason}</div>
              </div>
            ))}
            {!loading && tasks.length === 0 && (
              <p style={{ color: '#71767b', padding: 20 }}>Waiting for tasks... ensure the simulator is running</p>
            )}
          </div>
        </div>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">Task Distribution</div>
            <div className="chart-container" style={{ height: 200 }}>
              <DistributionChart
                edgeCount={m.edge_task_count}
                cloudCount={m.cloud_task_count}
                localCount={m.local_task_count}
              />
            </div>
          </div>
        <div className="card">
          <div className="card-title">Alert Events</div>
          <div className="stat-change" style={{ marginBottom: 8 }}>
            Security {m.security_alert_count || 0} · Performance {m.performance_warning_count || 0} · System {m.system_event_count || 0}
          </div>
          {alerts.length === 0 && <p style={{ color: '#71767b', fontSize: '0.8rem' }}>No alerts</p>}
          {['security', 'performance', 'system'].map(cat => {
            const items = alerts.filter(a => (a.alert_category || 'system') === cat)
            if (!items.length) return null
            const labels = { security: '🔴 Security', performance: '🟡 Performance', system: '🔵 System' }
            return (
              <div key={cat} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: '0.72rem', color: '#71767b', marginBottom: 4 }}>{labels[cat]}</div>
                {items.slice(0, 5).map(a => (
                  <div key={a.id} className={`alert-item alert-${a.alert_category || 'system'}`}>
                    <div>
                      <span className={`badge ${a.alert_level === 'critical' ? 'high' : a.alert_level === 'warning' ? 'medium' : 'low'}`}>
                        {a.alert_type || a.alert_level}
                      </span>
                      {' '}{a.message}
                    </div>
                    <div style={{ color: '#71767b', fontSize: '0.7rem', marginTop: 4 }}>{a.timestamp}</div>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">Strategy Latency Comparison</div>
          <div className="chart-container"><StrategyChart comparison={m.strategy_comparison} /></div>
        </div>
        <div className="card">
          <div className="card-title">IoT Device List</div>
          <div className="device-grid">
            {devices.map(d => (
              <div key={d.device_id} className="device-card">
                <div className="name">{d.device_id}</div>
                <div className="type">{d.type} · {d.task_types?.join(', ')}</div>
                <div className="online">● {d.status}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
