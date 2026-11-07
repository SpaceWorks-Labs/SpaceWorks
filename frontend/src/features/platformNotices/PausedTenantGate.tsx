import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient, type Query } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore, type ReactNode } from "react";
import { publicV1Request } from "../../lib/api";
import { StructuredApiError } from "../../lib/api/errors";
import { PausedSpacePage } from "./PausedSpacePage";

/** The space a public /m/<slug> page belongs to; the staff console handles paused spaces itself. */
export function publicTenantSlug(pathname: string) {
  const match = /^\/m\/([^/]+)(\/[^/]*)?/.exec(pathname);
  if (!match || match[2] === "/admin") return "";
  try { return decodeURIComponent(match[1]); } catch { return ""; }
}

/** The tenant bootstraps a public page may run: the shared one, and the member area's own. */
function isBootstrapOf(query: Query, slug: string) {
  const key = query.queryKey;
  return (key[0] === "tenant-bootstrap" && key[1] === slug) || (key[0] === "member" && key[1] === slug && key[2] === "bootstrap");
}

function bootstrapNotFound(queries: Query[], slug: string) {
  return queries.some(query => isBootstrapOf(query, slug) && query.state.error instanceof StructuredApiError && query.state.error.status === 404);
}

/**
 * A suspended space is unservable, so its tenant bootstrap 404s exactly like an unknown slug. Rather than
 * touching every public page, this watches the bootstrap queries those pages already run: on a 404 it
 * asks the public availability endpoint once, and shows the paused page when the answer is `paused`.
 * Anything else (a genuinely unknown or archived space) keeps the page's own not-found.
 */
export function PausedTenantGate({ slug, children }: { slug: string; children: ReactNode }) {
  const client = useQueryClient();
  const cache = client.getQueryCache();
  const subscribe = useCallback((listener: () => void) => cache.subscribe(listener), [cache]);
  const notFound = useSyncExternalStore(subscribe, () => Boolean(slug) && bootstrapNotFound(cache.getAll(), slug));
  const availability = useQuery({
    queryKey: ["public-space-availability", slug],
    queryFn: () => publicV1Request<{ state: "active" | "paused" }>(`/public/makerspaces/${encodeURIComponent(slug)}/availability`),
    enabled: notFound,
    retry: false,
    staleTime: 60_000,
  });
  if (notFound && availability.data?.state === "paused") {
    return <PausedSpacePage primary={{ label: t`Find another space`, href: "/" }} />;
  }
  return <>{children}</>;
}
