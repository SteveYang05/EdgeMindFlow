import React, { useState } from 'react'

const STRATEGY_IMAGES = {
  local_only: { file: 'strategy_local_only.png', title: '本地执行 Local-Only', caption: '全部任务在设备本地处理' },
  cloud_only: { file: 'strategy_cloud_only.png', title: '全上云 Cloud-Only', caption: '所有任务集中云端处理' },
  edge_only: { file: 'strategy_edge_only.png', title: '全边缘 Edge-Only', caption: '所有任务在边缘节点执行' },
  static_rule: { file: 'strategy_static_rule.png', title: '静态规则 Static-Rule', caption: '按任务类型固定映射' },
  dynamic: { file: 'strategy_late_offload.png', title: 'LATE-Offload 动态卸载', caption: '多目标代价评分 + 场景自适应' },
  learned_late: { file: 'strategy_late_learn.png', title: 'LATE-Learn 学习策略', caption: 'Oracle 监督学习，接近最优映射' },
  late_rl: { file: 'strategy_late_rl.png', title: 'LATE-RL 强化学习', caption: '长期 Reward 优化增强模块' },
}

const SCENARIO_IMAGES = {
  normal: { file: 'scenario_normal.png', title: '场景：网络正常 Normal', caption: '默认时延与负载，适合基线对比' },
  cloud_delay: { file: 'scenario_cloud_delay.png', title: '场景：云端延迟 Cloud Delay', caption: '云边链路劣化，不宜全上云' },
  edge_overload: { file: 'scenario_edge_overload.png', title: '场景：边缘过载 Edge Overload', caption: '边缘负载过高，安全任务仍优先' },
  emergency: { file: 'scenario_emergency.png', title: '场景：紧急告警 Emergency', caption: '安全关键任务低时延响应' },
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
        <div className="illustration-fallback">配图加载失败：{meta.file}</div>
      )}
    </div>
  )
}

export default function StrategyScenarioIllustration({ scenarioId, strategyId }) {
  const scenario = SCENARIO_IMAGES[scenarioId] || SCENARIO_IMAGES.normal
  const strategy = STRATEGY_IMAGES[strategyId] || STRATEGY_IMAGES.dynamic

  return (
    <div className="card illustration-panel">
      <div className="card-title">策略 / 场景示意图（切换按钮同步更新）</div>
      <div className="illustration-grid">
        <IllustrationCard
          meta={scenario}
          alt={`场景 ${scenarioId}`}
          imageKey={`scenario-${scenarioId}`}
        />
        <IllustrationCard
          meta={strategy}
          alt={`策略 ${strategyId}`}
          imageKey={`strategy-${strategyId}`}
        />
      </div>
    </div>
  )
}
