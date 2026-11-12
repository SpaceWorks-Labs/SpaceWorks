import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ListRow, Pagination, SegmentedControl, StatusPill } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { OUTCOME_LABELS } from "../bookings/DepartureForm";
import { opsQueryState } from "./opsPresentation";
import { useBookingIssues, useResolveIssue, type BookingIssue } from "./bookingQueueApi";
import { BoxArt } from "../../components/BoxSpinner";

/** Check-out issues (damaged, left early, something wrong), for one space or the whole makerspace. */
export function BookingIssuesList({ makerspaceId, spaceId, onOpenBooking }: {
  makerspaceId: number; spaceId?: number; onOpenBooking?: (issue: BookingIssue) => void;
}) {
  const [status, setStatus] = useState<"open" | "resolved" | "all">("open");
  const [page, setPage] = useState(1);
  const issues = useBookingIssues(makerspaceId, status, page, spaceId);
  const data = issues.data;
  return (
    <section aria-labelledby="booking-issues-title" className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="booking-issues-title" className="title-panel">{t`Issues `}<span className="tabular-nums">({data?.open_count ?? 0} open)</span></h2>
          <p className="mt-1 text-sm text-muted">{t`Raised when a booker or staff member reports a problem at check-out.`}</p>
        </div>
        <SegmentedControl label={t`Issue status`} value={status} onChange={value => { setStatus(value as typeof status); setPage(1); }}
          options={[{ value: "open", label: t`Open` }, { value: "resolved", label: t`Resolved` }, { value: "all", label: t`All` }]} />
      </div>
      <QueryContent state={opsQueryState(issues, "booking issues")} isEmpty={data?.results.length === 0}
        empty={{ message: status === "open" ? t`No open issues. Problems reported at check-out appear here.` : t`No issues match this filter.` }}>
        <ul className="grid gap-3">
          {data?.results.map(issue => <IssueRow key={issue.id} issue={issue} makerspaceId={makerspaceId} onOpenBooking={onOpenBooking} showSpace={!spaceId} />)}
        </ul>
        {data && data.count > 24 ? <Pagination page={page} pageSize={24} count={data.count} totalPages={Math.ceil(data.count / 24)} onChange={setPage} /> : null}
      </QueryContent>
    </section>
  );
}

function IssueRow({ issue, makerspaceId, onOpenBooking, showSpace }: {
  issue: BookingIssue; makerspaceId: number; onOpenBooking?: (issue: BookingIssue) => void; showSpace: boolean;
}) {
  const resolve = useResolveIssue(makerspaceId);
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(false);
  const when = new Date(issue.starts_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
  return (
    <li className="rounded-xl border border-line bg-panel">
      <ListRow title={`${OUTCOME_LABELS[issue.outcome]} · ${issue.booker_name}`} identity={{ kind: "icon", icon: "TriangleAlert", tone: issue.resolved_at ? "neutral" : "warn" }}
        meta={<>{showSpace ? `${issue.space_name} · ` : ""}{when} · {issue.source === "member" ? t`Reported by the booker` : t`Recorded by staff`}</>}
        right={<StatusPill label={issue.resolved_at ? t`Resolved` : t`Open`} tone={issue.resolved_at ? "success" : "warn"} />} />
      <div className="grid gap-3 px-4 pb-4">
        <p className="whitespace-pre-wrap text-sm">“{issue.remark}”</p>
        {issue.resolved_at ? <p className="text-sm text-muted">{t`Resolved ${new Date(issue.resolved_at).toLocaleString(formatLocale())}${issue.resolution_note ? ` — ${issue.resolution_note}` : ""}`}</p> : null}
        <div className="flex flex-wrap gap-2">
          {onOpenBooking ? <button type="button" className="desk-button-ghost min-h-11" onClick={() => onOpenBooking(issue)}>{t`Open booking`}</button> : null}
          {!issue.resolved_at && !open ? <button type="button" className="desk-button min-h-11" onClick={() => setOpen(true)}>{t`Resolve`}</button> : null}
        </div>
        {open ? <form className="grid gap-2" onSubmit={event => { event.preventDefault(); resolve.mutate({ id: issue.id, note }, { onSuccess: () => setOpen(false) }); }}>
          <label className="grid gap-1 text-sm">{t`What was done? (optional)`}<input className="desk-input" maxLength={500} value={note} onChange={event => setNote(event.target.value)} />
          </label>
          {resolve.error ? <p role="alert" className="text-sm text-danger">{resolve.error.message}</p> : null}
          <div className="flex gap-2">
            <button type="submit" className="desk-button-brand min-h-11" disabled={resolve.isPending}>{resolve.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Mark resolved`}</button>
            <button type="button" className="desk-button-ghost min-h-11" onClick={() => setOpen(false)}>{t`Not now`}</button>
          </div>
        </form> : null}
      </div>
    </li>
  );
}
