import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { DelightProvider, MakerModeHost, MakerModeToggle, useShellMakerMode, type DelightArtwork } from '../../../components/delight'
import { LogoDelight } from '../../../components/delight/LogoDelight'
import { SudoMake } from '../../../components/delight/SneakyLines'
import { getIllustration, type IllustrationId } from '../../../assets/illustrations'

const ids: Partial<Record<keyof DelightArtwork, IllustrationId>> = {
  loader: 'brand-loader', welcome: 'moods/welcome', success: 'moods/success', waiting: 'moods/waiting', empty: 'moods/empty', error: 'moods/error',
  tag: 'equipment-tag-404', companionWalk: 'companion/walk', companionFollow: 'companion/idle', companionNap: 'companion/nap', companionPrint: 'companion/print', demo: 'landing/workshop-demo',
}
const artwork = Object.fromEntries(Object.entries(ids).map(([key, id]) => [key, {
  light: getIllustration(id, 'light').src, dark: getIllustration(id, 'dark').src,
}])) as DelightArtwork

export function ProgrammeDelight({ children }: { children: ReactNode }) {
  const location = useLocation()
  return <DelightProvider artwork={artwork}><MakerModeHost pathname={`${location.pathname}${location.search}`} version={String(import.meta.env.VITE_APP_VERSION ?? '')}>
    <LogoActivation />{children}
  </MakerModeHost></DelightProvider>
}
function LogoActivation() {
  const mode = useShellMakerMode()
  const { pathname } = useLocation()
  return <><LogoDelight pathname={pathname} onLogoClick={mode?.activateLogo} /><SudoMake allowed={Boolean(mode?.allowed)} /></>
}
export function ProgrammeMakerToggle() {
  const mode = useShellMakerMode()
  return mode ? <MakerModeToggle mode={mode} /> : null
}
