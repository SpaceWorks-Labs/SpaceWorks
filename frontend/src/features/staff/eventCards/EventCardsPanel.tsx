// Event ID cards and ticket design, for every organiser who can edit the event. Cards go to
// confirmed registrants automatically once the card design is published (and every 15 min).
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CardDesigner } from "../../../components/card-designer/CardDesigner";
import type { CardDesign } from "../../../components/card-designer/cardTypes";
import { Badge, ErrorBlock, OverflowMenu, SegmentedControl, Skeleton } from "../../../components/ui";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { CardJobList, JOB_LABELS, useStartCardJob } from "../../cards/cardJobs";
import { SheetPreviewDialog } from "../../cards/SheetPreviewDialog";
import { StaffPhotoDialog } from "../../cards/StaffPhotoDialog";
import { EventCardApproval } from "./EventCardApproval";

type EventCard = { id: number; registration: number | null; role: string; printed_name: string; status: "active" | "revoked";
  valid_until: string | null; issued_at: string; revoked_at: string | null; photo_set: boolean };
const ROLES = ["attendee", "speaker", "mentor", "judge", "volunteer", "crew"];

export function EventCardsPanel({ eventId, features }: { eventId: number; features: readonly string[] }) {
  const designs = useQuery({ queryKey: ["event-card-designs", eventId],
    queryFn: () => staffRequest<Partial<Record<"event_card" | "event_ticket", CardDesign>>>(`/admin/events/${eventId}/card-designs`) });
  const cardsOn = features.includes("events.id_cards");
  const [view, setView] = useState<"cards" | "design" | "ticket">(cardsOn ? "cards" : "ticket");
  if (designs.isLoading) return <Skeleton className="h-40 w-full" />;
  if (designs.isError || !designs.data) return <ErrorBlock error={designs.error} resource="event card designs" />;
  const options = [...(designs.data.event_card ? [{ value: "cards", label: "ID cards" }, { value: "design", label: "Card design" }] : []),
    ...(designs.data.event_ticket ? [{ value: "ticket", label: "Ticket design" }] : [])];
  if (!options.length) return null;
  const card = designs.data.event_card;
  const ticket = designs.data.event_ticket;
  return <section className="grid gap-4" aria-label="Event cards and tickets">
    <h3 className="text-lg font-semibold text-ink">Cards and tickets</h3>
    <SegmentedControl label="Cards and tickets" value={view} options={options} onChange={(value) => setView(value as typeof view)} />
    {view === "cards" && card ? <EventCardList eventId={eventId} published={Boolean(card.published_at)} /> : null}
    {view === "design" && card ? <>
      <EventCardApproval eventId={eventId} />
      <CardDesigner key={card.id} designId={card.id} canEdit={card.can_edit} title="Event card design" />
    </> : null}
    {view === "ticket" && ticket ? <>
      <EventCardApproval eventId={eventId} />
      <p className="text-sm text-muted">The published ticket is attached as a PDF to each confirmation email.</p>
      <CardDesigner key={ticket.id} designId={ticket.id} canEdit={ticket.can_edit} title="Ticket design" />
    </> : null}
  </section>;
}

