// Programme settings: name, description, number prefix, validity, approval, joining, photo
// mode, the public check page, and the join-form questions (placement front/back/hidden).
import { useState } from "react";

import { ErrorBlock } from "../../../components/ui";
import { useUpdateProgramme, type Programme, type Question } from "./api";

// Saved details that may fill a join answer (backend id_programmes/prefill.py PREFILL_KEYS):
// never date of birth, emergency contact, dietary or access needs, the resume or skills.
const SAVED_DETAILS: [string, string][] = [["", "Nothing (typed by hand)"], ["name", "Name"], ["phone", "Phone"],
  ["institution", "Institution"], ["organization", "Organisation"], ["study_level", "Study level"], ["country", "Country"],
  ["shirt_size", "T-shirt size"], ["github_url", "GitHub link"], ["linkedin_url", "LinkedIn link"], ["portfolio_url", "Portfolio link"]];

export function ProgrammeSettings({ programme }: { programme: Programme }) {
  const update = useUpdateProgramme(programme.id);
  const [draft, setDraft] = useState<Programme>(programme);
  const set = <K extends keyof Programme>(key: K, value: Programme[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const setQuestion = (index: number, patch: Partial<Question>) =>
    set("form_schema", draft.form_schema.map((question, i) => (i === index ? { ...question, ...patch } : question)));
  const input = "desk-input min-h-11";
  const label = "grid gap-1 text-xs font-semibold text-muted";

  return <form className="grid max-w-2xl gap-4" onSubmit={(event) => {
    event.preventDefault();
    const { counts: _c, can_manage: _m, id: _i, organization: _o, organization_slug: _s, makerspace: _k, slug: _g,
      next_sequence: _n, created_at: _a, updated_at: _u, ...patch } = draft;
    update.mutate(patch);
  }}>
    <label className={label}><span>Name</span><input className={input} value={draft.name} maxLength={80} onChange={(e) => set("name", e.target.value)} /></label>
    <label className={label}><span>Description (shown on the join page)</span>
      <textarea className="desk-input min-h-20" value={draft.description} onChange={(e) => set("description", e.target.value)} /></label>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className={label}><span>Status</span><select className={input} value={draft.status} onChange={(e) => set("status", e.target.value as Programme["status"])}>
        <option value="draft">Draft</option><option value="active">Open</option><option value="closed">Closed</option></select></label>
      <label className={label}><span>Number prefix (2-6 letters)</span>
        <input className={`${input} uppercase`} value={draft.id_prefix} maxLength={6} onChange={(e) => set("id_prefix", e.target.value.toUpperCase())} /></label>
      <label className={label}><span>Cards are valid</span>
        <select className={input} value={draft.validity_mode} onChange={(e) => set("validity_mode", e.target.value as Programme["validity_mode"])}>
          <option value="none">With no end date</option><option value="fixed_date">Until a date</option><option value="days">For a number of days</option></select></label>
      {draft.validity_mode === "fixed_date" ? <label className={label}><span>Until</span>
        <input className={input} type="date" value={draft.valid_until ?? ""} onChange={(e) => set("valid_until", e.target.value || null)} /></label> : null}
      {draft.validity_mode === "days" ? <label className={label}><span>Days from approval</span>
        <input className={input} type="number" min={1} max={3650} value={draft.validity_days ?? 365} onChange={(e) => set("validity_days", Number(e.target.value))} /></label> : null}
      <label className={label}><span>Photo</span><select className={input} value={draft.photo_mode} onChange={(e) => set("photo_mode", e.target.value as Programme["photo_mode"])}>
        <option value="none">No photo</option><option value="optional">Optional</option><option value="required">Required</option></select></label>
    </div>
    {([["registration_open", "Joining is open (needs the Open status)"], ["requires_approval", "New people need approval"],
      ["public_verify", "Public check page for these cards"]] as const).map(([key, text]) => <label key={key} className="flex min-h-11 items-center gap-2 text-sm text-ink">
      <input type="checkbox" className="h-5 w-5" checked={draft[key]} onChange={(e) => set(key, e.target.checked)} />{text}</label>)}
    <fieldset className="grid gap-3"><legend className="mb-1 text-sm font-semibold text-ink">Join-form questions</legend>
      {draft.form_schema.map((question, index) => <div key={index} className="grid gap-2 rounded-control border border-line p-3 sm:grid-cols-2">
        <label className={label}><span>Question</span><input className={input} value={question.label} maxLength={120}
          onChange={(e) => setQuestion(index, { label: e.target.value })} /></label>
        <label className={label}><span>Answer type</span><select className={input} value={question.type} onChange={(e) => setQuestion(index, { type: e.target.value as Question["type"] })}>
          <option value="text">Text</option><option value="choice">Choice</option><option value="email">Email</option><option value="phone">Phone</option></select></label>
        {question.type === "choice" ? <label className={`${label} sm:col-span-2`}><span>Options, one per line</span>
          <textarea className="desk-input min-h-20" value={(question.options ?? []).join("\n")}
            onChange={(e) => setQuestion(index, { options: e.target.value.split("\n").map((item) => item.trim()).filter(Boolean) })} /></label> : null}
        <label className={label}><span>On the card</span><select className={input} value={question.placement}
          onChange={(e) => setQuestion(index, { placement: e.target.value as Question["placement"] })}>
          <option value="hidden">Not printed</option><option value="front">Front</option><option value="back">Back</option></select></label>
        <label className={label}><span>Offer to fill from Saved details</span><select className={input} value={question.saved_details_key ?? ""}
          onChange={(e) => setQuestion(index, { saved_details_key: e.target.value })}>
          {SAVED_DETAILS.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>
        <div className="flex items-end gap-3">
          <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" className="h-5 w-5" checked={question.required}
            onChange={(e) => setQuestion(index, { required: e.target.checked })} />Required</label>
          <button type="button" className="desk-button-ghost min-h-11" onClick={() => set("form_schema", draft.form_schema.filter((_q, i) => i !== index))}>Remove</button>
        </div>
      </div>)}
      {draft.form_schema.length < 12 ? <div><button type="button" className="desk-button min-h-11" onClick={() => set("form_schema", [...draft.form_schema,
        { key: `q${Date.now().toString(36)}`, label: "", type: "text", required: false, placement: "hidden" }])}>Add a question</button></div> : null}
    </fieldset>
    {update.error ? <ErrorBlock error={update.error} /> : null}
    {update.isSuccess ? <p role="status" className="text-sm text-success">Saved.</p> : null}
    <div><button type="submit" className="desk-button-primary min-h-11" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save settings"}</button></div>
  </form>;
}
