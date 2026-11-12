import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { ConfirmDialog, ErrorBlock, IconButton, SettingsRow, SettingsSection } from "../../../components/ui";
import type { TimelineKind } from "../publicProfileApi";
import { timelineRange } from "../profileFormat";
import { TIMELINE_COPY } from "../timelineCopy";
import { fieldError, useTimeline, useTimelineMutations, type TimelineEntry } from "./profileEditApi";
import { SectionToggle } from "./SectionToggle";
import { TimelineEntryForm } from "./TimelineEntryForm";
import { LogoLoader } from "../../../components/LogoLoader";

const KINDS: TimelineKind[] = ["experience", "education", "volunteering"];
type Editing = { kind: TimelineKind; entry?: TimelineEntry } | null;

/** Experience, education and volunteering. Each entry saves on its own through the timeline API. */
export function TimelineEditor() {
  const timeline = useTimeline();
  const { save, remove } = useTimelineMutations();
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<TimelineEntry | null>(null);
  const rows = timeline.data ?? [];
  const open = (next: Editing) => { save.reset(); setEditing(next); };
  return <SettingsSection title={t`Experience, education and volunteering`} description={t`Shown on your profile. Hide the whole section with its switch.`}>
    <SettingsRow label={t`Visibility`} helper={t`Volunteering follows the experience switch.`}>
      <div className="grid gap-1"><SectionToggle section="experience" label={t`Show experience and volunteering`} />
        <SectionToggle section="education" label={t`Show education`} /></div>
    </SettingsRow>
    {timeline.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" /> : null}
    {timeline.error ? <div className="py-4"><ErrorBlock error={new Error(t`Couldn't load your timeline. Try again.`)} onRetry={() => { void timeline.refetch(); }} /></div> : null}
    {!timeline.isLoading && !timeline.error ? KINDS.map(kind => {
      const copy = TIMELINE_COPY[kind];
      const entries = rows.filter(row => row.kind === kind);
      return <SettingsRow key={kind} label={copy.title} helper={entries.length ? undefined : copy.owner}>
        <div className="grid gap-3">
          {entries.length ? <ul className="grid gap-2">{entries.map(entry => <li key={entry.id} className="flex items-start justify-between gap-3 rounded-control border border-line p-3">
            <div className="min-w-0">
              <p className="break-words font-semibold text-ink">{entry.title}</p>
              <p className="text-sm text-muted">{[entry.organization, timelineRange(entry.start, entry.end)].filter(Boolean).join(" · ")}</p>
            </div>
            <div className="flex shrink-0 gap-1">
              <IconButton label={t`Edit ${entry.title}`} onClick={() => open({ kind, entry })}><Pencil aria-hidden="true" className="h-4 w-4" /></IconButton>
              <IconButton label={t`Delete ${entry.title}`} onClick={() => { remove.reset(); setDeleting(entry); }}><Trash2 aria-hidden="true" className="h-4 w-4" /></IconButton>
            </div>
          </li>)}</ul> : null}
          <button type="button" className="desk-button w-fit gap-2" onClick={() => open({ kind })}>
            <Plus aria-hidden="true" className="h-4 w-4" />{t`Add ${copy.title.toLowerCase()}`}</button>
        </div>
      </SettingsRow>;
    }) : null}
    {remove.error ? <p role="alert" className="py-3 text-sm text-danger">{fieldError(remove.error, "detail")}</p> : null}
    {editing ? <TimelineEntryForm key={editing.entry?.id ?? `new-${editing.kind}`} kind={editing.kind} entry={editing.entry}
      pending={save.isPending} error={save.error} onCancel={() => setEditing(null)}
      onSave={draft => save.mutate({ id: editing.entry?.id, draft }, { onSuccess: () => setEditing(null) })} /> : null}
    <ConfirmDialog open={Boolean(deleting)} tone="danger" title={t`Delete this entry?`} confirmLabel={t`Delete`}
      message={deleting ? t`"${deleting.title}" is removed from your profile and public page.` : ""} pending={remove.isPending}
      onCancel={() => setDeleting(null)} onConfirm={() => { if (deleting?.id !== undefined) remove.mutate(deleting.id, { onSettled: () => setDeleting(null) }); }} />
  </SettingsSection>;
}
