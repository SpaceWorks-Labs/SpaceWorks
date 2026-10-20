import { useEffect, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { DelightProvider, MakerModeHost, MakerModeToggle, eggsAllowed, useShellMakerMode, type DelightArtwork } from '../../../components/delight'
import { patchArtwork } from '../../../components/delight/patchArtwork'
import { getIllustration, type IllustrationId } from '../../../assets/illustrations'

const ids: Partial<Record<keyof DelightArtwork, IllustrationId>> = {
  loader: 'brand-loader', welcome: 'moods/welcome', success: 'moods/success', waiting: 'moods/waiting', empty: 'moods/empty', error: 'moods/error',
  tag: 'equipment-tag-404', companionWalk: 'companion/walk', companionFollow: 'companion/idle', companionNap: 'companion/nap', companionPrint: 'companion/print', demo: 'landing/workshop-demo',
}
const artwork = Object.fromEntries(Object.entries(ids).map(([key, id]) => [key, {
  light: getIllustration(id, 'light').src, dark: getIllustration(id, 'dark').src,
}])) as DelightArtwork
// Patch (bitmaps under /brand/patch/) overrides the SVG moods, except where eggs never run: kiosk, scanner, checkout, payment.
const withPatch: DelightArtwork = { ...artwork, ...patchArtwork }

export function ProgrammeDelight({ children }: { children: ReactNode }) {
  const location = useLocation()
  return <DelightProvider artwork={eggsAllowed(location.pathname) ? withPatch : artwork}><MakerModeHost pathname={`${location.pathname}${location.search}`} version={String(import.meta.env.VITE_APP_VERSION ?? '')}>
    <LogoActivation />{children}
  </MakerModeHost></DelightProvider>
}
function LogoActivation() {
  const mode = useShellMakerMode()
  useEffect(() => {
    if (!mode?.allowed) return
    const clicked = (event: MouseEvent) => { if (event.target instanceof Element && event.target.closest('[data-logo]')) mode.activateLogo() }
    document.addEventListener('click', clicked)
    return () => document.removeEventListener('click', clicked)
  }, [mode?.allowed, mode?.activateLogo])
  return null
}
export function ProgrammeMakerToggle() {
  const mode = useShellMakerMode()
  return mode ? <MakerModeToggle mode={mode} /> : null
}
