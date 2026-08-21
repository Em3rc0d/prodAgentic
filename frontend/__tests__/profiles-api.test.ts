import { createContentProfile, fetchContentProfiles, setDefaultContentProfile } from '../lib/api'

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
})
