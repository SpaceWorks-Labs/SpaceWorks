import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Image as ImageIcon, RotateCcw, Ban } from "lucide-react";
import { ConfirmDialog, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { CERTIFICATE_KINDS } from "./designer/samples";
import { savePng, useIssued, type IssuedRow } from "./issueApi";
import { EventPanelPager } from "../EventPanelPager";

const REASONS = [{ value: "staff_revoked", label: t`Withdrawn by organisers` }, { value: "attendance_corrected", label: t`Records corrected` },
  { value: "event_cancelled", label: t`Event cancelled` }];
const TONES: Record<string, "success" | "info" | "danger" | "neutral"> = { active: "success", pending: "info", rendering: "info", failed: "neutral", revoked: "danger" };

function Row({ row, eventId, onChanged }: { row: IssuedRow; eventId: number; onChanged: () => void }) {
  const [reason, setReason] = useState("staff_revoked");
  const [confirming, setConfirming] = useState(false);
  const act = useMutation({ mutationFn: async (action: "download" | "png" | "revoke" | "reissue") => {
    if (action === "png") return savePng(eventId, row);
    if (action === "download") {
      const result = await staffRequest<{ url: string }>(`/admin/event-certificates/${row.id}/download/`);
      window.location.assign(result.url); return;
    }
    await staffRequest(`/admin/event-certificates/${row.id}/${action}/`, { method: "POST", body: JSON.stringify(action === "revoke" ? { reason } : {}) });
  }, onSuccess: (_value, action) => { if (action === "revoke" || action === "reissue" || action === "download") onChanged(); } });
  return <li className="grid gap-2 rounded-control border border-line p-3">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0"><p className="font-semibold text-ink">{row.recipient_name}</p>
        <p className="text-sm text-muted">{t`${row.kind_title}${row.award ? ` · ${row.award}` : ""} · issued ${new Date(row.issued_at).toLocaleDateString(formatLocale())} · revision ${row.revision}`}</p></div>
      <StatusPill label={row.status === "revoked" ? t`Revoked` : row.status === "active" ? t`Issued` : row.status === "failed" ? t`Failed` : t`Preparing`} tone={TONES[row.status] ?? "neutral"} />
    </div>
    <div className="flex flex-wrap items-center gap-2">
      {row.status !== "revoked" ? <button type="button" className="desk-button" disabled={act.isPending} onClick={() => act.mutate("download")}>
        <FileText size={16} aria-hidden="true" />{row.status === "active" ? "PDF" : t`Prepare PDF`}</button> : null}
      {row.status === "active" ? <button type="button" className="desk-button" disabled={act.isPending} onClick={() => act.mutate("png")}><ImageIcon size={16} aria-hidden="true" />PNG</button> : null}
      {row.status === "active" ? <>
        <label className="sr-only" htmlFor={`reason-${row.id}`}>{t`Reason for revoking ${row.recipient_name}'s certificate`}</label>
        <select id={`reason-${row.id}`} className="desk-input min-h-11 w-auto" value={reason} onChange={(event) => setReason(event.target.value)}>
          {REASONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
        <button type="button" className="desk-button-danger" disabled={act.isPending} onClick={() => setConfirming(true)}>
          <Ban size={16} aria-hidden="true" />{t`Revoke`}</button></> : null}
      {row.status === "revoked" ? <button type="button" className="desk-button-success" disabled={act.isPending} onClick={() => act.mutate("reissue")}><RotateCcw size={16} aria-hidden="true" />{t`Reissue`}</button> : null}
    </div>
    {act.error ? <p role="alert" className="text-sm text-danger">{act.error.message}</p> : null}
    <ConfirmDialog open={confirming} tone="danger" title={t`Revoke this certificate?`} confirmLabel={t`Revoke`}
      message={t`Revoke ${row.recipient_name}'s certificate? The verification page will show it as withdrawn.`}
      onCancel={() => setConfirming(false)} onConfirm={() => { setConfirming(false); act.mutate("revoke"); }} />
  </li>;
}

/** Every certificate issued for the event, by kind, with download, PNG, revoke (with a reason) and reissue. */
export function IssuedCertificatesList({ eventId }: { eventId: number }) {
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState("");
  const client = useQueryClient();
  const query = useIssued(eventId, page, kind);
  return <section className="grid gap-3" aria-labelledby="issued-certificates">
    <div className="flex flex-wrap items-end justify-between gap-2">
      <h4 id="issued-certificates" className="font-semibold text-ink">{t`Issued certificates${query.data ? ` (${query.data.count})` : ""}`}</h4>
      <label className="grid gap-1 text-sm">{t`Kind`}<select className="desk-input" value={kind} onChange={(event) => { setKind(event.target.value); setPage(1); }}>
        <option value="">{t`All kinds`}</option>{CERTIFICATE_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
    </div>
    {query.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading issued certificates…`}</p> : null}
    {query.error ? <p role="alert" className="text-sm text-danger">{query.error.message}</p> : null}
    {query.data && !query.data.results.length ? <p className="text-sm text-muted">{t`Nothing issued yet.`}</p> : null}
    <ul className="grid gap-2">{query.data?.results.map((row) => <Row key={row.id} row={row} eventId={eventId}
      onChanged={() => { void client.invalidateQueries({ queryKey: ["events", "credentials", eventId, "issued"] }); }} />)}</ul>
    {query.data ? <EventPanelPager page={page} setPage={setPage} count={query.data.count} next={query.data.next} /> : null}
  </section>;
}
