import { useSyncExternalStore } from 'react'
import { currentTheme, subscribeTheme } from '../../../lib/theme'

/** ARTWORK supplies these exact original SVG twins at integration. */
const illustrations = {
  applications: { light: new URL('../../../assets/illustrations/empty/applications.light.svg', import.meta.url).href,
    dark: new URL('../../../assets/illustrations/empty/applications.dark.svg', import.meta.url).href },
  teams: { light: new URL('../../../assets/illustrations/empty/teams.light.svg', import.meta.url).href,
    dark: new URL('../../../assets/illustrations/empty/teams.dark.svg', import.meta.url).href },
  hackathon: { light: new URL('../../../assets/illustrations/roles/hackathon.light.svg', import.meta.url).href,
    dark: new URL('../../../assets/illustrations/roles/hackathon.dark.svg', import.meta.url).href },
}
export function AdmissionArtwork({ kind }: { kind: keyof typeof illustrations }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme)
  return <img src={illustrations[kind][theme]} width={160} height={120} alt="" aria-hidden="true" className="mx-auto max-w-full" />
}
