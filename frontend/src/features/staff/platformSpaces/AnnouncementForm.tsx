import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { severityLabels, useCreateAnnouncement, type AnnouncementBody, type AnnouncementSeverity } from "./announcementsApi";
import { SpacePicker, type PickedSpaces } from "./SpacePicker";
import { BoxArt } from "../../../components/BoxSpinner";

const EMPTY = { title: "", body: "", severity: "info" as AnnouncementSeverity, audience: "all_spaces" as AnnouncementBody["audience"],
  starts: "", ends: "", email: false, members: false };

function iso(local: string) {
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** Compose an announcement; with no start time it goes live now. */
export function AnnouncementForm() {
  const create = useCreateAnnouncement();
  const [form, setForm] = useState(EMPTY);
  const [spaces, setSpaces] = useState<PickedSpaces>({});
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) => setForm(current => ({ ...current, [key]: value }));
  const selectedIds = Object.keys(spaces).map(Number);
  const endsBeforeStart = Boolean(form.ends && iso(form.ends) && iso(form.ends)! <= (iso(form.starts) ?? new Date().toISOString()));
  const valid = form.title.trim() && form.body.trim() && (form.audience === "all_spaces" || selectedIds.length > 0) && !endsBeforeStart;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || create.isPending) return;
    create.mutate({ title: form.title.trim(), body: form.body.trim(), severity: form.severity, audience: form.audience,
      makerspace_ids: form.audience === "selected_spaces" ? selectedIds : [], starts_at: iso(form.starts) ?? new Date().toISOString(),
      ends_at: form.ends ? iso(form.ends) : null, send_email: form.email, show_to_members: form.members },
    { onSuccess: () => { toast(t`Announcement created.`); setForm(EMPTY); setSpaces({}); } });
  };
  return <form className="grid gap-4" aria-label={t`New announcement`} onSubmit={submit} noValidate>
    <Field label={t`Title`}><input className="desk-input" value={form.title} maxLength={120} onChange={event => set("title", event.target.value)} /></Field>
    <Field label={t`Message`} hint={`${form.body.length}/4000 characters.`}>
      <textarea className="desk-input min-h-28" value={form.body} maxLength={4000} onChange={event => set("body", event.target.value)} />
    </Field>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Kind`}>
        <select className="desk-input" value={form.severity} onChange={event => set("severity", event.target.value as AnnouncementSeverity)}>
          {(Object.entries(severityLabels()) as [AnnouncementSeverity, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </Field>
      <Field label={t`Audience`}>
        <select className="desk-input" value={form.audience} onChange={event => set("audience", event.target.value as AnnouncementBody["audience"])}>
          <option value="all_spaces">{t`Every space`}</option>
          <option value="selected_spaces">{t`Selected spaces`}</option>
        </select>
      </Field>
      <Field label={t`Starts`} hint={t`Leave empty to start now.`}><input className="desk-input" type="datetime-local" value={form.starts} onChange={event => set("starts", event.target.value)} /></Field>
      <Field label={t`Ends (optional)`} error={endsBeforeStart ? "The end must be after the start." : undefined}>
        <input className="desk-input" type="datetime-local" value={form.ends} onChange={event => set("ends", event.target.value)} />
      </Field>
    </div>
    {form.audience === "selected_spaces" ? <SpacePicker value={spaces} onChange={setSpaces} /> : null}
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={form.email} onChange={event => set("email", event.target.checked)} />{t`Also email the staff of these spaces`}</label>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={form.members} onChange={event => set("members", event.target.checked)} />{t`Show it to members too`}</label>
    {create.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(create.error)}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || create.isPending}>
      {create.isPending ? <><BoxArt size={16} mono />{t`Publishing…`}</> : t`Publish announcement`}
    </button>
  </form>;
}
