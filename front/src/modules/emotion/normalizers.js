function toCamelCase(value) {
  return value.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

export function normalizePayload(value) {
  if (Array.isArray(value)) return value.map(normalizePayload)
  if (value === null || typeof value !== 'object') return value

  return Object.fromEntries(
    Object.entries(value).map(([key, nested]) => [toCamelCase(key), normalizePayload(nested)]),
  )
}
