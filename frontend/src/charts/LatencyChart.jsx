import React from 'react'
import ReactECharts from 'echarts-for-react'

export default function LatencyChart({ tasks }) {
  const data = (tasks || []).slice(0, 20).reverse().map((t, i) => ({
    name: t.task_id?.slice(-8) || i,
    value: t.total_latency_ms || 0,
    itemStyle: { color: t.deadline_met ? '#00ba7c' : '#f4212e' },
  }))

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisLabel: { color: '#71767b', fontSize: 10, rotate: 30 },
      axisLine: { lineStyle: { color: '#2f3336' } },
    },
    yAxis: {
      type: 'value',
      name: 'ms',
      axisLabel: { color: '#71767b' },
      splitLine: { lineStyle: { color: '#2f3336' } },
    },
    series: [{
      type: 'line',
      smooth: true,
      data: data.map(d => d.value),
      areaStyle: { color: 'rgba(29,155,240,0.15)' },
      lineStyle: { color: '#1d9bf0', width: 2 },
      itemStyle: { color: '#1d9bf0' },
    }],
  }

  return <ReactECharts option={option} style={{ height: '100%' }} />
}
