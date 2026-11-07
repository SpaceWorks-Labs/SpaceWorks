import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { ConfirmDialog, ErrorText, Field } from "../../../components/ui";
import { useSaveStagePlan, useStagePlan } from "./api";
import { blankStage, fromPreset, fromSaved, move, saveBody, stageErrorMessage } from "./stageDraft";
import { StageFields } from "./StageFields";
import { StageTools } from "./StageTools";
import type { Preset, StageDraft, StagePlan } from "./types";

const WARNINGS: Record<string, string> = { ambiguous_deadline_time: "This deadline is at midnight or noon event time; pick 23:59 or a clearer time." };

/** #178-#180: the organiser's submission stages. Picking a preset only fills the draft; nothing saves until Save. */
export function StageEditorPanel({ eventId }: { eventId: number }) {
  const plan = useStagePlan(eventId); const save = useSaveStagePlan(eventId);
  const [rows, setRows] = useState<StageDraft[]>([]); const [preset, setPreset] = useState("");
  const [dirty, setDirty] = useState(false); const [pending, setPending] = useState<Preset | null>(null);
  useEffect(() => { if (plan.data && !dirty) setRows(fromSaved(plan.data.stages)); }, [plan.data, dirty]);
  if (plan.isLoading) return <p role="status">{t`Loading submission stages…`}</p>;
  if (!plan.data) return plan.error ? <ErrorText message={stageErrorMessage(plan.error)} onRetry={() => void plan.refetch()} /> : null;
  const data: StagePlan = plan.data;
  const change = (next: StageDraft[]) => { setRows(next); setDirty(true); };
  const saved = (id: number | null) => data.stages.find(stage => stage.id !== null && stage.id === id);
  const chosen = data.presets.find(item => item.key === preset);
  return <section className="grid gap-5" aria-labelledby="submission-stages-title">
    <div className="grid gap-1"><h3 id="submission-stages-title" className="title-section">{t`Submission stages`}</h3>
      <p className="text-sm text-muted">{t`Each stage has its own window and requirements. Times are entered in UTC and shown in the event's time zone (${data.timezone}) and yours.`}</p></div>
    <Field label={t`Start from a preset`} hint={t`Replaces the stages below after you confirm. Nothing is saved until you press Save stages.`}>
      <select className="desk-input min-h-11" value="" onChange={e => setPending(data.presets.find(item => item.key === e.target.value) ?? null)}>
        <option value="">{t`Choose a preset…`}</option>{data.presets.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</select></Field>
    {chosen ? <p className="text-sm text-muted">{t`Preset: ${chosen.name}. ${chosen.description}`}</p> : null}
    {chosen?.requires_admission && !data.admission_enabled ? <p className="rounded-2xl border border-line bg-info-soft p-3 text-sm text-info-ink">{t`This pipeline starts with applications. Turn on hackathon applications so only accepted teams reach the first stage.`}</p> : null}
    <ConfirmDialog open={pending !== null} title={t`Use the ${pending?.name ?? ""} preset?`} confirmLabel={t`Replace stages`}
      message={t`Your stages below are replaced by the preset. Stages that already have submissions cannot be removed when you save.`}
      onCancel={() => setPending(null)} onConfirm={() => { if (pending) { change(fromPreset(pending)); setPreset(pending.key); } setPending(null); }} />
    <ol className="grid gap-4">{rows.map((stage, index) => {
      const server = saved(stage.id);
      return <li key={stage.key} className="grid gap-4 rounded-2xl border border-line p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h4 className="font-semibold text-ink">{`${index + 1}. ${stage.name || "Untitled stage"}`}</h4>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="desk-button min-h-11" aria-label={t`Move ${stage.name || `stage ${index + 1}`} up`} disabled={index === 0} onClick={() => change(move(rows, index, -1))}><ArrowUp aria-hidden size={18} /></button>
            <button type="button" className="desk-button min-h-11" aria-label={t`Move ${stage.name || `stage ${index + 1}`} down`} disabled={index === rows.length - 1} onClick={() => change(move(rows, index, 1))}><ArrowDown aria-hidden size={18} /></button>
            <button type="button" className="desk-button min-h-11 gap-2" disabled={rows.length === 1} onClick={() => change(rows.filter((_, i) => i !== index))}><Trash2 aria-hidden size={18} />{t`Remove ${stage.name || `stage ${index + 1}`}`}</button>
          </div></div>
        {server ? <p className="text-sm text-muted">{t`${server.submissions ?? 0} submitted · ${server.pending_triage ?? 0} waiting for triage`}</p> : null}
        {server?.warnings?.map(code => <p key={code} className="rounded-2xl border border-line bg-warn-soft p-3 text-sm text-warn-ink">{WARNINGS[code] ?? code}</p>)}
        <StageFields stage={stage} index={index} last={index === rows.length - 1} plan={data} onChange={next => change(rows.map((row, i) => i === index ? next : row))} />
        {server && server.id !== null && !dirty ? <StageTools eventId={eventId} stage={server} timezone={data.timezone} /> : null}
      </li>;
    })}</ol>
    <button type="button" className="desk-button min-h-11 justify-self-start" disabled={rows.length >= data.max_stages}
      onClick={() => change([...rows, blankStage(rows.length + 1)])}>{t`Add a stage`}</button>
    {save.error ? <ErrorText message={stageErrorMessage(save.error)} /> : null}
    {dirty ? <p role="status" className="text-sm font-semibold text-ink">{t`You have unsaved stage changes.`}</p> : null}
    <div className="flex flex-wrap gap-3">
      <button type="button" className="desk-button-primary min-h-11" disabled={!dirty || save.isPending}
        onClick={() => save.mutate(saveBody(rows, data.fingerprint, preset), { onSuccess: () => { setDirty(false); setPreset(""); } })}>
        {save.isPending ? t`Saving…` : t`Save stages`}</button>
      {dirty ? <button type="button" className="desk-button min-h-11" onClick={() => { setDirty(false); setPreset(""); void plan.refetch(); }}>{t`Discard changes`}</button> : null}
    </div>
  </section>;
}
