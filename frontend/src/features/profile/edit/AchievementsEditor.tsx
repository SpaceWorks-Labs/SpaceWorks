import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Pencil, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { ConfirmDialog, ErrorBlock, IconButton, Modal, SettingsRow, SettingsSection } from "../../../components/ui";
import type { AccountProfile, SelfReportedAchievement } from "../accountProfileTypes";
import { verifiedSentence } from "../view/profileCopy";
import { useAchievementMutations, useAchievements, type AchievementDraft } from "./achievementsApi";
import { fieldError } from "./profileEditApi";
import { SectionToggle } from "./SectionToggle";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

const blank: AchievementDraft = { title: "", issuer: "", achieved_on: null, url: "", description: "", order: 0 };
const today = () => new Date().toISOString().slice(0, 10);

function AchievementForm({ entry, pending, error, onCancel, onSave }: {
  entry?: SelfReportedAchievement; pending: boolean; error: unknown; onCancel: () => void; onSave: (draft: AchievementDraft) => void;
}) {
  const [draft, setDraft] = useState<AchievementDraft>(() => entry ? { title: entry.title, issuer: entry.issuer, achieved_on: entry.achieved_on, url: entry.url, description: entry.description, order: entry.order } : blank);
  const set = (changes: Partial<AchievementDraft>) => setDraft(current => ({ ...current, ...changes }));
  const badUrl = draft.url.trim() !== "" && !/^https:\/\//i.test(draft.url.trim());
  const ready = draft.title.trim() !== "" && !badUrl;
  return <Modal open onClose={onCancel} title={entry ? t`Edit achievement` : t`Add an achievement`} footer={
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={onCancel}>{t`Cancel`}</button>
      <button type="submit" form="achievement-form" className="desk-button-primary w-full sm:w-auto" disabled={!ready || pending}>{pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save`}</button>
    </div>}>
    <form id="achievement-form" className="grid gap-4" onSubmit={event => { event.preventDefault(); if (ready) onSave({ ...draft, title: draft.title.trim(), url: draft.url.trim(), achieved_on: draft.achieved_on || null }); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor="achievement-title">{t`Title`}
        <input id="achievement-title" className="desk-input font-normal" required maxLength={160} value={draft.title} onChange={event => set({ title: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor="achievement-issuer">{t`Issued by`}
        <input id="achievement-issuer" className="desk-input font-normal" maxLength={160} value={draft.issuer} onChange={event => set({ issuer: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor="achievement-date">{t`Date`}
        <input id="achievement-date" type="date" className="desk-input font-normal" max={today()} value={draft.achieved_on ?? ""} onChange={event => set({ achieved_on: event.target.value || null })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor="achievement-url">{t`Link`}
        <input id="achievement-url" type="url" inputMode="url" className="desk-input font-normal" placeholder="https://…" value={draft.url} aria-invalid={badUrl || undefined}
          onChange={event => set({ url: event.target.value })} />
        {badUrl ? <span className="text-xs font-normal text-danger">{t`Use a link that starts with https://.`}</span> : null}</label>
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor="achievement-description">{t`Description`}
        <textarea id="achievement-description" className="desk-input font-normal" rows={3} maxLength={2000} value={draft.description} onChange={event => set({ description: event.target.value })} /></label>
      {error ? <p role="alert" className="text-sm text-danger">{fieldError(error, "achievements")}</p> : null}
    </form>
  </Modal>;
}

/**
 * Verified achievements come from the platform and are read-only ("Verified by <space>"). Self-reported ones
 * are the member's own claims: full create, edit and delete, always labelled "Self-reported".
 */
export function AchievementsEditor({ profile }: { profile: AccountProfile }) {
  const list = useAchievements();
  const { save, remove } = useAchievementMutations();
  const [editing, setEditing] = useState<{ entry?: SelfReportedAchievement } | null>(null);
  const [deleting, setDeleting] = useState<SelfReportedAchievement | null>(null);
  const own = list.data ?? [];
  const verified = profile.achievements.verified;
  return <SettingsSection title={t`Achievements`} description={t`Verified ones are added by spaces and events. You can add your own, and they are labelled as self-reported.`}>
    <SettingsRow label={t`Verified`} helper={t`Read-only. Awards, roles and attendance confirmed by a space.`}>
      {verified.length ? <ul className="grid gap-2">{verified.map((row, index) => <li key={index} className="flex flex-wrap items-start gap-3 rounded-control border border-line p-3">
        <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-success-ink" />
        <span className="min-w-0 flex-1 break-words text-ink">{verifiedSentence(row)}</span>
        <span className="chip bg-success-soft text-success-ink">{t`Verified by ${row.verified_by}`}</span>
      </li>)}</ul> : <p className="text-sm text-muted">{t`Nothing verified yet.`}</p>}
    </SettingsRow>
    <SettingsRow label={t`Self-reported`} helper={t`Add anything you are proud of. Link to proof if you have it.`}>
      <div className="grid gap-3">
        {list.isLoading ? <LogoLoader size={48} className="min-h-16 py-3" /> : null}
        {list.error ? <ErrorBlock error={new Error(t`Couldn't load your achievements. Try again.`)} onRetry={() => { void list.refetch(); }} /> : null}
        {own.length ? <ul className="grid gap-2">{own.map(row => <li key={row.id} className="flex items-start justify-between gap-3 rounded-control border border-line p-3">
          <div className="min-w-0"><p className="break-words font-semibold text-ink">{row.title}</p>
            <p className="text-sm text-muted">{[row.issuer, row.achieved_on].filter(Boolean).join(" · ")} <span className="chip">{t`Self-reported`}</span></p></div>
          <div className="flex shrink-0 gap-1">
            <IconButton label={t`Edit ${row.title}`} onClick={() => { save.reset(); setEditing({ entry: row }); }}><Pencil aria-hidden="true" className="h-4 w-4" /></IconButton>
            <IconButton label={t`Delete ${row.title}`} onClick={() => { remove.reset(); setDeleting(row); }}><Trash2 aria-hidden="true" className="h-4 w-4" /></IconButton>
          </div></li>)}</ul> : null}
        <button type="button" className="desk-button w-fit gap-2" onClick={() => { save.reset(); setEditing({}); }}><Plus aria-hidden="true" className="h-4 w-4" />{t`Add an achievement`}</button>
        {remove.error ? <p role="alert" className="text-sm text-danger">{fieldError(remove.error, "detail")}</p> : null}
      </div>
    </SettingsRow>
    <div className="py-3"><SectionToggle section="achievements" label={t`Show my achievements`} /></div>
    {editing ? <AchievementForm key={editing.entry?.id ?? "new"} entry={editing.entry} pending={save.isPending} error={save.error} onCancel={() => setEditing(null)}
      onSave={draft => save.mutate({ id: editing.entry?.id, draft }, { onSuccess: () => setEditing(null) })} /> : null}
    <ConfirmDialog open={Boolean(deleting)} tone="danger" title={t`Delete this achievement?`} confirmLabel={t`Delete`} pending={remove.isPending}
      message={deleting ? t`"${deleting.title}" is removed from your profile.` : ""} onCancel={() => setDeleting(null)}
      onConfirm={() => { if (deleting?.id !== undefined) remove.mutate(deleting.id, { onSettled: () => setDeleting(null) }); }} />
  </SettingsSection>;
}
