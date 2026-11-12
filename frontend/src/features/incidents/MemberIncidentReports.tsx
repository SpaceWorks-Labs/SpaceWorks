import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ListRow, Pagination, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import {
  incidentErrorMessage, KIND_LABELS, SEVERITY_LABELS, severityTone, STATUS_LABELS, statusTone, useMyIncidents, useReportIncident,
} from "./api";
import { draftBody, emptyDraft, IncidentFields } from "./IncidentFields";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

/** The member's "Report a safety incident" form and their own reports (`safety.incidents`).
 *  The member reads only what they filed; staff triage notes stay on the staff side. */
export function MemberIncidentReports({ makerspaceId }: { makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState(emptyDraft);
  const [open, setOpen] = useState(false);
  const mine = useMyIncidents(makerspaceId, page);
  const report = useReportIncident(makerspaceId);
  const rows = mine.data?.results ?? [];
  return <section aria-labelledby="member-incidents-title" className="desk-panel grid gap-4 p-4 sm:p-5">
    <div className="grid gap-1">
      <h2 id="member-incidents-title" className="title-panel">{t`Report a safety incident`}</h2>
      <p className="text-sm text-muted">{t`Something went wrong, or nearly did? Tell the staff. Near misses count too: reporting them is how the next accident is prevented, and nobody gets into trouble for it.`}</p>
    </div>
    {report.isSuccess && !open ? <p role="status" className="text-sm text-success-ink">{t`Thank you. Your report reached the staff.`}</p> : null}
    {open ? <form className="grid gap-4" onSubmit={event => {
      event.preventDefault();
      if (!draft.title.trim() || report.isPending) return;
      report.mutate(draftBody(draft), { onSuccess: () => { setDraft(emptyDraft()); setOpen(false); setPage(1); } });
    }}>
      <IncidentFields draft={draft} onChange={patch => setDraft(current => ({ ...current, ...patch }))}
        linkHint={t`If it involved one of your loans or bookings, or a machine or event, add its number. You can only link your own loans and bookings.`} />
      {report.error ? <p role="alert" className="text-sm text-danger">{incidentErrorMessage(report.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={() => setOpen(false)}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-brand" disabled={!draft.title.trim() || report.isPending}>
          {report.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send report`}</button>
      </div>
    </form> : <button type="button" className="desk-button-brand justify-self-start" onClick={() => { report.reset(); setOpen(true); }}>
      {t`Report an incident or near miss`}</button>}
    <h3 className="title-section">{t`Your reports`}</h3>
    {mine.isLoading ? <LogoLoader label={t`Loading your reports…`} size={48} className="min-h-16 py-3" />
      : mine.error ? <div role="alert" className="grid justify-items-start gap-2 text-sm text-danger"><p>{incidentErrorMessage(mine.error)}</p>
        <button type="button" className="desk-button" onClick={() => void mine.refetch()}>{t`Try again`}</button></div>
      : rows.length ? <div className="grid gap-3">{rows.map(row => <ListRow key={row.id} title={row.title}
        identity={{ kind: "icon", icon: row.kind === "near_miss" ? "ShieldAlert" : "TriangleAlert", tone: severityTone(row.severity) }}
        meta={[KIND_LABELS[row.kind], SEVERITY_LABELS[row.severity], formatDate(row.occurred_at)].join(" · ")}
        right={<StatusPill tone={statusTone(row.status)} label={STATUS_LABELS[row.status]} />} />)}</div>
      : <p className="text-sm text-muted">{t`You haven't reported anything here.`}</p>}
    {mine.data && mine.data.count > 24 ? <Pagination page={page} onChange={setPage} pageSize={24} count={mine.data.count}
      totalPages={Math.ceil(mine.data.count / 24)} /> : null}
  </section>;
}
