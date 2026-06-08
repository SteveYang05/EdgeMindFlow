import React, { useState } from 'react'

const STRATEGY_IMAGES = {
  local_only: { file: 'strategy_local_only.png', title: 'Local-Only', caption: 'All tasks processed on device' },
  cloud_only: { file: 'strategy_cloud_only.png', title: 'Cloud-Only', caption: 'All tasks offloaded to cloud' },
  edge_only: { file: 'strategy_edge_only.png', title: 'Edge-Only', caption: 'All tasks executed at edge nodes' },
  static_rule: { file: 'strategy_static_rule.png', title: 'Static-Rule', caption: 'Fixed mapping by task type' },
  dynamic: { file: 'strategy_late_offload.png', title: 'LATE-Offload', caption: 'Multi-objective cost scoring + scenario adaptation' },
  learned_late: { file: 'strategy_late_learn.png', title: 'LATE-Learn', caption: 'Oracle-supervised learning, near-optimal mapping' },
  late_rl: { file: 'strategy_late_rl.png', title: 'LATE-RL', caption: 'Long-term reward optimization module' },
}

const SCENARIO_IMAGES = {
  normal: { file: 'scenario_normal.png', title: 'Scenario: Normal', caption: 'Default latency and load; baseline comparison' },
  cloud_delay: { file: 'scenario_cloud_delay.png', title: 'Scenario: Cloud Delay', caption: 'Degraded cloud link; avoid cloud-only' },
  edge_overload: { file: 'scenario_edge_overload.png', title: 'Scenario: Edge Overload', caption: 'High edge load; safety tasks still prioritized' },
  emergency: { file: 'scenario_emergency.png', title: 'Scenario: Emergency', caption: 'Low-latency response for safety-critical tasks' },
}

function IllustrationCard({ meta, alt, imageKey }) {
  const [failed, setFailed] = useState(false)
  if (!meta) return null

  const src = `/api/images/${meta.file}`

  return (
    <div className="illustration-card">
      <div className="illustration-title">{meta.title}</div>
      <div className="illustration-caption">{meta.caption}</div>
      {!failed ? (
        <img
          key={imageKey}
          className="illustration-img"
          src={src}
          alt={alt || meta.title}
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="illustration-fallback">Failed to load: {meta.file}</div>
      )}
    </div>
  )
}

export default function StrategyScenarioIllustration({ scenarioId, strategyId }) {
  const scenario = SCENARIO_IMAGES[scenarioId] || SCENARIO_IMAGES.normal
  const strategy = STRATEGY_IMAGES[strategyId] || STRATEGY_IMAGES.dynamic

  return (
    <div className="card illustration-panel">
      <div className="card-title">Strategy / Scenario Illustrations (synced with controls)</div>
      <div className="illustration-grid">
        <IllustrationCard
          meta={scenario}
          alt={`Scenario ${scenarioId}`}
          imageKey={`scenario-${scenarioId}`}
        />
        <IllustrationCard
          meta={strategy}
          alt={`Strategy ${strategyId}`}
          imageKey={`strategy-${strategyId}`}
        />
      </div>
    </div>
  )
}
