/** Stable SPA destinations. API URLs always come from the token-resolved context. */
export const programmeRoutes = {
  application: { name: 'event-programme-application', suffix: 'application', label: 'Application and RSVP' },
  team: { name: 'event-programme-team', suffix: 'team', label: 'Your team' },
  finder: { name: 'event-programme-team-finder', suffix: 'finder', label: 'Team finder' },
  project: { name: 'event-programme-project', suffix: 'project', label: 'Project and files' },
  contribute: { name: 'event-programme-contribute', suffix: 'contribute', label: 'Contribute' },
  help: { name: 'event-programme-help', suffix: 'help', label: 'Mentor help' },
  officeHours: { name: 'event-programme-office-hours', suffix: 'office-hours', label: 'Office hours' },
  sharing: { name: 'event-programme-sharing', suffix: 'sharing', label: 'Sharing and résumé' },
  presentation: { name: 'event-programme-presentation', suffix: 'presentation', label: 'Badge and public cards' },
} as const
export function programmeHref(token: string, suffix = 'application', slug = '') {
  return `${slug ? `/m/${encodeURIComponent(slug)}` : ''}/events/${encodeURIComponent(token)}/programme/${suffix}`
}
export const programmeRoutePaths = [
  '/events/:publicToken/programme/*', '/m/:slug/events/:publicToken/programme/*',
] as const
export const programmeAccountPaths = ['/member/account/saved-details', '/m/:slug/member/account/saved-details',
  '/member/account/security-activity', '/m/:slug/member/account/security-activity'] as const

export function isProgrammePath(path: string) {
  return /^\/(?:m\/[^/]+\/)?events\/[^/]+\/(?:programme(?:\/|$)|gallery(?:\/|$)|results\/?$)/.test(path)
    || /^\/(?:m\/[^/]+\/)?member\/account\/(?:saved-details|security-activity)\/?$/.test(path)
    || /^\/certificates\/verify\/[^/]+\/?$/.test(path)
}
