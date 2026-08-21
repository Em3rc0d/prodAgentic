import type { ContentRun } from './api'

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
  author_urn?: string
  api_version?: string
  reason?: string
}

export async function fetchLinkedInPublisherStatus(): Promise<LinkedInPublisherStatus> {
  const res = await fetch(`${API}/api/publishing/linkedin/status`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to read LinkedIn publisher status: ${res.status}`)
  return res.json()
}

export async function publishContentRun(runId: string): Promise<PublishableContentRun> {
  const res = await fetch(`${API}/api/content-runs/${encodeURIComponent(runId)}/publish`, { method: 'POST' })
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    const detail = payload?.detail ? `: ${payload.detail}` : ''
    throw new Error(`LinkedIn publish failed (${res.status})${detail}`)
  }
  return res.json()
}
