import { t } from "@lingui/core/macro";
import { EmptyState, StatusBadge } from "../../components/ui";
import { requestStatusLabel } from "../../components/ui/StatusStepper";
import { formatDateTime } from "../../lib/format";
import type { OwnBorrowing } from "./borrowingHistoryApi";
import { MemberRequestWithdraw, WITHDRAWABLE } from "./MemberRequestWithdraw";
import { MemberLoanRenew } from "./MemberLoanRenew";

const date = (value: string) => formatDateTime(value);
const sourceLabel = (source: OwnBorrowing["source"]) => source === "admin_direct" ? t`Staff handout`
  : source === "public_self_checkout" ? t`Self-checkout` : t`Reviewed request`;

/** Own workflow facts only: stock calculations, evidence and staff-only fields stay in their owners.
 * `withdraw` is set when `loans.withdrawals` is on: a reviewed request not yet handed over can be withdrawn. */
export function BorrowingHistoryList({ rows, withdraw, space }: { rows: OwnBorrowing[]; withdraw?: { makerspaceId: number; makerspaceSlug: string };
  /** The space, for Renew on a loan the server says the borrower may renew (decision 221a). */
  space?: { makerspaceId: number; makerspaceSlug: string } }) {
  if (!rows.length) return <EmptyState message={t`No borrowing records match this view. Your requests, handovers and returns will appear here.`} />;
  return <ul className="grid gap-4">{rows.map(row => <li key={row.id}>
    <article aria-label={t`Request #${row.id}`} className="desk-panel grid min-w-0 gap-4 p-4 sm:p-5">
      <header className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div><h2 className="title-section">{t`Request #${row.id}`}</h2><p className="text-sm text-muted">{sourceLabel(row.source)}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={row.status} label={requestStatusLabel(row.status)} />
          {withdraw && row.source === "reviewed_request" && WITHDRAWABLE.includes(row.status) ? <MemberRequestWithdraw {...withdraw} requestId={row.id} /> : null}
          {space && row.can_renew ? <MemberLoanRenew key={row.return_due_at} {...space} requestId={row.id} />
            : row.renewal_refusal === "self_renewal_off" ? <span className="text-sm text-muted">{t`Ask staff to renew`}</span>
            : row.renewal_refusal === "renewal_limit" ? <span className="text-sm text-muted">{t`No renewals left`}</span> : null}
          {row.can_renew && typeof row.renewals_left === "number"
            ? <span className="text-sm text-muted">{row.renewals_left === 1 ? t`1 renewal left` : t`${row.renewals_left} renewals left`}</span> : null}
        </div>
      </header>
      <dl className="grid gap-2 text-sm text-muted sm:grid-cols-2">
        <div><dt className="font-semibold text-ink">{t`Requested`}</dt><dd>{date(row.created_at)}</dd></div>
        {row.issued_at || row.checked_out_at ? <div><dt className="font-semibold text-ink">{t`Handed over`}</dt><dd>{date((row.issued_at || row.checked_out_at)!)}</dd></div> : null}
        {row.return_due_at ? <div><dt className="font-semibold text-ink">{t`Due back`}</dt><dd>{date(row.return_due_at)}</dd></div> : null}
        {row.closed_at ? <div><dt className="font-semibold text-ink">{t`Closed`}</dt><dd>{date(row.closed_at)}</dd></div> : null}
        {row.returns.map((event, index) => <div key={`${event.returned_at}-${index}`}><dt className="font-semibold text-ink">{t`Return recorded`}</dt><dd>{date(event.returned_at)}</dd></div>)}
        {!row.returns.length && row.returned_at ? <div><dt className="font-semibold text-ink">{t`Returned`}</dt><dd>{date(row.returned_at)}</dd></div> : null}
      </dl>
      <ul className="grid gap-3">{row.items.map((item, index) => <li key={index} className="min-w-0 rounded-lg border border-line p-3">
        <h3 className="font-semibold text-ink">{item.product_name}</h3>
        <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
          <span>{t`Requested ${item.requested_quantity}`}</span><span>{t`Accepted ${item.accepted_quantity}`}</span>
          <span>{t`Issued ${item.issued_quantity}`}</span><span>{t`Returned ${item.returned_quantity}`}</span>
          {item.damaged_quantity > 0 ? <span>{t`Damaged ${item.damaged_quantity}`}</span> : null}
          {item.missing_quantity > 0 ? <span>{t`Missing ${item.missing_quantity}`}</span> : null}
          {item.needs_fix_quantity > 0 ? <span>{t`Needs repair ${item.needs_fix_quantity}`}</span> : null}
        </p>
      </li>)}</ul>
    </article>
  </li>)}</ul>;
}
