import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { StructuredApiError, publicV1Request } from "../../lib/api";
import { hostScope } from "../publicPages/pageApi";
import { safePublicLink } from "../publicPages/PublicCollectionCards";

// O-B5 public directory; typed locally until the staging step regenerates `generated/api.ts`.
export type DirectoryOrganization = { name: string; slug: string; description: string; logo_url: string | null; canonical_url: string };
export type DirectoryPage = { count: number; next: string | null; previous: string | null; results: DirectoryOrganization[] };

export const directoryKey = (page: number, search: string) => ["public-organization-directory", hostScope(), page, search] as const;

/** 404 is the server's answer when the directory switch is off or this host lists no organizations. */
export const isDirectoryOff = (error: unknown) => error instanceof StructuredApiError && error.status === 404;

export function usePublicOrganizationDirectory(page: number, search: string) {
  return useQuery({
    queryKey: directoryKey(page, search),
    queryFn: () => publicV1Request<DirectoryPage>(`/public/organizations/?${new URLSearchParams({ page: String(page), ...(search ? { search } : {}) })}`, { cache: "no-store" }),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    retry: (count: number, error: unknown) => !(error instanceof StructuredApiError && error.status < 500) && count < 1,
  });
}

/**
 * Whether to show a link to `/organizations`. Reads the directory's first page (the same cache entry
 * the page opens on); only a successful answer shows the link, so an off switch or an outage hides it.
 */
export function useOrganizationDirectoryEnabled() {
  const first = usePublicOrganizationDirectory(1, "");
  return first.isSuccess;
}

/** Same-origin canonical links navigate in-app; another origin (a handle's canonical host) stays a full link. */
export function canonicalHref(row: { canonical_url: string }, fallback: string) {
  const safe = safePublicLink(row.canonical_url);
  if (!safe) return fallback;
  const url = new URL(safe, window.location.origin);
  return url.origin === window.location.origin ? `${url.pathname}${url.search}` : url.href;
}
