import React from 'react'
import ReactECharts from 'echarts-for-react'

const STRATEGIES = ['local_only', 'cloud_only', 'edge_only', 'static_rule', 'dynamic', 'learned_late', 'late_rl']
const LABELS = {
  local_only: 'Local-Only',
  cloud_only: 'Cloud-Only',
  edge_only: 'Edge-Only',
  static_rule: 'Static-Rule',
  dynamic: 'LATE-Offload',
  learned_late: 'LATE-Learn',
  late_rl: 'LATE-RL',
}
const COLORS = ['#00ba7c', '#9b59b6', '#1d9bf0', '#ffad1f', '#e74c3c', '#17a589', '#f39c12']

export default function StrategyChart({ comparison }) {
  const data = STRATEGIES.map(s => comparison?.[s]?.avg_latency_ms || 0)

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 30, bottom: 50 },
    xAxis: {
      type: 'category',
      data: STRATEGIES.map(s => LABELS[s]),
      axisLabel: { color: '#71767b', rotate: 20, fontSize: 10 },
      axisLine: { lineStyle: { color: '#2f3336' } },
    },
    yAxis: {
      type: 'value',
      name: 'Avg Latency (ms)',
      axisLabel: { color: '#71767b' },
      splitLine: { lineStyle: { color: '#2f3336' } },
    },
    series: [{
      type: 'bar',
      data: data.map((v, i) => ({
        value: v,
        itemStyle: { color: COLORS[i] },
      })),
      barWidth: '55%',
    }],
  }
  return <ReactECharts option={option} style={{ height: '100%' }} />
}
