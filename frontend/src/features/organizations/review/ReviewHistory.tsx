import { t } from "@lingui/core/macro";
import { ErrorText, RelativeTime, Skeleton } from "../../../components/ui";
import type { SessionContext } from "../../../lib/api/sessionContext";
import { reviewActionLabels, useReviewHistory } from "./reviewApi";

/** The append-only review trail, newest first: what happened, when, and the reviewer's words. */
export function ReviewHistory({ organizationId, context, headingId }: { organizationId: number; context?: SessionContext; headingId: string }) {
  const history = useReviewHistory(organizationId, true, context);
  return <section aria-labelledby={headingId} className="grid gap-2">
    <h3 id={headingId} className="title-panel">{t`Review history`}</h3>
    {history.isLoading ? <Skeleton className="h-16 w-full" />
      : history.isError ? <ErrorText resource={t`the review history`} onRetry={() => { void history.refetch(); }} />
      : !history.data?.length ? <p className="text-sm text-muted">{t`No review steps yet.`}</p>
      : <ol className="grid gap-3">{history.data.map(entry => <li key={entry.id} className="rounded-xl border border-line p-3 text-sm">
        <p className="font-semibold text-ink">{reviewActionLabels()[entry.action] ?? entry.action} · <RelativeTime date={entry.created_at} /></p>
        {entry.reason ? <p className="mt-1 whitespace-pre-wrap text-ink">{entry.reason}</p> : null}
      </li>)}</ol>}
  </section>;
}
