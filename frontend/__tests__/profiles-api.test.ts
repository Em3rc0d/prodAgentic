import { acceptProfileV2, createContentProfile, fetchContentProfiles, proposeProfileV2, setDefaultContentProfile } from '../lib/api'

const profile = {
  name: 'Architect Voice',
  display_name: 'Architect Voice',
  positioning: 'Systems engineering through evidence.',
  audience: ['architects'],
  voice: ['technical'],
  core_topics: ['AI'],
  excluded_topics: [],
  target_language: 'en' as const,
  image_prompt_language: 'en' as const,
  min_words: 140,
  max_words: 210,
  preferred_style: 'educational',
  visual_enabled: true,
  default_aspect_ratio: '16:9' as const,
  default_visual_style: 'minimal',
  forbidden_claims: [],
  banned_phrases: [],
  brand_constraints: [],
  is_default: true,
}

describe('content profile API', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ profiles: [], count: 0 }) })) as jest.Mock
  })

  it('loads the reusable profile library', async () => {
    await fetchContentProfiles()
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/api/content-profiles', expect.objectContaining({ cache: 'no-store', credentials: 'include' }))
  })

  it('creates a profile with explicit guardrail payload', async () => {
    await createContentProfile(profile)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-profiles',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(profile) })
    )
  })

  it('sets the selected profile as the generation default', async () => {
    await setDefaultContentProfile('profile-1')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/content-profiles/profile-1/default',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
  })

  it('keeps Profile V2 proposal and acceptance as separate explicit calls', async () => {
    const setup = {
      name: 'Systems Field Notes', account_type: 'education' as const,
      goals: ['educate' as const], audience: 'software engineers', voice: ['direct'],
      batch_size: 4, channels: ['linkedin' as const], examples: [],
    }
    await proposeProfileV2(setup)
    expect(global.fetch).toHaveBeenLastCalledWith(
      'http://localhost:8000/api/profiles/inference-proposals',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(setup), credentials: 'include' })
    )
    await acceptProfileV2(setup, 'a'.repeat(64))
    expect(global.fetch).toHaveBeenLastCalledWith(
      'http://localhost:8000/api/profiles',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ setup, proposal_digest: 'a'.repeat(64) }), credentials: 'include' })
    )
  })
})
