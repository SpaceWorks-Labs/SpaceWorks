import { plural, t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useContext, useId, useState, type ReactNode } from "react";

import { StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { formatMoney } from "./paymentsApi";
import { StaffListContext } from "./StaffListContext";

// Decision 216 item 8: each money owner side by side, never summed across owners or currencies.
type Charges = { currency: string; charges: number; owed: string; paid_online: string; paid_offline: string;
  offline_receipts: number; offline_by_method: Record<string, string>; waived: string; refunded: string };
type Section<T> = { owner: string; source: string; currencies: T[] };
type Reimbursement = { currency: string; submitted_count: number; submitted: string; approved_count: number; approved: string; paid: string };
type Payout = { currency: string; obligations: number; approved: string; paid: string; remaining: string; paid_by_method: Record<string, string> };
type Budget = { currency: string; income: string; refunds: string; other_income: string; expenses: string; payouts: string;
  budget: string | null; budget_left: string | null; net: string };
type Linked = { event_id: number; sections: {
  registration_charges?: Section<Charges> & { tracking_enabled: boolean };
  venue_fee?: Section<Charges> & { status: "none" | "configured" | "charged" | "free" };
  booking_room_charge?: Section<Charges> & { label: string; read_only: boolean; state: "linked" | "booking_unavailable"; booking_ids: number[] };
  reimbursements?: Section<Reimbursement>;
  payouts?: Section<Payout> & { settlement: "offline" };
  budget?: Section<Budget>;
} };

export function EventLinkedFinancePanel({ tenant, eventId }: { tenant: number; eventId: number }) {
  const { actorId, makerspace } = useContext(StaffListContext);
  if (!actorId || makerspace?.id !== tenant || !makerspace.enabled_modules?.includes("events")) return null;
  // The server decides each section from its own module and authority; hidden sections are omitted.
  return <LinkedFinance key={`${actorId}:${tenant}:${eventId}`} tenant={tenant} eventId={eventId} actorId={actorId} />;
}

function LinkedFinance({ tenant, eventId, actorId }: { tenant: number; eventId: number; actorId: number }) {
  const [open, setOpen] = useState(false);
  const money = useQuery({
    queryKey: ["event-linked-finance", actorId, tenant, eventId], enabled: open, retry: false, gcTime: 0,
    queryFn: ({ signal }) => staffRequest<Linked>(`/admin/makerspace/${tenant}/finance/events/${eventId}/linked`, { signal }),
  });
  const s = money.data?.sections;
  const panelId = useId();
  return <section className="grid gap-2" data-replay-block>
    <button className="desk-button w-fit" type="button" aria-expanded={open} aria-controls={panelId}
      onClick={() => setOpen(value => !value)}>{open ? t`Hide linked finance` : t`View linked finance`}</button>
    <div id={panelId} className="grid gap-2" hidden={!open}>{open ? <>
      {money.isPending ? <p role="status">{t`Loading linked finance…`}</p> : null}
      {money.isError ? <p role="alert">{t`Linked finance is unavailable for your access.`}</p> : null}
      {s ? <div className="grid gap-3 sm:grid-cols-2">
        {s.registration_charges ? <Card title={t`Registration charges`} source={s.registration_charges.source}
          note={s.registration_charges.tracking_enabled ? undefined : t`Charge tracking is off; recorded charges are kept.`}>
          {s.registration_charges.currencies.map(row => <ChargeRows key={row.currency} row={row} />)}
        </Card> : null}
        {s.venue_fee ? <Card title={t`Venue fee`} source={s.venue_fee.source} note={venueStatus(s.venue_fee.status)}>
          {s.venue_fee.currencies.map(row => <ChargeRows key={row.currency} row={row} />)}
        </Card> : null}
        {s.booking_room_charge ? <Card title={t`Booking room charge`} source={s.booking_room_charge.source}
          badge={t`Booking-owned`} note={s.booking_room_charge.state === "linked"
            ? t`Read only. Bookings ${s.booking_room_charge.booking_ids.join(", ")}; managed from the booking.`
            : t`The linked booking is no longer available.`}>
          {s.booking_room_charge.currencies.map(row => <ChargeRows key={row.currency} row={row} />)}
        </Card> : null}
        {s.reimbursements ? <Card title={t`Reimbursements`} source={s.reimbursements.source}>
          {s.reimbursements.currencies.map(row => <Group key={row.currency} currency={row.currency}>
            <Row label={t`Submitted (${row.submitted_count})`} value={formatMoney(row.submitted, row.currency)} />
            <Row label={t`Approved (${row.approved_count})`} value={formatMoney(row.approved, row.currency)} />
            <Row label={t`Paid`} value={formatMoney(row.paid, row.currency)} />
          </Group>)}
        </Card> : null}
        {s.payouts ? <Card title={t`Payouts`} source={s.payouts.source} note={t`Recorded offline by finance staff.`}>
          {s.payouts.currencies.map(row => <Group key={row.currency} currency={row.currency}>
            <Row label={t`Approved (${row.obligations})`} value={formatMoney(row.approved, row.currency)} />
            <Row label={t`Paid`} value={formatMoney(row.paid, row.currency)} />
            <Row label={t`Remaining`} value={formatMoney(row.remaining, row.currency)} />
          </Group>)}
        </Card> : null}
        {s.budget ? <Card title={t`Budget against actual`} source={s.budget.source}>
          {s.budget.currencies.map(row => <Group key={row.currency} currency={row.currency}>
            <Row label={t`Budget`} value={row.budget === null ? t`Not set` : formatMoney(row.budget, row.currency)} />
            <Row label={t`Spent`} value={formatMoney(String(Number(row.expenses) + Number(row.payouts)), row.currency)} />
            {row.budget_left === null ? null : <Row label={t`Left`} value={formatMoney(row.budget_left, row.currency)} />}
            <Row label={t`Net`} value={formatMoney(row.net, row.currency)} />
          </Group>)}
        </Card> : null}
      </div> : null}
    </> : null}</div>
  </section>;
}

function venueStatus(status: "none" | "configured" | "charged" | "free") {
  return { none: t`No venue fee set.`, configured: t`Not charged yet.`, charged: t`Charged.`, free: t`Nothing to charge.` }[status];
}

function paidOffline(receipts: number) {
  return plural(receipts, { one: "Paid offline (# receipt)", other: "Paid offline (# receipts)" });
}

/** Each owner keeps its own provenance, named in operator language; an unknown one stays verbatim. */
function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    "payments.Payment": t`Registration payments`,
    "events.EventVenueFee": t`Event venue fee`,
    "bookings.Booking": t`Room booking`,
    "event_reimbursements.ReimbursementClaim": t`Reimbursement claims`,
    "payments.EventPayoutObligation": t`Event payouts`,
    "payments.finance_rows": t`Event finance records`,
  };
  return labels[source] ?? source;
}

