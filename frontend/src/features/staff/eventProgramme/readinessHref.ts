import { consoleSessionHref } from '../../../lib/api/sessionContext'

const tabs: Record<string, string> = {
  applications: 'applications', teams: 'programme-teams', submissions: 'programme-teams', judging: 'judging',
  mentoring: 'mentor-desk', volunteers: 'volunteers', roles: 'volunteers', certificates: 'certificates',
  publishing: 'settings', cover: 'website', forms: 'settings', overview: 'overview', website: 'website',
}
/** Backend readiness uses domain names; translate them into the existing drawer registry. */
export function readinessHref(href: string, eventId: number, currentPath: string) {
  let url: URL
  try { url = new URL(href, window.location.origin) } catch { return '' }
  if (url.origin !== window.location.origin || url.pathname !== '/admin/events' || url.searchParams.get('event') !== String(eventId)) return ''
  const tab = tabs[url.searchParams.get('tab') ?? '']
  if (!tab) return ''
  const path = /\/(?:admin)\/(?:events|assigned-events|assigned-resources|granted)\/?$/.test(currentPath) ? currentPath : '/admin/events'
  return consoleSessionHref(`${path}?event=${eventId}&eventTab=${tab}`)
}
