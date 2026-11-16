/** Explicit deployment allowlist; never trust an arbitrary presign's origin. */
export function uploadOrigins() {
  return [window.location.origin, ...String(import.meta.env.VITE_EVENT_UPLOAD_ORIGINS ?? '').split(',')]
    .map(value => value.trim()).filter(value => /^https?:\/\/[^/]+$/.test(value))
}
