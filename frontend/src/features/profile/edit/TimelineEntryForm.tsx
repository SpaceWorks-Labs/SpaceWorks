import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Modal } from "../../../components/ui";
import type { TimelineKind } from "../publicProfileApi";
import { TIMELINE_COPY } from "../ProfileSectionTabs";
import { fieldError, type TimelineDraft, type TimelineEntry } from "./profileEditApi";

const PLACEHOLDERS: Record<TimelineKind, { title: string; organization: string }> = {
  experience: { title: t`Role, e.g. Hardware intern`, organization: "Company or team" },
  education: { title: t`Qualification, e.g. B.Tech, Electronics`, organization: "School or university" },
  volunteering: { title: t`Role, e.g. Workshop mentor`, organization: "Organisation or community" },
};

export function blankDraft(kind: TimelineKind): TimelineDraft {
  return { kind, title: "", organization: "", location: "", start: "", end: null, description: "", order: 0 };
}

/** One add/edit dialog for every timeline kind. Dates are calendar dates; an empty end means ongoing. */
export function TimelineEntryForm({ entry, kind, pending, error, onCancel, onSave }: {
  entry?: TimelineEntry; kind: TimelineKind; pending: boolean; error: unknown;
  onCancel: () => void; onSave: (draft: TimelineDraft) => void;
}) {
  const [draft, setDraft] = useState<TimelineDraft>(() => entry ? { ...entry } : blankDraft(kind));
  const set = (changes: Partial<TimelineDraft>) => setDraft(current => ({ ...current, ...changes }));
  const backwards = Boolean(draft.end && draft.start && draft.end < draft.start);
  const ready = draft.title.trim() !== "" && draft.start !== "" && !backwards;
  const copy = TIMELINE_COPY[kind];
  const id = (field: string) => `timeline-${field}`;
  const submit = () => { if (ready) onSave({ ...draft, title: draft.title.trim(), end: draft.end || null }); };
  return <Modal open onClose={onCancel} title={`${entry ? "Edit" : "Add"} ${copy.title.toLowerCase()}`} footer={
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={onCancel}>{t`Cancel`}</button>
      <button type="submit" form="timeline-entry-form" className="desk-button-primary w-full sm:w-auto" disabled={!ready || pending}>{pending ? t`Saving…` : t`Save`}</button>
    </div>}>
    <form id="timeline-entry-form" className="grid gap-4" onSubmit={event => { event.preventDefault(); submit(); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id("title")}>{t`Title`}<input id={id("title")} className="desk-input font-normal" required maxLength={200} placeholder={PLACEHOLDERS[kind].title}
          value={draft.title} onChange={event => set({ title: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id("organization")}>{t`Organisation`}<input id={id("organization")} className="desk-input font-normal" maxLength={200} placeholder={PLACEHOLDERS[kind].organization}
          value={draft.organization} onChange={event => set({ organization: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id("location")}>{t`Location`}<input id={id("location")} className="desk-input font-normal" maxLength={200} value={draft.location}
          onChange={event => set({ location: event.target.value })} /></label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id("start")}>{t`Start date`}<input id={id("start")} type="date" className="desk-input font-normal" required value={draft.start}
            onChange={event => set({ start: event.target.value })} /></label>
        <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id("end")}>{t`End date`}<input id={id("end")} type="date" className="desk-input font-normal" value={draft.end ?? ""} min={draft.start || undefined}
            aria-describedby={id("end-hint")} aria-invalid={backwards || undefined} onChange={event => set({ end: event.target.value || null })} />
          <span id={id("end-hint")} className={`text-xs font-normal ${backwards ? "text-danger" : "text-muted"}`}>
            {backwards ? t`End must be on or after the start.` : t`Leave empty if it's ongoing.`}</span></label>
      </div>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id("description")}>{t`Description`}<textarea id={id("description")} className="desk-input font-normal" rows={3} maxLength={4000} value={draft.description}
          onChange={event => set({ description: event.target.value })} /></label>
      {error ? <p role="alert" className="text-sm text-danger">{fieldError(error, "end")}</p> : null}
    </form>
  </Modal>;
}
