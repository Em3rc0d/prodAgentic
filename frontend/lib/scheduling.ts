import type { ContentRun } from './api'
import { secureFetch } from './auth'

const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export interface ScheduleSnapshot {
  schedule_id: string
  status: 'SCHEDULED' | 'CLAIMED' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | string
  scheduled_for: string
  approval_id: string
  bundle_sha256: string
  created_at: string
  claimed_at?: string | null
  completed_at?: string | null
  cancelled_at?: string | null
  error_message?: string | null
}

export type ScheduledContentRun = ContentRun & { schedule?: ScheduleSnapshot | null }

export async function scheduleContentRun(runId: string, scheduledForIso: string): Promise<ScheduledContentRun> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheduled_for: scheduledForIso }),
  })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const detail = payload?.detail ? `: ${payload.detail}` : ''
    throw new Error(`Schedule failed (${res.status})${detail}`)
  }
  return res.json()
}

export async function cancelContentSchedule(runId: string): Promise<ScheduledContentRun> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/schedule`, { method: 'DELETE' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const detail = payload?.detail ? `: ${payload.detail}` : ''
    throw new Error(`Cancel schedule failed (${res.status})${detail}`)
  }
  return res.json()
}
