export async function fetchFundFlowDates(flowType, signal) {
  const response = await fetch(`/api/v1/fund-flow/${flowType}/dates`, { signal })
  if (!response.ok) throw new Error('获取日期失败')
  return (await response.json()).dates || []
}

export async function fetchFundFlowHistory(flowType, tradeDate, signal) {
  const response = await fetch(`/api/v1/fund-flow/${flowType}/history/${tradeDate}`, { signal })
  if (!response.ok) throw new Error('获取数据失败')
  const payload = await response.json()
  if (payload?.format !== 'matrix-v2') return payload
  return payload.times.map((time, index) => payload.boards.flatMap(board => {
    const point = board.points.find(item => item[0] === index)
    if (!point) return []
    return [{
      时间: time,
      板块名称: board.name,
      板块代码: board.code,
      龙头: point[2] || '',
      '资金净流入(亿)': point[1] || 0,
      资金净流入亿: point[1] || 0,
    }]
  }))
}
