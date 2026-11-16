import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { DelightProvider, MakerModeHost, MakerModeToggle, useDelightSpaceFeatures, useShellMakerMode, type DelightArtwork } from '../../../components/delight'
import { LogoDelight } from '../../../components/delight/LogoDelight'
import { SudoMake } from '../../../components/delight/SneakyLines'
import { useOptionalTenant } from '../../../lib/tenant'
import { useTenantBootstrap } from '../../inventory/usePublicInventory'
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
  const spaceFeatures = useShowingSpaceFeatures(location.pathname)
  return <DelightProvider artwork={artwork} spaceFeatures={spaceFeatures}><MakerModeHost pathname={`${location.pathname}${location.search}`} version={String(import.meta.env.VITE_APP_VERSION ?? '')}>
    <LogoActivation />{children}
  </MakerModeHost></DelightProvider>
}
/** Single-tenant bootstrap, the central /m/:slug bootstrap (shared cache), or the staff shell's space. */
function useShowingSpaceFeatures(pathname: string) {
  const tenant = useOptionalTenant()
  const slug = tenant?.mode === 'single' ? '' : /^\/m\/([^/]+)/.exec(pathname)?.[1] ?? ''
  const central = useTenantBootstrap(slug, Boolean(slug))
  const staff = useDelightSpaceFeatures()
  if (tenant?.mode === 'single') return tenant.bootstrap?.features ?? null
  if (slug) return central.data?.features ?? null
  return staff
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
