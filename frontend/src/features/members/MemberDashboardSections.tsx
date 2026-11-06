import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, StatusPill, StatCard } from "../../components/ui";
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
  const ends = new Date(term.ends_at).toLocaleDateString(formatLocale());
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

export function MemberDues({ dues }: { dues: MemberActivity["membership_dues"] }) {
  if (!dues) return null;
  // `null` is "we could not read the ledger", not "nothing is owed". Kept apart all the
  // way to the screen: collapsing them here would quietly tell a member they are clear.
  const unavailable = dues.outstanding_by_currency === null;
  const outstanding = Object.entries(dues.outstanding_by_currency ?? {});
  return (
    <section className="desk-panel p-5">
      <h2 className="title-panel">{t`Membership fee`}</h2>
<div className="mt-3 grid gap-3 sm:grid-cols-2"><StatCard label={t`Membership fee`} value={dues.dues_amount} />{outstanding.map(([currency, amount]) => <StatCard key={currency} label={t`Outstanding ${currency.toUpperCase()}`} value={`${amount} ${currency.toUpperCase()}`} />)}</div>
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
    {requests?.length ? <><h3 className="title-section">{t`Requests`}</h3>{requests.map((row, index) => <ListRow key={`${row.created_at}-${index}`} title={`${row.item_count} ${row.item_count === 1 ? "item" : "items"} requested`} identity={{ kind: "date", date: row.created_at }}
      meta={<>{row.returned_quantity} returned{row.damaged_quantity || row.missing_quantity ? <span className="block text-danger">{row.damaged_quantity} damaged, {row.missing_quantity} missing</span> : null}</>}
      right={<div className="grid justify-items-start gap-2"><StatusPill label={row.status.replace(/_/g, " ")} />
        {withdraw && row.id && WITHDRAWABLE.includes(row.status) ? <MemberRequestWithdraw {...withdraw} requestId={row.id} /> : null}</div>} />)}</> : null}
    {loans?.length ? <><h3 className="title-section">{t`Returned items`}</h3>{loans.map((row, index) => <ListRow key={`${row.label}-${index}`} title={row.label} identity={row.returned_at ? { kind: "date", date: row.returned_at } : undefined}
      meta={row.returned_at ? `Returned ${new Date(row.returned_at).toLocaleDateString(formatLocale())}` : undefined} right={row.returned_late ? <StatusPill label={t`Returned late`} tone="warn" /> : <StatusPill label={t`Returned`} tone="success" />} />)}</> : null}
  </section>;
}
