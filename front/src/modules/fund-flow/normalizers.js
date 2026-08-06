export function normalizeFundFlowRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows.flatMap(snapshot => {
    const items = Array.isArray(snapshot) ? snapshot : [snapshot]
    return items.flatMap(item => {
      if (!item?.board_name || !item?.time) return []
      return [{
        boardName: item.board_name,
        boardCode: item.board_code || '',
        time: item.time,
        netInflow100m: Number(item.net_inflow_100m ?? 0),
        leader: item.leader || '',
      }]
    })
  })
}

export function matrixToFundFlowRows(payload) {
  if (payload?.format !== 'matrix-v2') return normalizeFundFlowRows(payload)
  const times = Array.isArray(payload.times) ? payload.times : []
  return (Array.isArray(payload.boards) ? payload.boards : []).flatMap(board =>
    (Array.isArray(board.points) ? board.points : []).flatMap(point => {
      const time = times[point[0]]
      if (!time) return []
      return [{
        boardName: board.name,
        boardCode: board.code || '',
        time,
        netInflow100m: Number(point[1] ?? 0),
        leader: point[2] || '',
      }]
    })
  )
}

export function normalizeFundFlowEvent(payload) {
  if (!payload || typeof payload !== 'object') return null
  return {
    type: payload.type || '',
    flowType: payload.flow_type || '',
    tradeDate: payload.trade_date || '',
    collectedAt: payload.collected_at || '',
    recordCount: Number(payload.record_count ?? 0),
  }
}
