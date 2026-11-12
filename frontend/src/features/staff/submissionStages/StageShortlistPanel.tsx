import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ConfirmDialog, ErrorText, Field } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import type { Page } from "../../events/hackathonGallery/types";
import { useProgrammeOptions } from "../hackathonJudging/l21bApi";
import { stagesKey, useStageCommands, useStageShortlist } from "./api";
import { PromoteNext } from "./PromoteNext";
import { stageErrorMessage } from "./stageDraft";
import type { SavedStage, ShortlistPlan } from "./types";
import { LogoLoader } from "../../../components/LogoLoader";

type RoundRow = { id: number; key: string; state: string; submission_stage_id?: number | null };

export function publishWarning(plan: { not_shortlisted: number; email_enabled: boolean } | null) {
  if (!plan || plan.email_enabled || plan.not_shortlisted === 0) return "";
  return plural(plan.not_shortlisted, { one: "# team will NOT be told by email that it was not shortlisted.", other: "# teams will NOT be told by email that they were not shortlisted." });
}

/** #179: choose who continues after this stage (finalists engine), apply, then publish once. */
export function StageShortlistPanel({ eventId, stage }: { eventId: number; stage: SavedStage & { id: number } }) {
  const { query, preview, apply, publish } = useStageShortlist(eventId, stage.id);
  const scope = { eventId, makerspaceId: 0, actorId: 0, context: "person" };
  const options = useProgrammeOptions(scope);
  const rounds = useQuery({ queryKey: [...stagesKey(eventId), "rounds"], retry: false,
    queryFn: () => staffRequest<Page<RoundRow>>(`/admin/events/${eventId}/judging-rounds/?page=1`) });
  const [selection, setSelection] = useState<"top_n" | "manual">("manual"); const [topN, setTopN] = useState(10);
  const [round, setRound] = useState(""); const [picked, setPicked] = useState<number[]>([]); const [confirm, setConfirm] = useState(false);
  const plan: ShortlistPlan | undefined = preview.data; const data = query.data;
  const eligible = (data?.stage_entries ?? []).filter(row => row.triage === "eligible");
  const finalized = (rounds.data?.results ?? []).filter(row => row.state === "finalized" && row.submission_stage_id === stage.id);
  const body = { selection, ...(selection === "top_n" ? { top_n: topN } : { submission_ids: picked }), source_round_id: round ? Number(round) : null };
  const label = data?.label || stage.shortlist_label || "Shortlist";
  if (!data) return query.error ? <ErrorText message={stageErrorMessage(query.error)} /> : <LogoLoader label={t`Loading the shortlist…`} size={48} className="min-h-16 py-3" />;
  const published = Boolean(data.current?.published_at);
  return <section className="grid gap-3" aria-label={`${label} for ${stage.name}`}>
    {data.pending_triage ? <TriageBlocker eventId={eventId} stageId={stage.id} count={data.pending_triage}
      ids={data.stage_entries.filter(row => row.triage === "pending").map(row => row.submission_id)} /> : null}
    {data.current ? <div className="grid gap-2"><p className="text-sm text-ink">{data.current.selection === "promoted"
      ? t`${label} amended: a withdrawn team was replaced by the next ranked team.` : published ? `${label} published.` : t`${label} chosen, not yet published.`}</p>
      <ul className="grid gap-1 text-sm">{data.current.entries.map(entry => <li key={entry.submission_id}>{entry.source_rank ? `#${entry.source_rank} ` : ""}{entry.title || t`Team ${entry.team_id}`}</li>)}</ul></div> : null}
    {data.allowed_actions.includes("apply") ? <div className="grid gap-3">
      <Field label={t`How to choose`}><select className="desk-input min-h-11" value={selection} onChange={e => setSelection(e.target.value as typeof selection)}>
        <option value="manual">{t`Pick teams by hand`}</option><option value="top_n">{t`Top N from a judging round on this stage`}</option></select></Field>
      <Field label={t`Judging round (optional for hand-picking)`}><select className="desk-input min-h-11" value={round} onChange={e => setRound(e.target.value)}>
        <option value="">{t`No round`}</option>{finalized.map(row => <option key={row.id} value={row.id}>{row.key}</option>)}</select></Field>
      {selection === "top_n" ? <Field label={t`How many continue`} hint={t`Teams tied at the cutoff all continue.`}><input className="desk-input min-h-11" type="number" min={1} max={1000} value={topN} onChange={e => setTopN(Number(e.target.value))} /></Field>
        : <fieldset className="grid gap-1"><legend className="font-semibold text-ink">{t`Teams that continue`}</legend>
          {eligible.map(row => <label key={row.submission_id} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={picked.includes(row.submission_id)}
            onChange={e => setPicked(e.target.checked ? [...picked, row.submission_id] : picked.filter(id => id !== row.submission_id))} />{row.team_name}</label>)}
          {!eligible.length ? <p className="text-sm text-muted">{t`No eligible submissions for this stage yet.`}</p> : null}</fieldset>}
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={preview.isPending || (selection === "top_n" && !round)} onClick={() => preview.mutate(body)}>{t`Preview`}</button>
      {plan ? <div className="grid gap-2 rounded-2xl border border-line p-3">
        <p className="text-sm text-ink">{t`${plan.entries.length} of ${plan.candidates} eligible teams continue.`}</p>
        {plan.tied_at_cutoff ? <p className="text-sm text-warn-ink">{t`Teams tied at the cutoff are all included.`}</p> : null}
        <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={apply.isPending || !plan.entries.length}
          onClick={() => apply.mutate({ ...body, fingerprint: plan.fingerprint }, { onSuccess: () => preview.reset() })}>{t`Apply this ${label.toLowerCase()}`}</button></div> : null}
    </div> : null}
    {data.current && data.allowed_actions.includes("publish") ? <button type="button" className="desk-button-primary min-h-11 justify-self-start" onClick={() => setConfirm(true)}>{t`Publish the ${label.toLowerCase()}`}</button> : null}
    {data.allowed_actions.includes("promote") ? <PromoteNext eventId={eventId} stageId={stage.id} shortlist={data} /> : null}
    <ConfirmDialog open={confirm} title={t`Publish the ${label.toLowerCase()}?`} confirmLabel={t`Publish`} pending={publish.isPending}
      message={[`Only the chosen teams can submit the next stage. This happens once.`,
        publishWarning({ not_shortlisted: Math.max(0, data.candidates - (data.current?.entries.length ?? 0)), email_enabled: data.email_enabled })].filter(Boolean).join(" ")}
      onCancel={() => setConfirm(false)} onConfirm={() => data.current && publish.mutate(data.current.id, { onSuccess: () => setConfirm(false) })} />
    {!data.email_enabled && options.query.data ? <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={false} disabled={options.save.isPending}
      onChange={() => options.save.mutate({ version: options.query.data!.version, fields: { shortlist_email: true } }, { onSuccess: () => void query.refetch() })} />{t`Email teams their shortlist result when published`}</label> : null}
    {[preview.error, apply.error, publish.error, options.save.error].map((error, i) => error ? <ErrorText key={i} message={stageErrorMessage(error)} /> : null)}
  </section>;
}

function TriageBlocker({ eventId, stageId, count, ids }: { eventId: number; stageId: number; count: number; ids: number[] }) {
  const { triage } = useStageCommands(eventId, stageId);
  return <div className="grid gap-2 rounded-2xl border border-line bg-warn-soft p-3">
    <p className="text-sm text-warn-ink">{plural(count, { one: "# submission is waiting for triage. Triage every submission of this stage before choosing.", other: "# submissions are waiting for triage. Triage every submission of this stage before choosing." })}</p>
    <button type="button" className="desk-button min-h-11 justify-self-start" disabled={!ids.length || triage.isPending}
      onClick={() => triage.mutate({ submission_ids: ids, triage: "eligible", reason: t`Bulk-marked eligible before the shortlist.` })}>{t`Mark ${ids.length} pending as eligible`}</button>
    {triage.error ? <ErrorText message={stageErrorMessage(triage.error)} /> : null}
  </div>;
}
