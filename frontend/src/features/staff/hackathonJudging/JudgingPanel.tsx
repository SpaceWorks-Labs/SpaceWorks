import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from 'react';
import { ClipboardCheck } from 'lucide-react';
import { ConfirmDialog, EmptyState, ErrorBlock, Field, Pagination, ProgressBar, SegmentedControl, StatusPill } from '../../../components/ui';
import { StructuredApiError } from '../../../lib/api';
import { useJudging } from './api';
import { AssignmentPreview, deficitText, type AssignPlan } from './AssignmentPreview';
import { CoverageTable } from './CoverageTable';
import { DefinitionEditor } from './DefinitionEditor';
import { ResultsPanel } from './ResultsPanel';
import { MentorShortlistBoard } from './MentorShortlistBoard';
import { ScoresExportButton } from './ScoresExportButton';
import { ManagerExtras } from './ManagerExtras';
import type { Round, Scope } from './types';
import { PrivateProgrammeBoundary } from '../../events/hackathonGallery/PrivateProgrammeBoundary';
import { LogoLoader } from '../../../components/LogoLoader';

function methodText(round: Round) {
  const min = round.min_reviews;
  if (round.mode === 'pairwise') return t`Pairwise comparison · judges pick the better of two projects · At least ${min} comparisons per project.`;
  if (round.mode === 'top3') return t`Top-three ranking · fixed six points per ballot · At least ${min} reviews per project.`;
  return round.normalization === 'zscore' ? t`Weighted 1–5 · z-score ranking · At least ${min} reviews per project.`
    : t`Weighted 1–5 · weighted average · At least ${min} reviews per project.`;
}

