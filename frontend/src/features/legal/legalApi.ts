import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { publicAnonymousRequest } from "../../lib/api/requests";

/** Parity E-B8 (A13): privacy and terms. Typed locally until the staging step regenerates `generated/api.ts`. */
export type LegalSlug = "privacy" | "terms";
export type LegalPageBody = {
  slug: LegalSlug; markdown: string; source: "space" | "platform" | "default"; language: string; updated_at: string | null;
};

export const LEGAL_SLUGS: readonly LegalSlug[] = ["privacy", "terms"];
export const legalTitle = (slug: LegalSlug) => slug === "privacy" ? t`Privacy policy` : t`Terms of use`;

/** Anonymous read; `space` adds that space's own text when it wrote one (and its switch is on). */
export function useLegalPage(slug: LegalSlug, space: string) {
  return useQuery({
    queryKey: ["legal-page", slug, space],
    queryFn: () => publicAnonymousRequest<LegalPageBody>(`/discover/legal/${slug}/${space ? `?${new URLSearchParams({ space })}` : ""}`),
    staleTime: 300_000,
    retry: false,
  });
}
