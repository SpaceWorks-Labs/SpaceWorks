import { illustrationManifest } from './manifest'
import type { IllustrationId, IllustrationTheme } from './manifest'

export { illustrationManifest, illustrationTokens } from './manifest'
export type { IllustrationId, IllustrationTheme } from './manifest'

// Vite resolves these packaged files at build time, including their content hashes.
const sources = import.meta.glob<string>('./**/*.svg', {
  query: '?url', import: 'default', eager: true,
})

/** One image for the chosen theme; callers decide whether its meaning is needed. */
export function getIllustration(id: IllustrationId, theme: IllustrationTheme) {
  const entry = illustrationManifest.find((item) => item.id === id)
  if (!entry) throw new Error(`Unknown Space Works illustration: ${id}`)
  const src = sources[`./${entry.paths[theme]}`]
  if (!src) throw new Error(`Missing Space Works illustration: ${id}/${theme}`)
  return { ...entry, src }
}

/** Use an empty alt beside an equivalent heading; never expose two theme images. */
export function illustrationImageProps(
  id: IllustrationId, theme: IllustrationTheme, decorative = true,
) {
  const entry = getIllustration(id, theme)
  return {
    src: entry.src, width: entry.width, height: entry.height,
    alt: decorative ? '' : entry.alt,
    'aria-hidden': decorative ? true as const : undefined,
    draggable: false,
  }
}
