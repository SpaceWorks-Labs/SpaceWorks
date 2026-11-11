import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { EmptyState, ErrorText, ListRow, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { formatWhen, waitlistApi, waitlistKeys } from "../../inventory/waitlistApi";

/** Who is waiting for this item, in order. Offers expire on their own; staff only watch the queue here. */
export function ItemWaitlist({ makerspaceId, productId }: { makerspaceId: number; productId: number }) {
  const query = useQuery({ queryKey: waitlistKeys.staff(makerspaceId, productId), queryFn: () => waitlistApi.forItem(makerspaceId, productId) });
  const rows = query.data ?? [];
  return <section aria-label={t`Waitlist`} className="grid gap-3 border-t border-line pt-3">
    <h3 className="title-section">{t`Waitlist`}</h3>
    {query.isLoading ? <Skeleton className="h-16 w-full" /> : query.error ? <ErrorText message={t`Couldn't load the waitlist. Try again.`} />
      : !rows.length ? <EmptyState message={t`Nobody is waiting for this item.`} />
      : rows.map(entry => <ListRow key={entry.id} title={[entry.status === "offered" ? t`Offer held` : t`Place ${entry.position ?? "-"}`, entry.member_name].filter(Boolean).join(" · ")}
        identity={{ kind: "icon", icon: entry.status === "offered" ? "Clock" : "Circle", tone: entry.status === "offered" ? "info" : "neutral" }}
        meta={<><span className="tabular-nums">×{entry.quantity}</span> {t` · joined `}<RelativeTime date={entry.created_at} />
          {entry.status === "offered" && entry.offer_expires_at ? <> {t` · held until ${formatWhen(entry.offer_expires_at)}`}</> : null}</>}
        right={<StatusPill label={entry.status === "offered" ? t`Offered` : entry.status === "claimed" ? t`Claimed` : t`Waiting`}
          tone={entry.status === "offered" ? "info" : entry.status === "claimed" ? "success" : "neutral"} />} />)}
  </section>;
}
