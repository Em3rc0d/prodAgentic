import type { ContentRun } from './api'
import { secureFetch } from './auth'

const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export interface PublicationSnapshot {
  provider: 'linkedin' | string
  status: 'PUBLISHING' | 'PUBLISHED' | 'FAILED' | string
  attempt_id: string
  approval_id: string
  bundle_sha256: string
  author_urn?: string | null
  started_at: string
  completed_at?: string | null
  external_post_urn?: string | null
  external_image_urn?: string | null
  error_message?: string | null
}

export type PublishableContentRun = ContentRun & { publication?: PublicationSnapshot | null }

export interface LinkedInPublisherStatus {
  configured: boolean
  connected?: boolean
  status?: 'CONNECTED' | 'NOT_CONNECTED' | 'RECONNECT_REQUIRED' | string
  display_name?: string | null
  picture_url?: string | null
  author_urn?: string
  expires_at?: string | null
  scopes?: string[]
  api_version?: string
  reason?: string
}

export async function fetchLinkedInPublisherStatus(): Promise<LinkedInPublisherStatus> {
  const res = await secureFetch(`${API}/api/integrations/linkedin/status`, { cache: 'no-store' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    return {
      configured: false,
      connected: false,
      status: 'NOT_CONFIGURED',
      reason: payload?.detail || `LinkedIn integration unavailable (${res.status})`,
    }
  }
  return res.json()
}

export async function connectLinkedIn(): Promise<string> {
  const res = await secureFetch(`${API}/api/integrations/linkedin/connect`, { method: 'POST' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    throw new Error(payload?.detail || `LinkedIn connection failed (${res.status})`)
  }
  const payload = await res.json() as { authorization_url?: string }
  if (!payload.authorization_url) throw new Error('LinkedIn authorization URL was not returned')
  return payload.authorization_url
}

export async function disconnectLinkedIn(): Promise<void> {
  const res = await secureFetch(`${API}/api/integrations/linkedin/disconnect`, { method: 'POST' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    throw new Error(payload?.detail || `LinkedIn disconnect failed (${res.status})`)
  }
}

export async function publishContentRun(runId: string): Promise<PublishableContentRun> {
  const res = await secureFetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/publish`, { method: 'POST' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const detail = payload?.detail ? `: ${payload.detail}` : ''
    throw new Error(`LinkedIn publish failed (${res.status})${detail}`)
  }
  return res.json()
}
