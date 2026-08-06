import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeSnapshot, normalizeStrategyEvent } from './normalizers.js'

test('normalizes strategy snapshot and nested stock/event fields', () => {
  const result = normalizeSnapshot({ strategyId: 'eastmoney_1', stocks: [{ code: '600000', fields: { 涨跌幅: '3.2' } }], addedStocks: [{ eventId: 'evt-1', code: '600000' }] })
  assert.equal(result.stocks[0].code, '600000')
  assert.equal(result.stocks[0].fields['涨跌幅'], '3.2')
  assert.equal(result.addedStocks[0].eventId, 'evt-1')
})

test('normalizes English stream event and defaults sparse collections', () => {
  const result = normalizeStrategyEvent({ type: 'snapshot', strategyId: 'eastmoney_1' })
  assert.deepEqual(result.addedStocks, [])
  assert.equal(result.addedCount, 0)
})
