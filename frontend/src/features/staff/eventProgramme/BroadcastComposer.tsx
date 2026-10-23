import { useEffect, useRef, useState } from "react";
import { Card } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { useBroadcastCreate, type BroadcastCampaign, type BroadcastCta, type BroadcastDraft } from "./broadcastApi";
import { isProtectedDenial } from "./sessionScope";

export function BroadcastComposer({ makerspaceId, eventId, initial, onSaved }: { makerspaceId: number; eventId: number; initial?: BroadcastDraft; onSaved: (campaign: BroadcastCampaign) => void }) {
  const [draft, setDraft] = useState<BroadcastDraft>(initial ?? { subject: "", body: "", statuses: ["registered", "attended"], attendance: "any", render_schema_version: 2, design: "classic", ctas: [] });
  const create = useBroadcastCreate(makerspaceId, eventId);
  const lastAttempt = useRef({ digest: "", id: "" });
  const denied = isProtectedDenial(create.error);
  useEffect(() => { if (denied) { setDraft({ subject: "", body: "", statuses: [], attendance: "any", render_schema_version: 2, design: "classic", ctas: [] }); lastAttempt.current = { digest: "", id: "" }; } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">Broadcast composition is no longer available for your access.</p>;
  const patch = (value: Partial<BroadcastDraft>) => setDraft({ ...draft, ...value });
  const updateCta = (index: number, value: BroadcastCta) => patch({ ctas: draft.ctas.map((item, i) => i === index ? value : item) });
  return <Card><form className="grid gap-4" onSubmit={e => { e.preventDefault(); const digest = JSON.stringify(draft); if (lastAttempt.current.digest !== digest) lastAttempt.current = { digest, id: crypto.randomUUID() }; create.mutate({ operation_id: lastAttempt.current.id, draft }, { onSuccess: onSaved }); }}>
    <label className="grid gap-1 text-sm font-semibold">Start with<select className="desk-input font-normal" defaultValue="" onChange={e => {
      if (e.target.value === "reminder") patch({ subject: "See you at {{ event_title }}", body: "We look forward to welcoming you. Check your ticket before you travel.", statuses: ["registered"], attendance: "not_attended" });
      if (e.target.value === "thanks") patch({ subject: "Thank you for joining {{ event_title }}", body: "Thanks for sharing your time and ideas with our community.", statuses: ["attended"], attendance: "attended" });
    }}><option value="">Blank message</option><option value="reminder">Before the event · registered guests</option><option value="thanks">After the event · attendees</option></select></label>
    <label className="grid gap-1 text-sm font-semibold">Subject<input className="desk-input font-normal" required maxLength={200} value={draft.subject} onChange={e => patch({ subject: e.target.value })} /></label>
    <label className="grid gap-1 text-sm font-semibold">Message<textarea className="desk-input min-h-32 font-normal" required maxLength={10000} value={draft.body} onChange={e => patch({ body: e.target.value })} /></label>
    <p className="text-xs text-muted">Simple Markdown text. Placeholders: {"{{ name }}, {{ event_title }}, {{ event_date }}, {{ event_location }}, {{ ticket_url }}"}.</p>
    <label className="grid gap-1 text-sm">Brand design<select className="desk-input" value={draft.design} onChange={e => patch({ design: e.target.value as BroadcastDraft["design"] })}>{["classic", "bold", "minimal"].map(design => <option key={design}>{design}</option>)}</select></label>
    <fieldset className="grid gap-2"><legend className="mb-2 text-sm font-semibold">Calls to action · up to three</legend>{draft.ctas.map((cta, index) => <div key={index} className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">Button label<input className="desk-input" required maxLength={80} value={cta.label} onChange={e => updateCta(index, { ...cta, label: e.target.value })} /></label>
      <label className="grid gap-1 text-sm">Destination type<select className="desk-input" value={cta.kind} onChange={e => updateCta(index, e.target.value === "https" ? { kind: "https", label: cta.label, url: "https://" } : { kind: "navigation", label: cta.label, target: "event" })}><option value="navigation">Event or ticket</option><option value="https">HTTPS link</option></select></label>
      {cta.kind === "https" ? <label className="grid gap-1 text-sm">HTTPS URL<input className="desk-input" type="url" pattern="https://.*" required maxLength={2048} value={cta.url} onChange={e => updateCta(index, { ...cta, url: e.target.value })} /></label> : <label className="grid gap-1 text-sm">Page<select className="desk-input" value={cta.target} onChange={e => updateCta(index, { ...cta, target: e.target.value as "event" | "ticket" })}><option value="event">Event</option><option value="ticket">My ticket</option></select></label>}
      <button className="desk-button" type="button" onClick={() => patch({ ctas: draft.ctas.filter((_, i) => i !== index) })}>Remove button</button>
    </div>)}<button className="desk-button justify-self-start" type="button" disabled={draft.ctas.length >= 3} onClick={() => patch({ ctas: [...draft.ctas, { kind: "navigation", label: "View event", target: "event" }] })}>Add button</button></fieldset>
    <fieldset className="grid gap-2 sm:grid-cols-3"><legend className="mb-2 text-sm font-semibold">Registration states</legend>{["registered", "attended", "pending_approval", "waitlisted", "rejected", "cancelled"].map(status => <label key={status} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={draft.statuses.includes(status)} onChange={e => patch({ statuses: e.target.checked ? [...draft.statuses, status] : draft.statuses.filter(item => item !== status) })} />{status.replace(/_/g, " ")}</label>)}</fieldset>
    <label className="grid gap-1 text-sm">Attendance<select className="desk-input" value={draft.attendance} onChange={e => patch({ attendance: e.target.value })}><option value="any">Any</option><option value="attended">Attended</option><option value="not_attended">Not attended</option></select></label>
    {create.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(create.error)}</p> : null}
    <button className="desk-button-primary justify-self-end" type="submit" disabled={create.isPending || !draft.statuses.length}>{create.isPending ? "Saving…" : "Save draft"}</button>
  </form></Card>;
}
