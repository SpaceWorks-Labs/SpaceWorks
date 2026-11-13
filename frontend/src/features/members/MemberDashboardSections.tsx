import { formatDate } from "../../lib/format";
import { formatMoney } from "../../lib/money";
import { plural, t } from "@lingui/core/macro";
import { EmptyState, ListRow, ProgressBar, StatusPill, StatCard, statusToneMap } from "../../components/ui";
import { hoursText } from "../payments/IncludedHoursLine";
import { requestStatusLabel } from "../../components/ui/StatusStepper";
import type { MemberActivity } from "./MemberActivity";
import { MemberRequestWithdraw, WITHDRAWABLE } from "./MemberRequestWithdraw";

/** The member dashboard's history, money and notices (D8).
 *
 * Rendered only when the `membership` module is on, because the endpoint that feeds it
 * is module-gated. Notices are DERIVED server-side from the member's own rows rather
 * than read from the staff notification table, which has no recipient column.
 */
export function MemberNotices({ notices }: { notices: MemberActivity["notices"] }) {
  if (!notices?.length) return null;
  return (
    <section className="desk-panel p-5">
      <h2 className="title-panel">{t`Needs your attention`}</h2>
      <div className="mt-3 grid gap-3">{notices.map(notice => <ListRow key={notice.event + notice.title} title={notice.title} meta={notice.body}
        right={<StatusPill label={notice.level === "critical" ? t`Action needed` : notice.level === "warning" ? t`Attention` : t`Update`} tone={notice.level === "critical" ? "danger" : notice.level === "warning" ? "warn" : "info"} />} />)}</div>
    </section>
  );
}

/** The member's own plan term. Hidden when they never held one: plans are optional. */
export function MemberTerm({ term }: { term: MemberActivity["membership_term"] }) {
  if (!term) return null;
  const ends = formatDate(term.ends_at);
  return (
    <section className="desk-panel p-5">
      <h2 className="title-panel">{t`Membership plan`}</h2>
      <p className="mt-2 text-sm text-ink">{term.plan_name}</p>
      <p className="mt-1 text-sm text-muted">
        {term.current ? t`Current until ${ends}` : t`Ended ${ends}`}
      </p>
      {term.blocks_borrowing ? (
        <p className="mt-1 text-sm text-danger">{t`Borrowing is paused until your membership is renewed.`}</p>
      ) : null}
    </section>
  );
}

/** Decision 221(d): plan hours per term, used before any hourly price. Hidden when the plan has none. */
export function MemberIncludedHours({ rows }: { rows: MemberActivity["included_hours"] }) {
  const pools = (rows ?? []).filter((row) => row.allowance_minutes > 0);
  if (!pools.length) return null;
  return (
    <section className="desk-panel p-5" aria-labelledby="included-hours-title">
      <h2 id="included-hours-title" className="title-panel">{t`Included hours`}</h2>
      <ul className="mt-3 grid gap-4 sm:grid-cols-2">{pools.map((row) => {
        const left = hoursText(row.remaining_minutes / 60);
        const total = hoursText(row.allowance_minutes / 60);
        const ends = formatDate(row.term_ends_at);
        const label = row.kind === "machine" ? t`Machine time` : t`Room bookings`;
        return <li key={`${row.term_id}-${row.kind}`} className="grid gap-2">
          <p className="flex flex-wrap items-baseline justify-between gap-2 text-sm"><span className="font-semibold text-ink">{label}</span>
            <span className="tabular-nums text-ink">{t`${left} of ${total} h left`}</span></p>
          <ProgressBar value={row.remaining_minutes / row.allowance_minutes} label={t`${label}: ${left} of ${total} hours left`}
            tone={row.remaining_minutes === 0 ? "danger" : row.remaining_minutes * 5 <= row.allowance_minutes ? "warn" : "accent"} />
          <p className="text-xs text-muted">{t`${row.plan_name} · resets after ${ends}`}</p>
        </li>;
      })}</ul>
    </section>
  );
}

/** `currency` is the space's membership currency (the admission settings' joining-fee currency, which the
 *  dues amount is an alias of); the dues payload itself carries none. Without it the bare amount shows. */
export function MemberDues({ dues, currency }: { dues: MemberActivity["membership_dues"]; currency?: string }) {
  if (!dues) return null;
  // `null` is "we could not read the ledger", not "nothing is owed". Kept apart all the
  // way to the screen: collapsing them here would quietly tell a member they are clear.
  const unavailable = dues.outstanding_by_currency === null;
  const outstanding = Object.entries(dues.outstanding_by_currency ?? {});
  // The server names the dues currency; the admission settings' currency is the fallback for an older payload.
  const feeCurrency = dues.dues_currency || currency;
  return (
    <section className="desk-panel p-5">
      <h2 className="title-panel">{t`Membership fee`}</h2>
<div className="mt-3 grid gap-3 sm:grid-cols-2"><StatCard label={t`Membership fee`} value={feeCurrency ? formatMoney(dues.dues_amount, feeCurrency) : dues.dues_amount} />{outstanding.map(([currency, amount]) => <StatCard key={currency} label={outstanding.length > 1 ? t`Outstanding ${currency.toUpperCase()}` : t`Outstanding`} value={formatMoney(amount, currency)} />)}</div>
      {unavailable ? (
        <p className="mt-1 text-sm text-muted">
          {t`Outstanding balance is unavailable right now.`}</p>
      ) : !outstanding.length ? (
        <p className="mt-1 text-sm text-muted">{t`Nothing outstanding.`}</p>
      ) : null}
    </section>
  );
}

export function MemberHistory({
  loans,
  requests,
  withdraw,
}: {
  loans: MemberActivity["loan_history"];
  requests: MemberActivity["request_history"];
  /** Set when `loans.withdrawals` is on: pending and accepted requests get a Withdraw button. */
  withdraw?: { makerspaceId: number; makerspaceSlug: string };
}) {
  if (!loans?.length && !requests?.length) return <EmptyState message={t`No returned items yet. Your borrowing history will appear here.`} />;
  return <section className="grid gap-4"><h2 className="title-panel">{t`Your history`}</h2>
    {requests?.length ? <><h3 className="title-section">{t`Requests`}</h3>{requests.map((row, index) => <ListRow key={`${row.created_at}-${index}`} title={plural(row.item_count, { one: "# item requested", other: "# items requested" })} identity={{ kind: "date", date: row.created_at }}
      meta={<>{t`${row.returned_quantity} returned`}{row.damaged_quantity || row.missing_quantity ? <span className="block text-danger">{t`${row.damaged_quantity} damaged, ${row.missing_quantity} missing`}</span> : null}</>}
      right={<div className="grid justify-items-start gap-2"><StatusPill label={requestStatusLabel(row.status)} tone={statusToneMap[row.status]} />
        {withdraw && row.id && WITHDRAWABLE.includes(row.status) ? <MemberRequestWithdraw {...withdraw} requestId={row.id} /> : null}</div>} />)}</> : null}
    {loans?.length ? <><h3 className="title-section">{t`Returned items`}</h3>{loans.map((row, index) => <ListRow key={`${row.label}-${index}`} title={row.label} identity={row.returned_at ? { kind: "date", date: row.returned_at } : undefined}
      meta={row.returned_at ? t`Returned ${formatDate(row.returned_at)}` : undefined} right={row.returned_late ? <StatusPill label={t`Returned late`} tone="warn" /> : <StatusPill label={t`Returned`} tone="success" />} />)}</> : null}
  </section>;
}
