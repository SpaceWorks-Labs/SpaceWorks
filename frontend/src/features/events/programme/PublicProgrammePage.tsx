import { useParams } from 'react-router-dom'
import { CalendarDays } from 'lucide-react'
import { AppShell } from '../../../components/shell'
import { useTenant } from '../../../lib/tenant'
import { tenantPublicRequestBlob } from '../../../lib/api'
import { GalleryPage } from '../hackathonGallery/GalleryPage'
import { ResultsPage } from '../hackathonGallery/ResultsPage'

export function PublicProgrammePage({ results = false }: { results?: boolean }) {
  const { publicToken = '', entryPublicId, slug } = useParams(), tenant = useTenant()
  const makerspaceSlug = slug ?? tenant.slug ?? ''
  const base = `${makerspaceSlug ? `/m/${encodeURIComponent(makerspaceSlug)}` : ''}/events/${encodeURIComponent(publicToken)}`
  return <AppShell variant="member" compactNav="drawer" activeKey={results ? 'results' : 'gallery'} user={{ name: 'Space Works', menu: [] }}
    nav={[{ key: 'event', items: [{ key: 'event', label: 'Event', href: base, icon: CalendarDays },
      { key: 'gallery', label: 'Project gallery', href: `${base}/gallery`, icon: CalendarDays },
      { key: 'results', label: 'Results', href: `${base}/results`, icon: CalendarDays }] }]}>
    {results ? <ResultsPage makerspaceSlug={makerspaceSlug} publicToken={publicToken} eventTitle="Event" /> : <GalleryPage
      makerspaceSlug={makerspaceSlug} publicToken={publicToken} eventTitle="Event" entryPublicId={entryPublicId}
      projectHref={id => `${base}/gallery/${encodeURIComponent(id)}`}
      renderMemberCard={member => <a className="inline-flex min-h-11 items-center gap-3 underline" href={member.profile_url}>
        {member.photo_url ? <img src={member.photo_url} alt="" className="size-11 rounded-full object-cover" loading="lazy" referrerPolicy="no-referrer" /> : null}{member.display_name}</a>}
      onDownload={async asset => {
        // Ignore a cached download_url: the live token/opaque ID route rechecks consent.
        const blob = await tenantPublicRequestBlob(makerspaceSlug, `/public/event-programmes/${encodeURIComponent(publicToken)}/gallery/assets/${encodeURIComponent(asset.public_id)}/`)
        const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = `project-file-${asset.public_id}`; link.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      }} />}
  </AppShell>
}
