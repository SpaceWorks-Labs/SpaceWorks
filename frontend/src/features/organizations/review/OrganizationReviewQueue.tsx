import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, Field, ListRow, PagePager, RelativeTime, StatusPill } from "../../../components/ui";
import { OrganizationReviewDrawer } from "./OrganizationReviewDrawer";
import { REVIEW_STATUSES, reviewStatusLabels, reviewStatusTone, useReviewQueue, type ReviewQueueRow, type ReviewStatus } from "./reviewApi";
import { LogoLoader } from "../../../components/LogoLoader";

const emptyCopy = (): Record<ReviewStatus, string> => ({
  pending_review: t`Nothing waiting. New organizations appear here when review is required before they go live.`,
  changes_requested: t`No organization is waiting on changes from its applicant.`,
  approved: t`No approved organizations yet.`,
  suspended: t`No organization is suspended.`,
  declined: t`No organization has been declined.`,
});

/** The superadmin queue for organization applications (O-B5), oldest first, with every standing one filter away. */
export function OrganizationReviewQueue() {
  const [status, setStatus] = useState<ReviewStatus>("pending_review");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<ReviewQueueRow | null>(null);
  const queue = useReviewQueue(status, page);
  const rows = queue.data?.results ?? [];
  return <div className="grid gap-4">
    <Field label={t`Status`} className="max-w-xs">
      <select className="desk-input" value={status} onChange={event => { setStatus(event.target.value as ReviewStatus); setPage(1); }}>
        {REVIEW_STATUSES.map(key => <option key={key} value={key}>{reviewStatusLabels()[key]}</option>)}
      </select>
    </Field>
    {queue.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" />
      : queue.isError ? <ErrorText resource={t`organization reviews`} onRetry={() => { void queue.refetch(); }} />
      : !rows.length ? <EmptyState message={emptyCopy()[status]} />
      : <ul className="grid gap-3">{rows.map(row => <li key={row.id}><ListRow title={row.name} onClick={() => setOpen(row)}
        identity={{ kind: "avatar", name: row.name, seed: String(row.id) }}
        meta={<>/o/{row.slug}{row.submitted_by ? ` · ${row.submitted_by}` : ""} · <RelativeTime date={row.created_at} /></>}
        right={<StatusPill label={reviewStatusLabels()[row.review_status] ?? row.review_status} tone={reviewStatusTone(row.review_status)} />} /></li>)}</ul>}
    <PagePager page={page} setPage={setPage} count={queue.data?.count} disabled={queue.isFetching} />
    {open ? <OrganizationReviewDrawer key={open.id} row={open} onClose={() => setOpen(null)} /> : null}
  </div>;
}
