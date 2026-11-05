import { useParams } from 'react-router-dom'
import { PublicLayout } from '../../../components/layouts'
import { useTenant, useTenantPath } from '../../../lib/tenant'
import { tenantPublicRequestBlob } from '../../../lib/api'
import { useTenantBranding } from '../../../lib/useTenantBranding'
import { publicPageChrome } from '../../inventory/PublicPageChrome'
import { formatSlug } from '../../inventory/PublicInventoryParts'
import { useTenantBootstrap } from '../../inventory/usePublicInventory'
import { GalleryPage } from '../hackathonGallery/GalleryPage'
import { ResultsPage } from '../hackathonGallery/ResultsPage'

export function PublicProgrammePage({ results = false }: { results?: boolean }) {
  const { publicToken = '', entryPublicId, slug } = useParams(), tenant = useTenant()
  const makerspaceSlug = slug ?? tenant.slug ?? ''
  const tenantPath = useTenantPath(makerspaceSlug)
  // A public page: the public layout and tenant chrome, never the member shell (DY-03).
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === 'central')
  const bootstrap = tenant.mode === 'single' ? tenant.bootstrap : bootstrapQuery.data
  const brandStyle = useTenantBranding(bootstrap)
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || 'Makerspace'
  const base = tenantPath(`events/${encodeURIComponent(publicToken)}`)
  const here = results ? 'Results' : 'Project gallery'
  // #181: People's choice voting and its award, only where the space has it on.
  const peoplesChoice = bootstrap?.features.includes('events.peoples_choice') ? bootstrap.makerspace.id : undefined
  const projectHref = (id: string) => `${base}/gallery/${encodeURIComponent(id)}`
  return <div style={brandStyle}><PublicLayout {...publicPageChrome(makerspaceSlug, name, tenantPath, bootstrap)} state={{ status: 'ready' }}
    breadcrumb={[{ label: 'All events', href: tenantPath('events') }, { label: 'Event', href: base },
      ...(entryPublicId && !results ? [{ label: here, href: `${base}/gallery` }, { label: 'Project' }] : [{ label: here }])]}>
    {results ? <ResultsPage makerspaceSlug={makerspaceSlug} publicToken={publicToken} eventTitle="Event"
      peoplesChoice={peoplesChoice !== undefined} projectHref={projectHref} /> : <GalleryPage
      peoplesChoice={peoplesChoice !== undefined ? { makerspaceId: peoplesChoice } : undefined}
      makerspaceSlug={makerspaceSlug} publicToken={publicToken} eventTitle="Event" entryPublicId={entryPublicId}
      projectHref={projectHref}
      renderMemberCard={member => <a className="inline-flex min-h-11 items-center gap-3 underline" href={member.profile_url}>
        {member.photo_url ? <img src={member.photo_url} alt="" className="size-11 rounded-full object-cover" loading="lazy" referrerPolicy="no-referrer" /> : null}{member.display_name}</a>}
      onDownload={async asset => {
        // Ignore a cached download_url: the live token/opaque ID route rechecks consent.
        const blob = await tenantPublicRequestBlob(makerspaceSlug, `/public/event-programmes/${encodeURIComponent(publicToken)}/gallery/assets/${encodeURIComponent(asset.public_id)}/`)
        const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = `project-file-${asset.public_id}`; link.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }} />}
  </PublicLayout></div>
}
