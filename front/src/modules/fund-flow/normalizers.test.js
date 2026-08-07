import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeFundFlowRows, matrixToFundFlowRows, normalizeFundFlowEvent, formatFundFlowAmount } from './normalizers.js'

test('formats fund-flow amounts to two decimals without changing raw values', () => {
  assert.equal(formatFundFlowAmount(4.111302), '4.11')
  assert.equal(formatFundFlowAmount(-4.105), '-4.11')
  assert.equal(formatFundFlowAmount(0), '0.00')
  assert.equal(formatFundFlowAmount(123456.789), '123456.79')
})

test('normalizes snapshot rows to camelCase and converts null amounts', () => {
  assert.deepEqual(normalizeFundFlowRows([{ board_name: '机器人', time: '10:00:00', net_inflow_100m: null, leader: '甲' }]), [
    { boardName: '机器人', time: '10:00:00', netInflow100m: 0, leader: '甲', boardCode: '' },
  ])
})

test('flattens sparse English matrix data without inventing missing points', () => {
  assert.deepEqual(matrixToFundFlowRows({ format: 'matrix-v2', times: ['10:00', '10:01'], boards: [{ name: '机器人', code: 'A', points: [[1, 3, '甲']] }] }), [
    { boardName: '机器人', boardCode: 'A', time: '10:01', netInflow100m: 3, leader: '甲' },
  ])
})

test('normalizes English snapshot events', () => {
  assert.deepEqual(normalizeFundFlowEvent({ type: 'snapshot', flow_type: 'industry', trade_date: '20260806' }), {
    type: 'snapshot', flowType: 'industry', tradeDate: '20260806', collectedAt: '', recordCount: 0,
  })
})
