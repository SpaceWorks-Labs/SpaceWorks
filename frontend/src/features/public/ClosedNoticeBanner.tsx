import { Callout } from "../../components/ui";
import type { TenantBootstrap } from "../../lib/api";

/**
 * #77: the Space Manager's "closed for now" notice. The space keeps working (no lifecycle
 * state); the bootstrap carries the notice only while `public_site.closed_notice` is on.
 */
export function ClosedNoticeBanner({ bootstrap }: { bootstrap: TenantBootstrap }) {
  const notice = bootstrap.makerspace.closed_notice;
  if (!notice) return null;
  const reopens = notice.reopens_on
    ? new Intl.DateTimeFormat(undefined, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })
      .format(new Date(`${notice.reopens_on}T00:00:00Z`))
    : null;
  return <div role="status"><Callout size="banner" tone="warn" lead={notice.text} body={reopens ? `Reopening ${reopens}.` : undefined} /></div>;
}
