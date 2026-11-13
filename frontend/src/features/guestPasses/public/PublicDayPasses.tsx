import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { ActionControl } from "../../../components/ui";
import { formatPrice } from "../../../lib/money";
import { MakerspaceSection } from "../../public/MakerspaceSection";
import { guestKeys, publicDayPasses } from "../api";

/**
 * Day passes on the public space page (decision 223 b): name and price only. Buying needs an
 * account, so the action opens the member area, where the pass is bought and paid for.
 * Hidden while loading, when none are on sale, and when the feature is off (the list 404s).
 */
export function PublicDayPasses({ slug, memberHref }: { slug: string; memberHref: string }) {
  const offers = useQuery({ queryKey: guestKeys.publicOffers(slug), queryFn: () => publicDayPasses(slug), retry: false, enabled: Boolean(slug) });
  const rows = offers.data ?? [];
  if (!rows.length) return null;
  return <MakerspaceSection id="day-passes" title={t`Visit for a day`} subtitle={t`Not a member? A day pass lets you use the space for one day.`}>
    <div className="desk-panel grid gap-4 p-5">
      <ul className="grid gap-2">{rows.map((row) => <li key={row.id} className="flex flex-wrap items-baseline justify-between gap-2 text-base">
        <span className="font-semibold text-ink">{row.name}</span><span className="tabular-nums text-muted">{formatPrice(row.amount, row.currency)}</span>
      </li>)}</ul>
      <ActionControl action={{ label: t`Get a day pass`, href: memberHref }} primary className="desk-button-brand w-fit" />
      <p className="text-sm text-muted">{t`You'll sign in or create an account, then pay online or at the space.`}</p>
    </div>
  </MakerspaceSection>;
}
