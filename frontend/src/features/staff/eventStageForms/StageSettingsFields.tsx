import { Field } from "../../../components/ui/Field";
import { localDateTime, utcInstant } from "../../events/stagedForms/formPayload";
import type { StageSettings } from "./types";
import { CommaListField } from "../../events/stagedForms/CommaListField";

export function defaultStageSettings(): StageSettings {
  return { title: "", slug: "", stage: "application", activation_point: "", opening_mode: "trigger", opens_at: null, opening_offset_seconds: null,
    due_mode: "after_trigger", due_at: null, due_after_seconds: 604800, due_event_offset_seconds: null,
    reminder_offsets: [-604800, -86400], required: false, missed_action: "none", blocked_actions: [], lock_on_next_stage: true,
    audience: { roles: [], track_ids: [], travel_requested: null } };
}
export function StageSettingsFields({ value, onChange, canBlock }: { value: StageSettings; onChange: (value: StageSettings) => void; canBlock: boolean }) {
  const change = <K extends keyof StageSettings>(key: K, next: StageSettings[K]) => onChange({ ...value, [key]: next });
  const date = (key: "opens_at" | "due_at", label: string) => <Field label={label}><input className="desk-input" type="datetime-local" required value={localDateTime(value[key])} onChange={event => change(key, event.target.value ? utcInstant(event.target.value) : null)} /></Field>;
  return <section className="grid gap-5" aria-label="Stage settings">
    <div className="grid gap-4 md:grid-cols-2"><Field label="Title"><input className="desk-input" required maxLength={200} value={value.title} onChange={event => change("title", event.target.value)} /></Field>
      <Field label="Slug"><input className="desk-input" required maxLength={64} pattern="[a-zA-Z0-9_-]+" value={value.slug} onChange={event => change("slug", event.target.value)} /></Field></div>
    <Field label="Stage"><select className="desk-input" value={value.stage} onChange={event => onChange({ ...value, stage: event.target.value as StageSettings["stage"], activation_point: event.target.value === "accepted_rsvp" ? "accepted" : "" })}>
      {["application", "shortlisted", "accepted_rsvp", "pre_event", "post_event"].map(stage => <option key={stage} value={stage}>{stage.replace(/_/g, " ")}</option>)}</select></Field>
    {value.stage === "accepted_rsvp" ? <Field label="Activation point"><select className="desk-input" value={value.activation_point} onChange={event => change("activation_point", event.target.value as StageSettings["activation_point"])}><option value="accepted">Accepted</option><option value="rsvp">RSVP confirmed</option></select></Field> : null}
    <p className="text-sm text-muted">Forms open only after their trigger and audience match. A checklist milestone does not change admission or registration.</p>
    <Field label="Opening schedule"><select className="desk-input" value={value.opening_mode} onChange={event => onChange({ ...value, opening_mode: event.target.value as StageSettings["opening_mode"], opens_at: null, opening_offset_seconds: ["event_start", "event_end"].includes(event.target.value) ? 0 : null })}>
      {["trigger", "absolute", "event_start", "event_end"].map(mode => <option key={mode} value={mode}>{mode.replace(/_/g, " ")}</option>)}</select></Field>
    {value.opening_mode === "absolute" ? date("opens_at", "Opens at (your local time)") : value.opening_mode !== "trigger" ? <Field label="Opening offset in seconds" hint="Negative opens before the event time; positive opens after."><input className="desk-input" type="number" required min={-31536000} max={31536000} value={value.opening_offset_seconds ?? ""} onChange={event => change("opening_offset_seconds", event.target.valueAsNumber)} /></Field> : null}
    <Field label="Deadline schedule"><select className="desk-input" value={value.due_mode} onChange={event => onChange({ ...value, due_mode: event.target.value as StageSettings["due_mode"], due_at: null, due_after_seconds: event.target.value === "after_trigger" ? 604800 : null, due_event_offset_seconds: ["event_start", "event_end"].includes(event.target.value) ? 0 : null })}>
      {["absolute", "after_trigger", "event_start", "event_end"].map(mode => <option key={mode} value={mode}>{mode.replace(/_/g, " ")}</option>)}</select></Field>
    {value.due_mode === "absolute" ? date("due_at", "Due at (your local time)") : <Field label={value.due_mode === "after_trigger" ? "Seconds after trigger" : "Deadline offset in seconds"}>
      <input className="desk-input" type="number" required min={value.due_mode === "after_trigger" ? 1 : -31536000} max={31536000} value={(value.due_mode === "after_trigger" ? value.due_after_seconds : value.due_event_offset_seconds) ?? ""}
        onChange={event => change(value.due_mode === "after_trigger" ? "due_after_seconds" : "due_event_offset_seconds", event.target.valueAsNumber)} /></Field>}
    <CommaListField label="Reminder offsets in seconds" hint="Comma separated; at most 10 offsets relative to the due time. Negative values remind before it." values={value.reminder_offsets} pattern="\s*-?[0-9]+(?:\s*,\s*-?[0-9]+)*\s*" onChange={parts => change("reminder_offsets", parts.map(Number))} />
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.required} onChange={event => change("required", event.target.checked)} />Required form</label>
    <Field label="Missed deadline action"><select className="desk-input" value={value.missed_action} onChange={event => onChange({ ...value, missed_action: event.target.value as StageSettings["missed_action"], blocked_actions: event.target.value === "block" ? value.blocked_actions : [] })}>
      <option value="none">No later action restriction</option><option value="warn">Warn participant</option><option value="block" disabled={!canBlock}>Block configured later actions</option></select></Field>
    {value.missed_action === "block" ? <fieldset disabled={!canBlock}><legend>Require completion before</legend>{["rsvp", "check_in", "claim_submit"].map(action => <label key={action} className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.blocked_actions.includes(action)} onChange={event => change("blocked_actions", event.target.checked ? [...value.blocked_actions, action] : value.blocked_actions.filter(item => item !== action))} />{action.replace(/_/g, " ")}</label>)}</fieldset> : null}
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.lock_on_next_stage} onChange={event => change("lock_on_next_stage", event.target.checked)} />Lock answers when the next stage opens</label>
    <CommaListField label="Audience roles" hint="Comma separated role keys; empty means no role filter." values={value.audience.roles} onChange={parts => change("audience", { ...value.audience, roles: parts })} />
    <CommaListField label="Audience track IDs" hint="Comma separated positive IDs for this event; empty means no track filter." values={value.audience.track_ids} pattern="\s*[1-9][0-9]*(?:\s*,\s*[1-9][0-9]*)*\s*" onChange={parts => change("audience", { ...value.audience, track_ids: parts.map(Number) })} />
    <Field label="Travel request audience"><select className="desk-input" value={value.audience.travel_requested === null ? "all" : String(value.audience.travel_requested)} onChange={event => change("audience", { ...value.audience, travel_requested: event.target.value === "all" ? null : event.target.value === "true" })}><option value="all">Everyone matching other filters</option><option value="true">Travel support requested</option><option value="false">No travel support requested</option></select></Field>
  </section>;
}
