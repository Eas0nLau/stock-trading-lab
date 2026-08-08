import assert from 'node:assert/strict'
import test from 'node:test'

import { normalizePayload } from './normalizers.js'


test('normalizes nested snake case keys and preserves values', () => {
  const payload = {
    status: 'success',
    index_cycle: {
      trade_date: 20260806,
      market_breadth: { advancing_count: 3000, turnover_ratio: null },
      recent_trend: [{ trade_date: 20260805 }, null, { trade_date: 20260806 }],
    },
  }

  const result = normalizePayload(payload)

  assert.equal(result.indexCycle.tradeDate, 20260806)
  assert.equal(result.indexCycle.marketBreadth.advancingCount, 3000)
  assert.equal(result.indexCycle.marketBreadth.turnoverRatio, null)
  assert.equal(result.indexCycle.recentTrend[1], null)
})
