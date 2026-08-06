import { normalizePayload } from './normalizers.js'


async function fetchEmotionPayload(url, options = {}) {
  const response = await fetch(url, options)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)

  const payload = normalizePayload(await response.json())
  if (payload?.status !== 'success') {
    throw new Error(payload?.errorMessage || 'Emotion data is unavailable')
  }
  return payload
}

export function fetchIndexEmotion(options = {}) {
  return fetchEmotionPayload('/api/v1/emotion/current', options)
}

export function fetchHotBoardEmotion(days = 30, options = {}) {
  const boundedDays = Math.max(5, Math.min(60, Number(days) || 30))
  return fetchEmotionPayload(`/api/v1/emotion/hot-boards?days=${boundedDays}`, options)
}
