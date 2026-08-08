import { normalizeEvent, normalizeSnapshot, normalizeStrategy, normalizeStrategyEvent } from './normalizers.js'

async function request(path, options = {}) {
  const response = await fetch(`/api/v1/strategy-pick${path}`, options)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try { message = (await response.json())?.detail || message } catch (_) {}
    throw new Error(message)
  }
  return response.json()
}

export async function fetchStrategyPickStrategies() {
  const data = await request('/strategies')
  return Array.isArray(data) ? data.map(normalizeStrategy).filter(Boolean) : []
}
export async function fetchStrategyPickLatest(strategyId) { return normalizeSnapshot(await request(`/strategies/${strategyId}/latest`)) }
export async function fetchStrategyPickDates(strategyId) { const data = await request(`/strategies/${strategyId}/dates`); return Array.isArray(data) ? data : [] }
export async function fetchStrategyPickDateData(strategyId, date) { const [events, history] = await Promise.all([request(`/strategies/${strategyId}/events/${date}`), request(`/strategies/${strategyId}/history/${date}`)]); return { events: (Array.isArray(events) ? events : []).map(normalizeEvent).filter(Boolean), history: (Array.isArray(history) ? history : []).map(normalizeSnapshot) } }
export async function refreshStrategyPick(strategyId) { return normalizeSnapshot(await request(`/strategies/${strategyId}/refresh`, { method: 'POST' })) }
export async function createStrategyPick(payload) { return normalizeStrategy(await request('/strategies', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })) }
export async function updateStrategyPick(strategyId, payload) { return normalizeStrategy(await request(`/strategies/${strategyId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })) }
export async function deleteStrategyPick(strategyId) { return request(`/strategies/${strategyId}`, { method: 'DELETE' }) }
export function openStrategyPickStream(onEvent) { const stream = new EventSource('/api/v1/strategy-pick/stream'); stream.onmessage = event => { const payload = normalizeStrategyEvent(JSON.parse(event.data)); if (payload) onEvent(payload) }; return stream }
