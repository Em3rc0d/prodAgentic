import {
  connectLinkedIn,
  disconnectLinkedIn,
  fetchLinkedInPublisherStatus,
  publishContentRun,
} from '../lib/publishing'

describe('LinkedIn publishing API', () => {
  const authorizationUrl = 'https://www.linkedin.com/oauth/v2/authorization?state=opaque'

  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        configured: true,
        authenticated: true,
        csrf_token: 'csrf-test',
        authorization_url: authorizationUrl,
      }),
    })) as jest.Mock
  })

  it('reads OAuth connection readiness without exposing secret material', async () => {
    await fetchLinkedInPublisherStatus()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/integrations/linkedin/status',
      expect.objectContaining({ cache: 'no-store', credentials: 'include' })
    )
  })

  it('starts LinkedIn OAuth using only the backend-issued authorization URL', async () => {
    await expect(connectLinkedIn()).resolves.toBe(authorizationUrl)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/integrations/linkedin/connect',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
  })

  it('disconnects LinkedIn through the protected backend boundary', async () => {
    await disconnectLinkedIn()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/integrations/linkedin/disconnect',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
  })

  it('publishes by ContentRun identity with no mutable content payload', async () => {
    await publishContentRun('run-123')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs/run-123/publish',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
  })
})
