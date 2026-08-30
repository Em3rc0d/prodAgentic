import { buildEditorialSvg, escapeXml } from '../lib/editorial-visual'


describe('deterministic editorial visual renderer', () => {
  it('builds LinkedIn portrait geometry by default', () => {
    const result = buildEditorialSvg(
      'Un LLM no debería poder validar su propia verdad. La frontera debe ser explícita.',
      'EDITORIAL_POSTER',
    )

    expect(result.width).toBe(1080)
    expect(result.height).toBe(1350)
    expect(result.svg).toContain('viewBox="0 0 1080 1350"')
    expect(result.svg).toContain('EDITORIAL POSTER')
  })

  it('escapes user/model text instead of allowing SVG markup injection', () => {
    const hostile = '<script>alert("x")</script> & una arquitectura segura.'
    const result = buildEditorialSvg(hostile, 'TECHNICAL_DIAGRAM', '4:5')

    expect(result.svg).not.toContain('<script>')
    expect(result.svg).toContain('&lt;script&gt;')
    expect(result.svg).toContain('&amp;')
    expect(escapeXml('a < b & c > d')).toBe('a &lt; b &amp; c &gt; d')
  })

  it('keeps portrait architecture layouts inside the feed canvas using stacked cards', () => {
    const result = buildEditorialSvg(
      'Una arquitectura separa generación y validación. El boundary revisa el resultado. La publicación ocurre después.',
      'ARCHITECTURE_SCHEMATIC',
      '4:5',
    )

    expect(result.svg).toContain('ARCHITECTURE SCHEMATIC')
    expect(result.svg).toContain('x="112"')
    expect(result.svg).not.toContain('A boundary should make the decision visible')
  })

  it('uses distinct deterministic compositions instead of one generic wallpaper template', () => {
    const content = 'Primero se genera una propuesta. Luego se valida. Después se revisa. Finalmente se publica.'
    const process = buildEditorialSvg(content, 'PROCESS_FLOW', '4:5').svg
    const comparison = buildEditorialSvg(content, 'COMPARISON', '4:5').svg
    const artifact = buildEditorialSvg(content, 'ARTIFACT_BOARD', '4:5').svg

    expect(process).not.toBe(comparison)
    expect(comparison).toContain('>VS<')
    expect(artifact).toContain('ARTIFACT BOARD')
  })
})