function JudgingPanelContent({ scope, timezone = 'UTC', fullManager = false, galleryEnabled = false, pairwiseEnabled = false, features = [] }: {
  scope: Scope; timezone?: string; fullManager?: boolean; galleryEnabled?: boolean; pairwiseEnabled?: boolean; features?: readonly string[] }) {
  const [page, setPage] = useState(1); const { query, mutate, denied } = useJudging(scope, true, false, page);
  const [judges, setJudges] = useState(''); const [reason, setReason] = useState('');
  const [strategy, setStrategy] = useState('balanced'); const [maxLoad, setMaxLoad] = useState(100);
  const [confirm, setConfirm] = useState<{ round: Round; action: string } | null>(null);
  const [plan, setPlan] = useState(''); const [seed, setSeed] = useState('0');
  const [existing, setExisting] = useState<'keep' | 'replace'>('keep');
  const [preview, setPreview] = useState<{ roundId: number; plan: AssignPlan; stale: boolean } | null>(null);
  useEffect(() => setPreview(null), [judges, strategy, maxLoad, seed, existing]); // D10: a changed input is a different plan.
  const planChanged = mutate.error instanceof StructuredApiError && mutate.error.code === 'plan_changed';
  const run = (round: Round, action: string, dry = false) => {
    const fields = action === 'assign' ? { strategy, max_load: maxLoad, dry_run: dry, seed, existing,
      ...(dry ? {} : { plan_fingerprint: preview?.plan.plan_fingerprint }),
      judge_role_assignment_ids: judges.split(',').map(value => Number(value.trim())).filter(value => Number.isSafeInteger(value) && value > 0) }
      : action === 'finalize' && reason.trim() ? { coverage_exception_reason: reason.trim() } : {};
    mutate.mutate({ suffix: `judging-rounds/${round.id}/${action}/`, version: round.version, fields }, {
      onSuccess: result => { setConfirm(null); if (action !== 'assign') return;
        if (dry) { setPreview({ roundId: round.id, plan: result as unknown as AssignPlan, stale: false }); setPlan(''); return; }
        setPreview(null); setPlan(result.coverage_complete ? t`Assignments applied. Every project has its judges.` : deficitText(result.deficits)); },
      onError: error => { if (action === 'assign' && !dry && error instanceof StructuredApiError && error.code === 'plan_changed')
        setPreview(current => current && { ...current, stale: true }); },
    });
  };
  if (denied) return <ErrorBlock error={query.error || mutate.error || new Error(t`You no longer have access to judging.`)} />;
  return <section className="grid gap-6" aria-label={t`Hackathon judging`}>
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="flex items-start gap-3"><ClipboardCheck className="mt-1 text-accent-ink" aria-hidden="true" /><div>
      <h2 className="title-panel">{t`Judging`}</h2><p className="text-sm text-muted">{t`Frozen submissions, fair coverage and a clear record of every result.`}</p></div></div>
      {fullManager && features.includes('events.scores_export') ? <ScoresExportButton scope={scope} rounds={query.data?.results ?? []} /> : null}</div>
    {query.isLoading ? <LogoLoader label={t`Loading judging rounds…`} size={48} className="min-h-16 py-3" /> : null}
    <ErrorBlock error={query.error || (planChanged ? null : mutate.error)} onRetry={() => void query.refetch()} />
    <details><summary className="min-h-11 cursor-pointer py-3 font-semibold">{t`Manage tracks, prizes and rubrics`}</summary><div className="mt-3"><DefinitionEditor scope={scope} pairwiseEnabled={pairwiseEnabled} /></div></details>
    <fieldset className="grid gap-3 rounded-xl border border-line p-4" disabled={mutate.isPending}>
      <legend className="px-1 font-semibold">{t`Assignment planning`}</legend>
      <Field label={t`Judge role assignment IDs`} hint={t`Choose approved judges from the event Team tab; separate their IDs with commas.`}><input className="desk-input min-h-11" value={judges} onChange={e => setJudges(e.target.value)} /></Field>
      <Field label={t`Partition`}><select className="desk-input min-h-11" value={strategy} onChange={e => setStrategy(e.target.value)}>
        <option value="balanced">{t`Balanced within judge scope`}</option><option value="track">{t`By track`}</option><option value="room">{t`By room`}</option>
        <option value="random">{t`Random (seeded, reproducible)`}</option></select></Field>
      {strategy === 'random' ? <p className="text-sm text-muted">{t`Seed ${seed}. `}<button type="button" className="desk-button min-h-11"
        onClick={() => { setSeed(crypto.randomUUID().slice(0, 8)); setPlan(''); }}>{t`Re-roll`}</button> {t` Then preview again; assigning uses the same seed.`}</p> : null}
      <Field label={t`Maximum projects per judge`}><input className="desk-input min-h-11" type="number" min={1} max={2000} value={maxLoad} onChange={e => setMaxLoad(Number(e.target.value))} /></Field>
      <div className="grid gap-1"><span className="text-sm font-semibold text-ink">{t`Current assignments`}</span>
        <SegmentedControl label={t`Current assignments`} value={existing} onChange={value => setExisting(value as 'keep' | 'replace')}
          options={[{ value: 'keep', label: t`Keep them` }, { value: 'replace', label: t`Re-plan unscored` }]} />
        <p className="text-xs text-muted">{existing === 'keep' ? t`Judges keep what they have; the plan only adds what coverage still needs.`
          : t`Unscored assignments may move to another judge. Scored work is never touched.`}</p></div>
    </fieldset>
    <p role="status" className="text-sm text-muted">{plan}</p>
    {!query.isLoading && !query.data?.count ? <EmptyState title={t`No judging rounds yet`} description={t`Create a rubric or a top-three round to begin.`} /> : null}
    {query.data?.results.map(round => <article key={round.id} className="grid gap-4 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="title-section">{round.key}</h3><StatusPill label={round.state ?? t`Draft`} /></div>
      <p className="text-sm text-muted">{methodText(round)}</p>
      {round.mode === 'pairwise' && !pairwiseEnabled ? <p role="status" className="text-sm text-muted">{t`Pairwise judging is switched off for this space. The round and its comparisons are kept; switch it back on to continue.`}</p> : null}
      {round.closes_at ? <p className="text-sm">{t`Closes ${new Intl.DateTimeFormat(formatLocale(), { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone }).format(new Date(round.closes_at))} (${timezone})`}</p> : null}
      {round.mode === 'pairwise' ? <p className="text-sm">{t`${round.submitted / 2} valid comparisons · ${round.assigned} projects shown · ${round.recused} recused · ${round.skipped} skipped`}</p> : <>
      <ProgressBar label={t`Submitted assignments for ${round.key}`} value={round.assigned ? round.submitted / round.assigned : 0} />
      <p className="text-sm">{t`${round.submitted} of ${round.assigned} assignments submitted · ${round.recused} recused · ${round.skipped} skipped`}</p></>}
      <p className="text-sm text-muted">{t`Estimated judges: ${round.estimated_judges} at ${round.minutes_per_view} minutes per project in a ${round.judging_minutes}-minute judging window.`}</p>
      {round.rows.length ? <CoverageTable rows={round.rows} pairwise={round.mode === 'pairwise'} /> : null}
      <div className="flex flex-wrap gap-2">
        {round.state === 'draft' ? <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || (round.mode === 'pairwise' && !pairwiseEnabled)} onClick={() => setConfirm({ round, action: 'open' })}>{t`Open and freeze rubric`}</button> : null}
        {round.state === 'open' && round.mode === 'pairwise' ? <button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !pairwiseEnabled}
          onClick={() => setConfirm({ round, action: 'close' })}>{t`Close comparisons`}</button> : null}
        {round.state === 'open' && round.mode !== 'pairwise' ? <><button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || !judges.trim()} onClick={() => run(round, 'assign', true)}>{t`Preview assignments`}</button>
          <button type="button" className="desk-button min-h-11" disabled={mutate.isPending} onClick={() => setConfirm({ round, action: 'close' })}>{t`Close scoring`}</button></> : null}
        {round.state === 'closed' && fullManager ? <><Field label={t`Coverage exception reason (only if needed)`}><textarea className="desk-input min-h-24" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
          <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || (!round.coverage_complete && !reason.trim())} onClick={() => setConfirm({ round, action: 'finalize' })}>{t`Finalize round`}</button></> : null}
      </div>
      {preview?.roundId === round.id && round.state === 'open' ? <AssignmentPreview round={round} plan={preview.plan} stale={preview.stale || planChanged}
        pending={mutate.isPending} onApply={() => run(round, 'assign')} onPreviewAgain={() => run(round, 'assign', true)} onDiscard={() => setPreview(null)} /> : null}
    </article>)}
    <Pagination page={page} count={query.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} disabled={mutate.isPending} />
    {fullManager ? <><MentorShortlistBoard scope={scope} /><ResultsPanel scope={scope} rounds={query.data?.results ?? []} galleryEnabled={galleryEnabled} /></> : null}
    <ManagerExtras scope={scope} rounds={query.data?.results ?? []} features={features} fullManager={fullManager} />
    <ConfirmDialog open={!!confirm} title={confirm?.action === 'open' ? t`Freeze this judging rubric?` : confirm?.action === 'close' ? t`Close scoring?` : t`Finalize this round?`}
      message={confirm?.action === 'open' ? t`Opening freezes the method, criteria and eligible submission set.` : t`This action is recorded in the event history. Review coverage before continuing.`}
      pending={mutate.isPending} onCancel={() => setConfirm(null)} onConfirm={() => confirm && run(confirm.round, confirm.action)} />
  </section>;
}

export function JudgingPanel(props: Parameters<typeof JudgingPanelContent>[0]) {
  return <PrivateProgrammeBoundary identity={`${props.scope.context}:${props.scope.actorId}:${props.scope.makerspaceId}:${props.scope.eventId}`}><JudgingPanelContent {...props} /></PrivateProgrammeBoundary>;
}
