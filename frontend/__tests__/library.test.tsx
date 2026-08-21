import { act, render, screen } from '@testing-library/react'

import ContentLibraryPage from '../app/library/page'


describe('Content Library', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          count: 1,
          runs: [
            {
              run_id: 'run-123',
              topic: 'Agentic systems',
              style: 'educational',
              idea: 'Why durable AI workflows beat prompt chains',
              status: 'READY_FOR_REVIEW',
              resolved_target_language: 'en',
              stages: {},
              final_content: 'Final copy',
              visual_prompt: 'Visual prompt',
              created_at: '2026-08-20T12:00:00Z',
              updated_at: '2026-08-20T13:00:00Z',
            },
          ],
        }),
      })
    ) as jest.Mock;
  });

  it('lists persisted runs and links to the reopen surface', async () => {
    await act(async () => {
      render(<ContentLibraryPage />)
    })

    const idea = await screen.findByText('Why durable AI workflows beat prompt chains')
    expect(screen.getAllByText(/READY FOR REVIEW/i).length).toBeGreaterThan(0)
    expect(screen.getByText('Agentic systems')).toBeInTheDocument()
    expect(idea.closest('a')).toHaveAttribute('href', '/library/run-123')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs?limit=100',
      expect.objectContaining({ cache: 'no-store', credentials: 'include' })
    )
  })
})
