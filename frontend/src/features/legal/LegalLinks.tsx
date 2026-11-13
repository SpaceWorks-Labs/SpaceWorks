import { t } from "@lingui/core/macro";
import { useOptionalTenant } from "../../lib/tenant";
import { RouteLink } from "../../components/ui/RouteLink";

/** "Privacy · Terms" under sign-in and sign-up (parity A13); a space's own pages when a space is known. */
export function LegalLinks({ space = "" }: { space?: string }) {
  const tenant = useOptionalTenant();
  const href = (slug: "privacy" | "terms") => tenant?.mode !== "single" && space ? `/m/${space}/${slug}` : `/${slug}`;
  return <nav aria-label={t`Privacy and terms`} className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
    <RouteLink className="underline underline-offset-4 hover:text-ink" href={href("privacy")}>{t`Privacy`}</RouteLink>
    <span aria-hidden="true">·</span>
    <RouteLink className="underline underline-offset-4 hover:text-ink" href={href("terms")}>{t`Terms`}</RouteLink>
  </nav>;
}
