import React from 'react'

const AGENT_ORDER = [
  'IntentAgent',
  'PlannerAgent',
  'PolicyAgent',
  'ToolLayer',
  'MonitorAgent',
  'ValidatorAgent',
  'RecoveryAgent',
  'Orchestrator',
]

const STATUS_COLOR = {
  ok: '#00ba7c',
  warn: '#ffad1f',
  error: '#f4212e',
  dry_run: '#1d9bf0',
}

export default function AgentWorkflow({ trace = [] }) {
  if (!trace.length) {
    return (
      <p style={{ color: '#71767b', fontSize: '0.78rem' }}>
        提交网络意图后，此处展示多智能体协同 workflow trace。
      </p>
    )
  }

  const sorted = [...trace].sort((a, b) => {
    const ia = AGENT_ORDER.indexOf(a.agent)
    const ib = AGENT_ORDER.indexOf(b.agent)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })

  return (
    <div className="agent-workflow">
      {sorted.map((step, idx) => (
        <div key={`${step.agent}-${idx}`} className="agent-step">
          <div className="agent-step-header">
            <span className="agent-name">{step.agent}</span>
            <span
              className="agent-status"
              style={{ color: STATUS_COLOR[step.status] || '#71767b' }}
            >
              {step.status}
            </span>
          </div>
          <div className="agent-io">
            <div><strong>Input:</strong> {step.input_summary || '—'}</div>
            <div><strong>Output:</strong> {step.output_summary || '—'}</div>
          </div>
          {idx < sorted.length - 1 && <div className="agent-arrow">↓</div>}
        </div>
      ))}
    </div>
  )
}
