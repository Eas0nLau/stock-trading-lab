import { matrixToFundFlowRows, normalizeFundFlowEvent } from './normalizers.js'

export async function fetchFundFlowDates(flowType, signal) {
  const response = await fetch(`/api/v1/fund-flow/${flowType}/dates`, { signal })
  if (!response.ok) throw new Error('获取日期失败')
  return (await response.json()).dates || []
}

export async function fetchFundFlowHistory(flowType, tradeDate, signal) {
  const response = await fetch(`/api/v1/fund-flow/${flowType}/history/${tradeDate}`, { signal })
  if (!response.ok) throw new Error('获取数据失败')
  const payload = await response.json()
  return matrixToFundFlowRows(payload)
}

export function openFundFlowStream(onEvent) {
  const stream = new EventSource('/api/v1/fund-flow/stream')
  stream.onmessage = event => {
    const payload = normalizeFundFlowEvent(JSON.parse(event.data))
    if (payload) onEvent(payload)
  }
  return stream
}
