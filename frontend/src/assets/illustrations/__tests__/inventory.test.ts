import { readFileSync, readdirSync } from 'node:fs'
import { resolve, sep } from 'node:path'
import { createHash } from 'node:crypto'
import { createElement } from 'react'
import { render, cleanup } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import frozen from '../../../../../backend/tests/events/programme/contracts/fixtures/template-seed-v2.json'
import seeds from '../../../../../backend/apps/events/default_templates/schema_fixtures.json'
import { getIllustration, illustrationImageProps, illustrationManifest, illustrationTokens } from '..'
import { expectNoA11yViolations } from '../../../test/axe'

const root = resolve(process.cwd(), 'src/assets/illustrations') + sep
const themes = ['light', 'dark'] as const
const allPaths = illustrationManifest.flatMap((entry) => themes.map((theme) => entry.paths[theme]))
afterEach(cleanup)

describe('Space Works original artwork inventory', () => {
  it('enumerates exactly the frozen 58 frontend files and 29 real theme twins', () => {
    const files = readdirSync(root, { recursive: true }).map(String)
      .filter((name) => name.endsWith('.svg')).map((name) => name.replace(/\\/g, '/'))
    expect(files.sort()).toEqual([...allPaths].sort())
    expect(files).toHaveLength(frozen.counts.frontend_svg)
    expect(illustrationManifest).toHaveLength(29)
    expect(new Set(illustrationManifest.map((item) => item.consumerId)).size).toBe(29)
    for (const entry of illustrationManifest) {
      expect(entry.alt.length).toBeGreaterThan(12)
      expect(entry.consumerId.length).toBeGreaterThan(6)
      expect(readFileSync(root + entry.paths.light, 'utf8'))
        .not.toBe(readFileSync(root + entry.paths.dark, 'utf8'))
      for (const theme of themes) {
        expect(getIllustration(entry.id, theme).src).toMatch(/^(data:image\/svg\+xml,|\/)/)
      }
      expect(getIllustration(entry.id, 'light').src).not.toBe(getIllustration(entry.id, 'dark').src)
    }
  })

  it('keeps all twelve required empty areas and all four companion poses', () => {
    expect(illustrationManifest.filter((entry) => entry.semanticRole === 'empty')
      .map((entry) => entry.id)).toEqual([
      'empty/applications', 'empty/teams', 'empty/submissions', 'empty/judging',
      'empty/mentoring', 'empty/volunteering', 'empty/gallery', 'empty/certificates',
      'empty/broadcasts', 'empty/saved-details', 'empty/analytics', 'empty/readiness',
    ])
    expect(illustrationManifest.filter((entry) => entry.semanticRole === 'companion')
      .map((entry) => entry.id)).toEqual([
      'companion/idle', 'companion/walk', 'companion/nap', 'companion/print',
    ])
  })

  it('completes the exact 70-file inventory with checksum-bound E template fixtures', () => {
    const templates = resolve(process.cwd(), '../backend/apps/events/default_templates')
    const files = readdirSync(resolve(templates, 'artwork')).filter((file) => file.endsWith('.svg'))
    expect(files).toHaveLength(frozen.counts.packaged_svg)
    expect(files.length + allPaths.length).toBe(70)
    expect((files.length + allPaths.length) / 2).toBe(frozen.counts.twin_pairs)
    expect(seeds.certificates).toHaveLength(frozen.counts.certificate_renders)
    expect(seeds.badges).toHaveLength(frozen.counts.badge_stock_renders)
    expect(new Set(seeds.badges.map((seed) => seed.stock))).toEqual(new Set(Object.keys(frozen.stocks)))
    const resources = [...seeds.certificates, ...seeds.badges].flatMap((seed) => seed.resources)
    expect(new Set(resources.map((resource) => resource.path.replace('artwork/', ''))))
      .toEqual(new Set(files))
    for (const resource of resources) {
      expect(resource.kind).toBe('packaged_artwork')
      expect(resource.path).toMatch(/^artwork\/(certificate|badge)-[a-z]+\.(light|dark)\.svg$/)
      const bytes = readFileSync(resolve(templates, resource.path))
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(resource.sha256)
    }
    for (const seed of [...seeds.certificates, ...seeds.badges]) {
      expect(seed.document.version).toBe(2)
      expect(seed.document.layers.length).toBeLessThanOrEqual(frozen.max_layers)
    }
  })

  it('resolves the same light/dark CSS tokens used by the app and print artwork', () => {
    const css = readFileSync(resolve(root, '../../index.css'), 'utf8')
    const blocks = [css.split(':root {')[1].split('}')[0], css.split('.sw-island-dark {')[1].split('}')[0]]
    themes.forEach((theme, index) => {
      for (const [token, hex] of Object.entries(illustrationTokens[theme])) {
        const match = blocks[index].match(new RegExp(`--color-${token}:\\s*([\\d ]+);`))
        expect(match, token).not.toBeNull()
        const actual = '#' + match![1].trim().split(/\s+/).map((n) => Number(n).toString(16).padStart(2, '0')).join('').toUpperCase()
        expect(actual).toBe(hex)
      }
    })
  })

  it('contains only inert self-contained SVG primitives and approved per-mode colours', () => {
    const allowed = new Set(['svg', 'g', 'path', 'rect', 'circle'])
    for (const entry of illustrationManifest) for (const theme of themes) {
      const source = readFileSync(root + entry.paths[theme], 'utf8')
      const xml = new DOMParser().parseFromString(source, 'image/svg+xml')
      expect(xml.querySelector('parsererror')).toBeNull()
      const svg = xml.documentElement
      expect(svg.getAttribute('viewBox')).toBe(`0 0 ${entry.width} ${entry.height}`)
      expect(svg.getAttribute('aria-hidden')).toBe('true')
      expect(svg.getAttribute('focusable')).toBe('false')
      expect(source).not.toMatch(/<!|url\(|https?:\/\/(?!www\.w3\.org\/2000\/svg)|SW2[.:]|animate|filter|<style|<text/)
      for (const element of [svg, ...svg.querySelectorAll('*')]) {
        expect(allowed.has(element.localName)).toBe(true)
        for (const attribute of element.attributes) {
          expect(attribute.name).not.toMatch(/^on|href|tabindex/i)
        }
      }
      const palette = new Set<string>(Object.values(illustrationTokens[theme]))
      for (const hex of source.match(/#[\da-fA-F]{6}/g) ?? []) expect(palette.has(hex)).toBe(true)
    }
  })

  it('provides one decorative or meaningfully labelled image without focusable content', async () => {
    const decorative = render(createElement('img', illustrationImageProps('empty/teams', 'light')))
    expect(decorative.container.querySelector('img')).toHaveAttribute('alt', '')
    expect(decorative.container.querySelector('img')).toHaveAttribute('aria-hidden', 'true')
    const meaningful = render(createElement('img', illustrationImageProps('roles/mentor', 'dark', false)))
    expect(meaningful.getByRole('img')).toHaveAccessibleName('Open workshop notebook and conversation card')
    expect(meaningful.container.querySelector('img')).not.toHaveAttribute('aria-hidden')
    await expectNoA11yViolations(meaningful.container)
  })
})
