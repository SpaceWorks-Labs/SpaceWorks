import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { Callout } from "../ui";

function lockDate(endsAt: string) {
  const date = new Date(endsAt);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(formatLocale(), { weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit" });
}

/**
 * The staff-shell readiness banner (#128 C-1): shown at each sign-in while a person's 3-day
 * grace runs. Staff screens lock when it ends; member screens never do.
 */
export function MfaReadinessBanner({ endsAt, href }: { endsAt: string; href: string }) {
  const when = lockDate(endsAt);
  return <Callout size="banner" tone="warn" lead="Set up two-step sign-in"
    body={`${when ? `Staff screens lock on ${when}.` : "Staff screens lock soon."} Use an authenticator app or a passkey. Your member area keeps working.`}
    action={{ label: t`Set it up now`, href }} />;
}