function ChargeRows({ row }: { row: Charges }) {
  return <Group currency={row.currency}>
    <Row label={t`Owed`} value={formatMoney(row.owed, row.currency)} />
    <Row label={t`Paid online`} value={formatMoney(row.paid_online, row.currency)} />
    <Row label={paidOffline(row.offline_receipts)} value={formatMoney(row.paid_offline, row.currency)} />
    {Number(row.waived) ? <Row label={t`Waived`} value={formatMoney(row.waived, row.currency)} /> : null}
    {Number(row.refunded) ? <Row label={t`Refunded`} value={formatMoney(row.refunded, row.currency)} /> : null}
  </Group>;
}

function Card({ title, source, badge, note, children }: { title: string; source: string; badge?: string; note?: string; children: ReactNode }) {
  const from = sourceLabel(source);
  return <article className="min-w-0 rounded-xl border border-line bg-panel p-3">
    <h4 className="flex flex-wrap items-center gap-2 font-semibold">{title}{badge ? <StatusPill label={badge} /> : null}</h4>
    {note ? <p className="text-xs text-muted">{note}</p> : null}
    <div className="grid gap-2 text-sm">{children}</div>
    <p className="mt-2 text-xs text-muted">{t`Source: ${from}`}</p>
  </article>;
}

function Group({ currency, children }: { currency: string; children: ReactNode }) {
  return <div className="grid gap-1">
    <p className="text-xs font-semibold text-muted">{currency.toUpperCase()}</p>
    <dl className="grid gap-1" aria-label={currency.toUpperCase()}>{children}</dl>
  </div>;
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return <div className="flex justify-between gap-3"><dt>{label}</dt><dd>{value}</dd></div>;
}
