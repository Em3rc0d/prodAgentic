import { fetchLinkedInPublisherStatus, publishContentRun } from '../lib/publishing'

describe('LinkedIn publishing API', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ configured: true }) })) as jest.Mock
  })

  it('reads publisher readiness without exposing secret material', async () => {
    await fetchLinkedInPublisherStatus()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/publishing/linkedin/status',
      { cache: 'no-store' }
    )
  })

  it('publishes by ContentRun identity with no mutable content payload', async () => {
    await publishContentRun('run-123')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs/run-123/publish',
      { method: 'POST' }
    )
  })
})