function EventCardList({ eventId, published }: { eventId: number; published: boolean }) {
  const client = useQueryClient();
  const key = ["event-id-cards", eventId];
  const cards = useQuery({ queryKey: key, queryFn: () => staffRequest<EventCard[]>(`/admin/events/${eventId}/id-cards`) });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const issue = useMutation({ mutationFn: () => staffRequest<{ issued: number; revoked: number }>(`/admin/events/${eventId}/id-cards`, { method: "POST" }), onSuccess: refresh });
  const revoke = useMutation({ mutationFn: ({ id, reason }: { id: number; reason: string }) =>
    staffRequest(`/admin/event-id-cards/${id}/revoke`, { method: "POST", body: JSON.stringify({ reason }) }), onSuccess: refresh });
  const role = useMutation({ mutationFn: ({ id, value }: { id: number; value: string }) =>
    staffRequest(`/admin/event-id-cards/${id}`, { method: "PATCH", body: JSON.stringify({ role: value }) }), onSuccess: refresh });
  const jobsPath = `/admin/events/${eventId}/card-jobs`;
  const startJob = useStartCardJob(jobsPath);
  const [revoking, setRevoking] = useState<EventCard | null>(null);
  const [reason, setReason] = useState("");
  const [photoFor, setPhotoFor] = useState<EventCard | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [printRole, setPrintRole] = useState("");
  const [printCheckIn, setPrintCheckIn] = useState<"" | "in" | "out">("");
  const printFilter = { status: "active" as const, ...(printRole ? { roles: [printRole] } : {}),
    ...(printCheckIn ? { checked_in: printCheckIn === "in" } : {}) };
  const download = async (row: EventCard) => {
    const url = URL.createObjectURL(await staffRequestBlob(`/admin/event-id-cards/${row.id}/download?format=pdf`));
    Object.assign(document.createElement("a"), { href: url, download: `event-card-${row.id}.pdf` }).click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const rows = cards.data ?? [];
  return <div className="grid gap-3">
    {!published ? <p className="text-sm text-warn-ink">Publish the card design to start issuing cards.</p> : null}
    <div className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>Print for</span>
        <select className="desk-input min-h-11" value={printRole} onChange={(event) => setPrintRole(event.target.value)}>
          <option value="">Every role</option>
          {ROLES.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}s</option>)}
        </select></label>
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>Check-in</span>
        <select className="desk-input min-h-11" value={printCheckIn} onChange={(event) => setPrintCheckIn(event.target.value as typeof printCheckIn)}>
          <option value="">Everyone</option><option value="in">Checked in</option><option value="out">Not checked in yet</option>
        </select></label>
    </div>
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary min-h-11" disabled={!published || issue.isPending} onClick={() => issue.mutate()}>
        {issue.isPending ? "Issuing…" : "Issue cards now"}</button>
      <button type="button" className="desk-button min-h-11" disabled={!rows.length} onClick={() => setPreviewing(true)}>
        {JOB_LABELS.bulk_sheet}…</button>
      <button type="button" className="desk-button min-h-11" disabled={!rows.length} onClick={() => startJob.mutate({ kind: "zip", ...printFilter })}>
        {JOB_LABELS.zip}</button>
    </div>
    {issue.data ? <p role="status" className="text-sm text-muted">{issue.data.issued} issued, {issue.data.revoked} withdrawn.</p> : null}
    {[issue.error, revoke.error, role.error, startJob.error, cards.error].find(Boolean) ? <ErrorBlock error={[issue.error, revoke.error, role.error, startJob.error, cards.error].find(Boolean)} /> : null}
    <CardJobList listPath={jobsPath} />
    <SheetPreviewDialog open={previewing} onClose={() => setPreviewing(false)} filter={printFilter} jobsPath={jobsPath}
      previewPath={`${jobsPath}/preview`} title={printRole || printCheckIn ? "Print sheet: the chosen event cards" : "Print sheet: all active event cards"} />
    <StaffPhotoDialog holderName={photoFor?.printed_name ?? null} photoPath={`/admin/event-id-cards/${photoFor?.id}/photo`}
      onClose={() => setPhotoFor(null)} onSaved={() => { setPhotoFor(null); void refresh(); }} />
    {revoking ? <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault();
      revoke.mutate({ id: revoking.id, reason: reason.trim() }, { onSuccess: () => { setRevoking(null); setReason(""); } }); }}>
      <label className="grid flex-1 gap-1 text-xs font-semibold text-muted"><span>Why revoke {revoking.printed_name}'s card?</span>
        <input className="desk-input min-h-11" value={reason} maxLength={300} onChange={(event) => setReason(event.target.value)} /></label>
      <button type="submit" className="desk-button-danger min-h-11" disabled={reason.trim().length < 3 || revoke.isPending}>Revoke card</button>
      <button type="button" className="desk-button min-h-11" onClick={() => setRevoking(null)}>Cancel</button>
    </form> : null}
    <ul className="grid gap-2">
      {!rows.length && !cards.isLoading ? <li className="text-sm text-muted">No cards yet.</li> : null}
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-control border border-line bg-panel p-3">
        <span className="min-w-0 flex-1 text-sm text-ink">{row.printed_name}</span>
        <select className="desk-input min-h-11" aria-label={`Role for ${row.printed_name}`} value={row.role} disabled={row.status !== "active"}
          onChange={(event) => role.mutate({ id: row.id, value: event.target.value })}>
          {ROLES.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select>
        <Badge tone={row.status === "active" ? "success" : "danger"}>{row.status === "active" ? "Active" : "Revoked"}</Badge>
        {row.status === "active" ? <OverflowMenu label={`Actions for ${row.printed_name}`} actions={[
          { label: "Download PDF", onClick: () => void download(row) },
          { label: row.photo_set ? "Replace photo" : "Take or upload photo", confirms: true, onClick: () => setPhotoFor(row) },
          { label: "Revoke", confirms: true, tone: "danger", onClick: () => { setReason(""); setRevoking(row); } }]} /> : null}
      </li>)}
    </ul>
  </div>;
}
