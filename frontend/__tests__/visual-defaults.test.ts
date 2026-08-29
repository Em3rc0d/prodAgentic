import { renderVisual } from '../lib/api'


describe('visual render defaults', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        render_id: 'render-1',
        status: 'READY',
        provider: 'test',
        prompt_used: 'Architecture schematic technical_editorial',
      }),
    })) as jest.Mock
  })

  it('uses LinkedIn portrait technical-editorial defaults when the caller does not override them', async () => {
    await renderVisual('Architecture schematic', undefined, undefined, 'run-1', 'render-key-123')

    const [, init] = (global.fetch as jest.Mock).mock.calls[0]
    const payload = JSON.parse(init.body)

    expect(payload.aspect_ratio).toBe('4:5')
    expect(payload.style).toBe('technical_editorial')
    expect(payload.run_id).toBe('run-1')
  })
})
