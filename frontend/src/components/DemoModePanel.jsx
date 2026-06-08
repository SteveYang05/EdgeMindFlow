import React, { useState } from 'react'
import { demoStart, demoStop, demoTriggerSmoke, setScenario } from '../api'

const TOUR_SCENARIOS = [
  { id: 'normal', label: 'Normal', delay: 5000 },
  { id: 'cloud_delay', label: 'Cloud Delay↑', delay: 5000 },
  { id: 'edge_overload', label: 'Edge Overload', delay: 5000 },
  { id: 'emergency', label: 'Emergency', delay: 5000 },
]

export default function DemoModePanel({ onRefresh }) {
  const [demoActive, setDemoActive] = useState(false)
  const [touring, setTouring] = useState(false)
  const [tourStep, setTourStep] = useState('')
  const [msg, setMsg] = useState('')

  const handleStart = async () => {
    await demoStart()
    setDemoActive(true)
    setMsg('Demo Mode started (dynamic + normal)')
    onRefresh?.()
  }

  const handleStop = async () => {
    await demoStop()
    setDemoActive(false)
    setTouring(false)
    setTourStep('')
    setMsg('Demo Mode stopped')
    onRefresh?.()
  }

  const handleSmoke = async () => {
    const r = await demoTriggerSmoke()
    setMsg(`Smoke alert triggered → ${r.task?.decision || 'edge'}`)
    onRefresh?.()
  }

  const handleTour = async () => {
    if (touring) return
    setTouring(true)
    setDemoActive(true)
    for (const s of TOUR_SCENARIOS) {
      setTourStep(s.label)
      await setScenario(s.id)
      onRefresh?.()
      await new Promise(resolve => setTimeout(resolve, s.delay))
    }
    await setScenario('normal')
    setTourStep('')
    setTouring(false)
    setMsg('Scenario tour complete: normal → cloud_delay → edge_overload → emergency → normal')
    onRefresh?.()
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">
        Demo Mode
        {demoActive && <span className="status-badge healthy" style={{ fontSize: '0.68rem' }}>ACTIVE</span>}
      </div>
      <div className="btn-group">
        <button className={`btn ${demoActive ? 'active' : ''}`} onClick={handleStart} disabled={touring}>
          Start Demo
        </button>
        <button className="btn" onClick={handleStop} disabled={touring}>
          Stop Demo
        </button>
        <button className="btn danger" onClick={handleSmoke} disabled={touring}>
          Trigger Smoke Alert
        </button>
        <button className="btn" onClick={handleTour} disabled={touring}>
          {touring ? `Tour in progress: ${tourStep}` : 'Run Scenario Tour'}
        </button>
      </div>
      {msg && <p style={{ fontSize: '0.72rem', color: '#71767b', marginTop: 8 }}>{msg}</p>}
      <p style={{ fontSize: '0.68rem', color: '#555', marginTop: 4 }}>
        Tip: set TASK_INTERVAL_SEC=1 and restart the simulator for faster task flow
      </p>
    </div>
  )
}
