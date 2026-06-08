import React from 'react'
import ReactECharts from 'echarts-for-react'

export default function LoadChart({ edgeMetrics, cloudMetrics }) {
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['边缘 CPU', '边缘内存', '云端 CPU', '云端内存'], textStyle: { color: '#71767b' } },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: ['当前'],
      axisLabel: { color: '#71767b' },
      axisLine: { lineStyle: { color: '#2f3336' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#71767b', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#2f3336' } },
    },
    series: [
      { name: '边缘 CPU', type: 'bar', data: [edgeMetrics?.cpu_percent || 0], itemStyle: { color: '#1d9bf0' } },
      { name: '边缘内存', type: 'bar', data: [edgeMetrics?.memory_percent || 0], itemStyle: { color: '#00ba7c' } },
      { name: '云端 CPU', type: 'bar', data: [cloudMetrics?.cpu_percent || 0], itemStyle: { color: '#9b59b6' } },
      { name: '云端内存', type: 'bar', data: [cloudMetrics?.memory_percent || 0], itemStyle: { color: '#ffad1f' } },
    ],
  }
  return <ReactECharts option={option} style={{ height: '100%' }} />
}
