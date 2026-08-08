async function request(url, options) {
  const response = await fetch(url, options)
  const body = await response.json()
  if (!response.ok) throw new Error(body.detail || '请求失败')
  return body
}

export function createDragonTigerCollectionJob(startDate, latestDate) {
  return request('/api/v1/dragon-tiger/collection-jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ startDate: Number(startDate), latestDate: Number(latestDate) }),
  })
}

export function getDragonTigerCollectionJob(jobId) {
  return request(`/api/v1/dragon-tiger/collection-jobs/${encodeURIComponent(jobId)}`)
}

export function analyzeDragonTigerPremium(startDate, latestDate) {
  return request(`/api/v1/dragon-tiger/premium?start_date=${Number(startDate)}&latest_date=${Number(latestDate)}`)
}
