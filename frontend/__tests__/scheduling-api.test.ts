import { cancelContentSchedule, scheduleContentRun } from '../lib/scheduling'

describe('scheduling API', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ run_id: 'run-1' }) })) as jest.Mock
  })

  it('sends the exact offset-aware instant chosen by the UI', async () => {
    const instant = '2026-08-21T15:30:00.000Z'
    await scheduleContentRun('run-1', instant)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs/run-1/schedule',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ scheduled_for: instant }) })
    )
  })

  it('cancels by ContentRun identity without mutating approval content', async () => {
    await cancelContentSchedule('run-1')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-runs/run-1/schedule',
      expect.objectContaining({ method: 'DELETE', credentials: 'include' })
    )
  })
})
