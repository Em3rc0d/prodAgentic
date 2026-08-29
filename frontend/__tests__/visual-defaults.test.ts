import { renderVisual } from '../lib/api'


describe('visual render defaults', () => {
  beforeEach(() => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/auth/session')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ authenticated: true, auth_enabled: true, csrf_token: 'csrf-test' }),
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          render_id: 'render-1',
          status: 'READY',
          provider: 'test',
          prompt_used: 'Architecture schematic technical_editorial',
        }),
      })
    }) as jest.Mock
  })

  it('uses LinkedIn portrait technical-editorial defaults when the caller does not override them', async () => {
    await renderVisual('Architecture schematic', undefined, undefined, 'run-1', 'render-key-123')

    const renderCall = (global.fetch as jest.Mock).mock.calls.find(([input]) =>
      String(input).endsWith('/api/visual-renders')
    )
    expect(renderCall).toBeDefined()

    const [, init] = renderCall
    const payload = JSON.parse(init.body)

    expect(payload.aspect_ratio).toBe('4:5')
    expect(payload.style).toBe('technical_editorial')
    expect(payload.run_id).toBe('run-1')
  })
})
