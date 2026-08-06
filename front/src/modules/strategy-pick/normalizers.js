export function normalizeStrategy(value) {
  if (!value || typeof value !== 'object') return null
  return {
    id: value.id || '', name: value.name || '', pageUrl: value.pageUrl || '',
    listenTargets: Array.isArray(value.listenTargets) ? value.listenTargets : [],
    monitorPeriods: Array.isArray(value.monitorPeriods) ? value.monitorPeriods : [],
    monitorIntervalSeconds: Number(value.monitorIntervalSeconds || 60),
    enabled: value.enabled !== false, createdAt: value.createdAt || '', updatedAt: value.updatedAt || '',
  }
}

export function normalizeStock(value) {
  if (!value || typeof value !== 'object') return null
  return { ...value, code: value.code || '', name: value.name || '', market: value.market || '', fields: value.fields && typeof value.fields === 'object' ? value.fields : {}, selectedDate: value.selectedDate || '', selectedAt: value.selectedAt || '', selectedClock: value.selectedClock || '', lastCollectedAt: value.lastCollectedAt || '' }
}

export function normalizeEvent(value) {
  if (!value || typeof value !== 'object') return null
  return { ...value, eventId: value.eventId || value.event_id || '', strategyId: value.strategyId || '', strategyName: value.strategyName || '', selectedDate: value.selectedDate || '', selectedAt: value.selectedAt || '', selectedClock: value.selectedClock || '', code: value.code || '', name: value.name || '', market: value.market || '', fields: value.fields && typeof value.fields === 'object' ? value.fields : {} }
}

export function normalizeSnapshot(value) {
  if (!value || typeof value !== 'object') return {}
  return { ...value, strategyId: value.strategyId || '', strategyName: value.strategyName || '', collectedDate: value.collectedDate || '', collectedTime: value.collectedTime || '', status: value.status || '', errorMessage: value.errorMessage || '', stocks: Array.isArray(value.stocks) ? value.stocks.map(normalizeStock).filter(Boolean) : [], addedStocks: Array.isArray(value.addedStocks) ? value.addedStocks.map(normalizeEvent).filter(Boolean) : [], removedStocks: Array.isArray(value.removedStocks) ? value.removedStocks.map(normalizeEvent).filter(Boolean) : [] }
}

export function normalizeStrategyEvent(value) {
  if (!value || typeof value !== 'object') return null
  return { type: value.type || '', strategyId: value.strategyId || '', strategyName: value.strategyName || '', collectedDate: value.collectedDate || '', collectedTime: value.collectedTime || '', status: value.status || '', stockCount: Number(value.stockCount || 0), addedCount: Number(value.addedCount || 0), addedStocks: Array.isArray(value.addedStocks) ? value.addedStocks.map(normalizeEvent).filter(Boolean) : [], removedCount: Number(value.removedCount || 0), removedStocks: Array.isArray(value.removedStocks) ? value.removedStocks.map(normalizeEvent).filter(Boolean) : [] }
}
