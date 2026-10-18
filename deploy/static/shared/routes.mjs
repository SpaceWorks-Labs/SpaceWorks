const RESERVED = new Set(('about admin api assets bookings checkout config.js control discover docs embed e events '
  + 'event-check-in favicon.ico fonts guest-admin health healthz index.html install items kiosk m machines media '
  + 'member member-sw.js mfa now o organization-invitations print redoc reset-password robots.txt scanner '
  + 'schema setup share sitemap.xml staff staff-invitations static stats superadmin sw.js').split(' '));
const UUID = '[0-9a-fA-F-]{36}';

export function safePath(pathname) {
  let path;
  try { path = decodeURIComponent(pathname); } catch { return null; }
  // Refuse ambiguous encodings before a downstream proxy can decode them again.
  if (/[\\\u0000-\u0020\u007f%]/.test(path) || path.includes('//')
      || path.split('/').some(part => part === '.' || part === '..')) return null;
  return path;
}

export function route(path, userAgent = '') {
  if (/^\/(?:control|mfa\/control)(?:\/|$)/i.test(path)
      || /^\/api\/v1\/(?:internal|metrics)(?:\/|$)/i.test(path)) return { kind: 'deny' };
  if (/^\/config\.js\/?$/.test(path)) return { kind: 'config' };
  if (/^\/(?:api|share|embed|static|docs|redoc|schema)(?:\/|$)/.test(path)
      || /^\/(?:robots\.txt|sitemap\.xml)$/.test(path)) return { kind: 'proxy', path };
  if (/bot|crawler|spider|slack|facebookexternalhit|twitter|whatsapp|linkedin/i.test(userAgent)) {
    const event = path.match(new RegExp(`^/(?:m/[^/]+/)?events/(${UUID})/?$`))
      || path.match(new RegExp(`^/e/(${UUID})/?$`));
    if (event) return { kind: 'proxy', path: `/share/events/${event[1]}/` };
    const booking = path.match(new RegExp(`^/(?:m/[^/]+/)?bookings/(${UUID})/?$`));
    if (booking) return { kind: 'proxy', path: `/share/bookings/${booking[1]}/` };
    const handle = path.match(/^\/([a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9]))\/?$/);
    if (handle && !RESERVED.has(handle[1])) return { kind: 'proxy', path: `/share/pages/${handle[1]}/` };
  }
  return { kind: 'asset' };
}
