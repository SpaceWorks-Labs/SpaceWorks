import { t } from "@lingui/core/macro";
import { formatLocale } from "../../lib/format";
import type { TenantBootstrap } from "../../lib/api";

/**
 * P3-4: "Open now" / "Closed now, opens ..." from the space's recorded hours. The bootstrap
 * carries `open_status` only when hours are set, so nothing renders otherwise. A status past
 * its own change instant is stale (the page outlived it) and renders nothing rather than guess.
 */
export function OpenNowIndicator({ bootstrap, now = Date.now() }: { bootstrap: TenantBootstrap; now?: number }) {
  const status = bootstrap.makerspace.open_status;
  if (!status) return null;
  const changesAt = status.open_now ? status.closes_at : status.next_opens_at;
  if (changesAt && now >= new Date(changesAt).getTime()) return null;
  const timeZone = bootstrap.makerspace.timezone;
  const at = changesAt ? new Intl.DateTimeFormat(formatLocale(), {
    weekday: "short", hour: "numeric", minute: "2-digit", timeZone,
  }).format(new Date(changesAt)) : null;
  const tone = status.open_now ? "border-success bg-success-soft" : "border-warn bg-warn-soft";
  const label = status.open_now
    ? (at ? t`Open now · closes ${at}` : t`Open now`)
    : (at ? t`Closed now · next opens ${at}` : t`Closed now`);
  return <p className={`w-fit rounded-full border px-3 py-1 text-sm font-semibold text-ink ${tone}`} role="status">{label}</p>;
}
