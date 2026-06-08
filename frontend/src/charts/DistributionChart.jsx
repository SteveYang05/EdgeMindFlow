import React from 'react'
import ReactECharts from 'echarts-for-react'

export default function DistributionChart({ edgeCount, cloudCount, localCount }) {
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#71767b' } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: [
        { value: edgeCount, name: '边缘', itemStyle: { color: '#1d9bf0' } },
        { value: cloudCount, name: '云端', itemStyle: { color: '#9b59b6' } },
        { value: localCount, name: '本地', itemStyle: { color: '#00ba7c' } },
      ],
      label: { color: '#e7e9ea' },
    }],
  }
  return <ReactECharts option={option} style={{ height: '100%' }} />
}
