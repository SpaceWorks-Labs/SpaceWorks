import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { Callout, ProgressBar, StatusPill } from "../../components/ui";
import { memberRequest } from "../../lib/api";

// Hand-written until the OpenAPI snapshot is regenerated (decision 234 addendum 3).
type Level = "ok" | "warning" | "limit";
export type AllowanceMeter = { used: number; limit: number | null; remaining: number | null; percent: number | null; level: Level };
export type MemberAllowancesData = {
  makerspace_id: number;
  borrowing: { active_loans: AllowanceMeter; items_out: AllowanceMeter } | null;
  included_hours: unknown[];
  guest_passes: AllowanceMeter | null;
  day_passes: { product_id: number; name: string; available_today: boolean }[] | null;
};

export const memberAllowancesKey = (id: number) => ["member", "allowances", id] as const;
export function useMemberAllowances(makerspaceId: number) {
  return useQuery({ queryKey: memberAllowancesKey(makerspaceId), enabled: makerspaceId >= 0, retry: false, staleTime: 60_000,
    queryFn: () => memberRequest<MemberAllowancesData>(`/member/makerspaces/${makerspaceId}/allowances`) });
}

function Meter({ label, meter, left }: { label: string; meter: AllowanceMeter; left: string }) {
  if (meter.limit === null) return null; // no cap: nothing to count down
  const tone = meter.level === "limit" ? "danger" : meter.level === "warning" ? "warn" : "accent";
  return <li className="grid gap-1">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-sm font-semibold text-ink">{label}</span>
      {meter.level === "limit" ? <StatusPill label={t`None left`} tone="danger" /> : meter.level === "warning" ? <StatusPill label={t`Almost used`} tone="warn" /> : null}
    </div>
    <p className="text-sm text-muted">{left}</p>
    <ProgressBar value={(meter.percent ?? 0) / 100} tone={tone} label={label} />
  </li>;
}

/**
 * What the member has left here (#234 addendum 3(a)): loans and items they can still borrow, guests
 * they can bring now, and whether day passes are on sale today. Included hours have their own card.
 * Renders nothing when no section applies.
 */
export function MemberAllowances({ makerspaceId }: { makerspaceId: number }) {
  const query = useMemberAllowances(makerspaceId);
  const data = query.data;
  if (!data || typeof data !== "object" || !("borrowing" in data)) return null;
  const loans = data.borrowing?.active_loans, items = data.borrowing?.items_out, guests = data.guest_passes;
  const meters = [
    loans?.limit != null ? <Meter key="loans" label={t`Loans at once`} meter={loans}
      left={t`${loans.remaining ?? 0} of ${loans.limit} left`} /> : null,
    items?.limit != null ? <Meter key="items" label={t`Items out at once`} meter={items}
      left={t`${items.remaining ?? 0} of ${items.limit} left`} /> : null,
    guests?.limit != null ? <Meter key="guests" label={t`Guests you can bring now`} meter={guests}
      left={t`${guests.remaining ?? 0} of ${guests.limit} left`} /> : null,
  ].filter(Boolean);
  const passes = data.day_passes ?? [];
  if (!meters.length && !passes.length) return null;
  const full = [loans, items].some(meter => meter?.level === "limit");
  return <section aria-labelledby="member-allowances-title" className="desk-panel grid gap-4 p-5">
    <h2 id="member-allowances-title" className="title-panel">{t`What you have left`}</h2>
    {full ? <Callout size="inline" tone="danger" lead={t`You've reached your borrowing limit.`} body={t`Return something to borrow more.`} />
      : [loans, items].some(meter => meter?.level === "warning")
        ? <Callout size="inline" tone="warn" lead={t`You're close to your borrowing limit.`} /> : null}
    {meters.length ? <ul className="grid gap-4 sm:grid-cols-2">{meters}</ul> : null}
    {passes.length ? <div className="grid gap-2">
      <h3 className="text-sm font-semibold text-ink">{t`Day passes today`}</h3>
      <ul className="flex flex-wrap gap-2">{passes.map(pass => <li key={pass.product_id}>
        <StatusPill label={pass.available_today ? t`${pass.name}: available` : t`${pass.name}: sold out`} tone={pass.available_today ? "success" : "neutral"} />
      </li>)}</ul>
    </div> : null}
  </section>;
}
