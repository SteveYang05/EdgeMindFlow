import React, { useEffect, useState } from 'react'
import {
  fetchAgentStatus,
  fetchAgentExamples,
  submitAgentIntent,
} from '../api'
import AgentWorkflow from './AgentWorkflow'

const STATUS_LABEL = {
  satisfied: { text: 'Intent satisfied', cls: 'good' },
  recovered: { text: 'Recovered & satisfied', cls: 'good' },
  failed: { text: 'Not satisfied', cls: 'bad' },
  dry_run: { text: 'Dry Run', cls: '' },
  partial: { text: 'Partial validation', cls: 'warn' },
}

export default function AgentIntentPanel({ onRefresh }) {
  const [intentText, setIntentText] = useState('')
  const [dryRun, setDryRun] = useState(false)
  const [autoRecover, setAutoRecover] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [status, setStatus] = useState(null)
  const [examples, setExamples] = useState([])
  const [result, setResult] = useState(null)

  useEffect(() => {
    Promise.all([fetchAgentStatus(), fetchAgentExamples()])
      .then(([s, ex]) => {
        setStatus(s)
        setExamples(ex.examples || [])
      })
      .catch(e => setError(String(e.message || e)))
  }, [])

  const handleSubmit = async () => {
    if (!intentText.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await submitAgentIntent({
        intent_text: intentText.trim(),
        dry_run: dryRun,
        auto_recover: autoRecover,
      })
      setResult(res)
      if (onRefresh && !dryRun) onRefresh()
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Agent API call failed')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const parsed = result?.parsed_intent
  const plan = result?.plan
  const validation = result?.validation_result
  const finalStatus = result?.final_status
  const statusInfo = STATUS_LABEL[finalStatus] || { text: finalStatus, cls: '' }

  return (
    <div className="card agent-panel">
      <div className="card-title">
        AgentNet Network Intent
        {status && (
          <span style={{ fontSize: '0.68rem', color: '#1d9bf0' }}>
            {status.mode} · LLM {status.llm_enabled ? 'ON' : 'OFF'}
          </span>
        )}
      </div>

      <textarea
        className="agent-intent-input"
        rows={3}
        placeholder="Enter a natural-language network intent, e.g.: When cloud link degrades, prioritize smoke alerts under 100ms latency"
        value={intentText}
        onChange={e => setIntentText(e.target.value)}
      />

      <div className="agent-options">
        <label>
          <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />
          dry_run (plan only, no scenario/strategy switch)
        </label>
        <label>
          <input type="checkbox" checked={autoRecover} onChange={e => setAutoRecover(e.target.checked)} />
          auto_recover (self-heal on validation failure)
        </label>
      </div>

      <div className="btn-group">
        {examples.map(ex => (
          <button key={ex} type="button" className="btn" onClick={() => setIntentText(ex)}>
            {ex.length > 28 ? `${ex.slice(0, 28)}…` : ex}
          </button>
        ))}
      </div>

      <div className="btn-group" style={{ marginTop: 8 }}>
        <button type="button" className="btn active" disabled={loading} onClick={handleSubmit}>
          {loading ? 'Processing…' : 'Submit Intent'}
        </button>
      </div>

      {error && (
        <div className="agent-error">{error}</div>
      )}

      {result && (
        <div className="agent-result">
          <div className="grid grid-2" style={{ marginTop: 12, gap: 12 }}>
            <div className="agent-block">
              <div className="agent-block-title">Parsed Intent</div>
              <div>Type: {parsed?.intent_type}</div>
              <div>Tasks: {(parsed?.target_task_types || []).join(', ') || '—'}</div>
              <div>Scenario: {parsed?.target_scenario || plan?.recommended_scenario || '—'}</div>
              <div>Target latency: {parsed?.target_latency_ms ? `${parsed.target_latency_ms}ms` : '—'}</div>
            </div>
            <div className="agent-block">
              <div className="agent-block-title">Plan & Status</div>
              <div>Recommended scenario: {plan?.recommended_scenario || '—'}</div>
              <div>Recommended strategy: {plan?.recommended_strategy || '—'}</div>
              <div className={`stat-change ${statusInfo.cls}`}>
                Final status: {statusInfo.text}
              </div>
              <div style={{ fontSize: '0.72rem', marginTop: 6 }}>{plan?.rationale}</div>
            </div>
          </div>

          {validation && (
            <div className="agent-block" style={{ marginTop: 12 }}>
              <div className="agent-block-title">Validation</div>
              <div>{validation.summary}</div>
              <div style={{ fontSize: '0.68rem', color: '#71767b', marginTop: 4 }}>
                satisfied: {String(validation.satisfied)} · checks: {(validation.checks || []).length}
              </div>
            </div>
          )}

          {(result.recovery_actions || []).length > 0 && (
            <div className="agent-block" style={{ marginTop: 12 }}>
              <div className="agent-block-title">Recovery Actions</div>
              <pre className="agent-pre">{JSON.stringify(result.recovery_actions, null, 2)}</pre>
            </div>
          )}

          <div className="agent-block" style={{ marginTop: 12 }}>
            <div className="agent-block-title">Multi-Agent Workflow</div>
            <AgentWorkflow trace={result.workflow_trace || []} />
          </div>

          {result.explanation && (
            <p style={{ fontSize: '0.72rem', color: '#aaa', marginTop: 10 }}>{result.explanation}</p>
          )}
        </div>
      )}
    </div>
  )
}
