import { approveContentRun } from '../lib/api'


describe('ContentRun approval API', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          run_id: 'run-approval',
          status: 'APPROVED',
          approval: {
            approval_id: 'approval-1',
            approved_at: '2026-08-20T20:00:00Z',
            source: 'explicit_user_action',
            include_visual: true,
            final_content: 'Approved text',
            final_content_sha256: 'a'.repeat(64),
            visual_render_sha256: 'b'.repeat(64),
            bundle_sha256: 'c'.repeat(64),
          },
          topic: 'AI',
          style: 'educational',
          idea: 'Idea',
          stages: {},
          created_at: '2026-08-20T19:00:00Z',
          updated_at: '2026-08-20T20:00:00Z',
        }),
      })
    ) as jest.Mock;
  });

  it('sends the explicit text-plus-visual approval decision', async () => {
    const approved = await approveContentRun('run-approval', true)

    expect(approved.status).toBe('APPROVED')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs/run-approval/approve',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ include_visual: true }),
      }
    )
  })

  it('can explicitly approve a text-only bundle', async () => {
    await approveContentRun('run-approval', false)

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs/run-approval/approve',
      expect.objectContaining({
        body: JSON.stringify({ include_visual: false }),
      })
    )
  })
})
