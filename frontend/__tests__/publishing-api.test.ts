import {
  connectLinkedIn,
  disconnectLinkedIn,
  fetchLinkedInPublisherStatus,
  publishContentRun,
} from '../lib/publishing'

describe('LinkedIn publishing API', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ configured: true, csrf_token: 'csrf-test' }) })) as jest.Mock
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { assign: jest.fn() },
    })
  })

  it('reads OAuth connection readiness without exposing secret material', async () => {
    await fetchLinkedInPublisherStatus()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/integrations/linkedin/status',
      expect.objectContaining({ cache: 'no-store', credentials: 'include' })
    )
  })

  it('starts LinkedIn OAuth using only the backend-issued authorization URL', async () => {
    global.fetch = jest.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ authenticated: true, csrf_token: 'csrf-connect' }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ authorization_url: 'https://www.linkedin.com/oauth/v2/authorization?state=opaque' }) })

    await connectLinkedIn()
    expect(global.fetch).toHaveBeenLastCalledWith(
      'http://localhost:8000/api/integrations/linkedin/connect',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
    expect(window.location.assign).toHaveBeenCalledWith('https://www.linkedin.com/oauth/v2/authorization?state=opaque')
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
