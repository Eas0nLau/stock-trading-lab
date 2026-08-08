import test from 'node:test'
import assert from 'node:assert/strict'
import { createDragonTigerCollectionJob, getDragonTigerCollectionJob, analyzeDragonTigerPremium } from './api.js'

function mockFetch(t, expectedUrl, expectedOptions, body) {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, expectedUrl)
    assert.deepEqual(options, expectedOptions)
    return { ok: true, async json() { return body } }
  })
}

test('creates collection job with date payload', async t => {
  mockFetch(t, '/api/v1/dragon-tiger/collection-jobs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"startDate":20260404,"latestDate":20260806}',
  }, { jobId: 'job-1' })
  assert.deepEqual(await createDragonTigerCollectionJob('20260404', '20260806'), { jobId: 'job-1' })
})

test('gets job status and analyzes premium range', async t => {
  mockFetch(t, '/api/v1/dragon-tiger/collection-jobs/job-1', undefined, { status: 'running' })
  assert.equal((await getDragonTigerCollectionJob('job-1')).status, 'running')
  mockFetch(t, '/api/v1/dragon-tiger/premium?start_date=20260404&latest_date=20260806', undefined, { selectedCodes: [] })
  assert.deepEqual(await analyzeDragonTigerPremium(20260404, 20260806), { selectedCodes: [] })
})
