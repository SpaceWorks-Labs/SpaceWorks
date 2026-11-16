/** A slug route is never platform telemetry, even while tenant resolution is pending. */
export type ScopeSelection = { kind: "tenant"; slug: string } | { kind: "platform" } | { kind: "none" };
export function telemetryScope(url: URL, singleTenant: boolean, resolvedSlug?: string): ScopeSelection {
  if (url.origin !== window.location.origin) return { kind: "none" };
  const match = url.pathname.match(/^\/m\/([^/]+)(?:\/|$)/);
  if (match) return { kind: "tenant", slug: match[1] };
  if (singleTenant) return resolvedSlug ? { kind: "tenant", slug: resolvedSlug } : { kind: "none" };
  return { kind: "platform" };
}
