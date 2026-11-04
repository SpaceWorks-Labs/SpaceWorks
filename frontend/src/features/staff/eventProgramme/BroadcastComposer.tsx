import { useEffect, useRef, useState } from "react";
import { Card } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { useBroadcastCreate, useBroadcastTemplates, type BroadcastCampaign, type BroadcastCta, type BroadcastDraft } from "./broadcastApi";
import { AUTOSAVE_TEXT, useDraftAutosave } from "./broadcastAutosave";
import { isProtectedDenial } from "./sessionScope";
import { BroadcastDesignPicker } from "./BroadcastDesignPicker";
import { BroadcastTemplateGallery } from "./BroadcastTemplateGallery";

const PLACEHOLDER_HINT = ["name", "event_title", "event_date", "event_location", "ticket_url", "event_url", "schedule_url", "feedback_url", "organization"].map(key => `{{ ${key} }}`).join(", ");
const EMPTY: BroadcastDraft = { subject: "", body: "", statuses: ["registered", "attended"], attendance: "any", render_schema_version: 2, design: "classic", ctas: [] };

export function BroadcastComposer({ makerspaceId, eventId, initial, existing, onSaved }: { makerspaceId: number; eventId: number; initial?: BroadcastDraft; existing?: BroadcastCampaign; onSaved: (campaign: BroadcastCampaign) => void }) {
  const [draft, setDraft] = useState<BroadcastDraft>(existing ? { ...existing, render_schema_version: 2 } : initial ?? EMPTY);
  const [saved, setSaved] = useState<BroadcastCampaign | null>(existing ?? null);
  const create = useBroadcastCreate(makerspaceId, eventId);
  const templates = useBroadcastTemplates(makerspaceId, eventId);
  const autosave = useDraftAutosave(makerspaceId, eventId, saved, draft, row => { setSaved(row); onSaved(row); });
  const lastAttempt = useRef({ digest: "", id: "" });
  const denied = isProtectedDenial(create.error);
  const firstSave = !saved && !create.isPending && !create.isError && !!draft.subject.trim() && !!draft.body.trim() && draft.statuses.length > 0;
  // Autosave starts with the first complete subject and message; later edits PATCH the draft.
  useEffect(() => {
    if (!firstSave) return;
    const timer = setTimeout(submit, 2000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstSave, JSON.stringify(draft)]);
  useEffect(() => { if (denied) { setDraft({ ...EMPTY, statuses: [] }); setSaved(null); lastAttempt.current = { digest: "", id: "" }; } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">Broadcast composition is no longer available for your access.</p>;
  const patch = (value: Partial<BroadcastDraft>) => setDraft({ ...draft, ...value });
  const updateCta = (index: number, value: BroadcastCta) => patch({ ctas: draft.ctas.map((item, i) => i === index ? value : item) });
  const submit = () => {
    if (saved) { autosave.flush(); onSaved(saved); return; }
    const digest = JSON.stringify(draft);
    if (lastAttempt.current.digest !== digest) lastAttempt.current = { digest, id: crypto.randomUUID() };
    create.mutate({ operation_id: lastAttempt.current.id, draft }, { onSuccess: row => { setSaved(row); onSaved(row); } });
  };
  return <Card><form className="grid gap-4" onSubmit={e => { e.preventDefault(); submit(); }}>
    <BroadcastTemplateGallery templates={templates} onPick={template => patch({ subject: template.subject, body: template.body, statuses: template.statuses, attendance: template.attendance, design: template.design })} />
    <label className="grid gap-1 text-sm font-semibold">Subject<input className="desk-input font-normal" required maxLength={200} value={draft.subject} onChange={e => patch({ subject: e.target.value })} /></label>
    <label className="grid gap-1 text-sm font-semibold">Message<textarea className="desk-input min-h-32 font-normal" required maxLength={10000} value={draft.body} onChange={e => patch({ body: e.target.value })} /></label>
    <p className="text-xs text-muted">Simple Markdown text. Placeholders: {PLACEHOLDER_HINT}.</p>
    <BroadcastDesignPicker value={draft.design} extended={!!templates.data} onChange={design => patch({ design })} />
    <fieldset className="grid gap-2"><legend className="mb-2 text-sm font-semibold">Calls to action · up to three</legend>{draft.ctas.map((cta, index) => <div key={index} className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">Button label<input className="desk-input" required maxLength={80} value={cta.label} onChange={e => updateCta(index, { ...cta, label: e.target.value })} /></label>
      <label className="grid gap-1 text-sm">Destination type<select className="desk-input" value={cta.kind} onChange={e => updateCta(index, e.target.value === "https" ? { kind: "https", label: cta.label, url: "https://" } : { kind: "navigation", label: cta.label, target: "event" })}><option value="navigation">Event or ticket</option><option value="https">HTTPS link</option></select></label>
      {cta.kind === "https" ? <label className="grid gap-1 text-sm">HTTPS URL<input className="desk-input" type="url" pattern="https://.*" required maxLength={2048} value={cta.url} onChange={e => updateCta(index, { ...cta, url: e.target.value })} /></label> : <label className="grid gap-1 text-sm">Page<select className="desk-input" value={cta.target} onChange={e => updateCta(index, { ...cta, target: e.target.value as "event" | "ticket" })}><option value="event">Event</option><option value="ticket">My ticket</option></select></label>}
      <button className="desk-button" type="button" onClick={() => patch({ ctas: draft.ctas.filter((_, i) => i !== index) })}>Remove button</button>
    </div>)}<button className="desk-button justify-self-start" type="button" disabled={draft.ctas.length >= 3} onClick={() => patch({ ctas: [...draft.ctas, { kind: "navigation", label: "View event", target: "event" }] })}>Add button</button></fieldset>
    <fieldset className="grid gap-2 sm:grid-cols-3"><legend className="mb-2 text-sm font-semibold">Registration states</legend>{["registered", "attended", "pending_approval", "waitlisted", "rejected", "cancelled"].map(status => <label key={status} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={draft.statuses.includes(status)} onChange={e => patch({ statuses: e.target.checked ? [...draft.statuses, status] : draft.statuses.filter(item => item !== status) })} />{status.replace(/_/g, " ")}</label>)}</fieldset>
    <label className="grid gap-1 text-sm">Attendance<select className="desk-input" value={draft.attendance} onChange={e => patch({ attendance: e.target.value })}><option value="any">Any</option><option value="attended">Attended</option><option value="not_attended">Not attended</option></select></label>
    {create.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(create.error)}</p> : null}
    <div className="flex flex-wrap items-center justify-end gap-3">
      {saved ? <p role="status" aria-live="polite" className={`text-sm ${autosave.state === "conflict" || autosave.state === "error" ? "text-danger" : "text-muted"}`}>{AUTOSAVE_TEXT[autosave.state] || "Changes save automatically."}</p> : null}
      <button className="desk-button-primary" type="submit" disabled={create.isPending || !draft.statuses.length}>{create.isPending ? "Saving…" : saved ? "Save and review" : "Save draft"}</button>
    </div>
  </form></Card>;
}
