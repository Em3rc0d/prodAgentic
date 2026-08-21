import { resolveBackendAssetUrl } from '../lib/api'


describe('backend asset URL resolution', () => {
  it('resolves backend-relative render assets against the configured API origin', () => {
    expect(resolveBackendAssetUrl('/assets/renders/render-1.png')).toBe(
      'http://localhost:8000/assets/renders/render-1.png'
    )
  })

  it('preserves already absolute render assets', () => {
    expect(resolveBackendAssetUrl('https://cdn.example.com/render-1.png')).toBe(
      'https://cdn.example.com/render-1.png'
    )
  })

  it('preserves null when there is no owned render asset', () => {
    expect(resolveBackendAssetUrl(null)).toBeNull()
  })
})
