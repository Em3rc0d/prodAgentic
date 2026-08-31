jest.mock('../lib/editorial-visual', () => {
  const actual = jest.requireActual('../lib/editorial-visual')
  return {
    ...actual,
    rasterizeEditorialVisual: jest.fn(() => Promise.resolve({
      svg: '<svg/>',
      width: 1080,
      height: 1350,
      base64: 'iVBORw0KGgo=',
      sha256: 'a'.repeat(64),
    })),
  }
})

import { renderVisual } from '../lib/api'
import { rasterizeEditorialVisual } from '../lib/editorial-visual'


function response(payload: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  })
}


describe('hybrid visual API dispatch', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('rasterizes server-selected deterministic formats before POSTing owned PNG bytes', async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/auth/session')) {
        return response({ authenticated: true, auth_enabled: true, csrf_token: 'csrf-test' })
      }
      if (url.endsWith('/api/visual-plans/run-det')) {
        return response({
          run_id: 'run-det',
          policy_version: 'visual-direction-policy-v2',
          visual_format: 'ARCHITECTURE_SCHEMATIC',
          renderer: 'DETERMINISTIC',
          final_content: 'Una arquitectura separa generación y validación.',
          recommended_aspect_ratio: '4:5',
          recommended_style: 'technical_editorial',
        })
      }
      return response({
        render_id: 'render-det',
        status: 'READY',
        provider: 'DeterministicBrowserRenderer',
        prompt_used: 'visual brief',
      })
    }) as jest.Mock

    await renderVisual('visual brief', '4:5', 'technical_editorial', 'run-det', 'det-key-123')

    expect(rasterizeEditorialVisual).toHaveBeenCalledWith(
      'Una arquitectura separa generación y validación.',
      'ARCHITECTURE_SCHEMATIC',
      '4:5',
    )
    const renderCall = (global.fetch as jest.Mock).mock.calls.find(([input]) => String(input).endsWith('/api/visual-renders'))
    expect(renderCall).toBeDefined()
    const payload = JSON.parse(renderCall![1].body)
    expect(payload.deterministic_png_base64).toBe('iVBORw0KGgo=')
    expect(payload.deterministic_png_sha256).toBe('a'.repeat(64))
  })

  it('keeps genuine illustration plans on the generative provider path', async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/auth/session')) {
        return response({ authenticated: true, auth_enabled: true, csrf_token: 'csrf-test' })
      }
      if (url.endsWith('/api/visual-plans/run-story')) {
        return response({
          run_id: 'run-story',
          policy_version: 'visual-direction-policy-v2',
          visual_format: 'ILLUSTRATION',
          renderer: 'GENERATIVE',
          final_content: 'Una historia profesional sobre criterio y creatividad.',
          recommended_aspect_ratio: '4:5',
          recommended_style: 'illustration',
        })
      }
      return response({
        render_id: 'render-story',
        status: 'READY',
        provider: 'ImageProvider',
        prompt_used: 'illustration brief',
      })
    }) as jest.Mock

    await renderVisual('illustration brief', '4:5', 'illustration', 'run-story', 'gen-key-123')

    expect(rasterizeEditorialVisual).not.toHaveBeenCalled()
    const renderCall = (global.fetch as jest.Mock).mock.calls.find(([input]) => String(input).endsWith('/api/visual-renders'))
    expect(renderCall).toBeDefined()
    const payload = JSON.parse(renderCall![1].body)
    expect(payload.deterministic_png_base64).toBeUndefined()
    expect(payload.deterministic_png_sha256).toBeUndefined()
  })
})
