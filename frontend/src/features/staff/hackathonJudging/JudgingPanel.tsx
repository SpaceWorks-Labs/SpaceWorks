import { useState } from 'react';
import { ClipboardCheck } from 'lucide-react';
import { ConfirmDialog, EmptyState, ErrorBlock, Field, Pagination, ProgressBar, StatusPill } from '../../../components/ui';
import { useJudging } from './api';
import { CoverageTable } from './CoverageTable';
import { DefinitionEditor } from './DefinitionEditor';
import { ResultsPanel } from './ResultsPanel';
import { MentorShortlistBoard } from './MentorShortlistBoard';
import type { Round, Scope } from './types';
import { PrivateProgrammeBoundary } from '../../events/hackathonGallery/PrivateProgrammeBoundary';

function JudgingPanelContent({ scope, timezone = 'UTC', fullManager = false, galleryEnabled = false }: { scope: Scope; timezone?: string; fullManager?: boolean; galleryEnabled?: boolean }) {
  const [page, setPage] = useState(1); const { query, mutate, denied } = useJudging(scope, true, false, page);
  const [judges, setJudges] = useState(''); const [reason, setReason] = useState('');
  const [strategy, setStrategy] = useState('balanced'); const [maxLoad, setMaxLoad] = useState(100);
  const [confirm, setConfirm] = useState<{ round: Round; action: string } | null>(null);
  const [plan, setPlan] = useState('');
  const run = (round: Round, action: string, dry = false) => {
    const fields = action === 'assign' ? { strategy, max_load: maxLoad, dry_run: dry, seed: '0',
      judge_role_assignment_ids: judges.split(',').map(value => Number(value.trim())).filter(value => Number.isSafeInteger(value) && value > 0) }
      : action === 'finalize' && reason.trim() ? { coverage_exception_reason: reason.trim() } : {};
    mutate.mutate({ suffix: `judging-rounds/${round.id}/${action}/`, version: round.version, fields }, {
      onSuccess: result => { setConfirm(null); if (action === 'assign') setPlan(result.coverage_complete ? 'Every project has an assignment plan.' : `More judges are needed: ${JSON.stringify(result.deficits)}`); },
    });
  };
  if (denied) return <ErrorBlock error={query.error || mutate.error || new Error('You no longer have access to judging.')} />;
  return <section className="grid gap-6" aria-label="Hackathon judging">
    <div className="flex items-start gap-3"><ClipboardCheck className="mt-1 text-accent" aria-hidden="true" /><div>
      <h2 className="title-panel">Judging</h2><p className="text-sm text-muted">Frozen submissions, fair coverage and a clear record of every result.</p></div></div>
    {query.isLoading ? <p role="status">Loading judging rounds…</p> : null}
    <ErrorBlock error={query.error || mutate.error} onRetry={() => void query.refetch()} />
    <details><summary className="min-h-11 cursor-pointer py-3 font-semibold">Manage tracks, prizes and rubrics</summary><div className="mt-3"><DefinitionEditor scope={scope} /></div></details>
    <fieldset className="grid gap-3 rounded-xl border border-line p-4" disabled={mutate.isPending}>
      <legend className="px-1 font-semibold">Assignment planning</legend>
      <Field label="Judge role assignment IDs" hint="Choose approved judges from the event Team tab; separate their IDs with commas."><input className="desk-input min-h-11" value={judges} onChange={e => setJudges(e.target.value)} /></Field>
      <Field label="Partition"><select className="desk-input min-h-11" value={strategy} onChange={e => setStrategy(e.target.value)}>
        <option value="balanced">Balanced within judge scope</option><option value="track">By track</option><option value="room">By room</option></select></Field>
      <Field label="Maximum projects per judge"><input className="desk-input min-h-11" type="number" min={1} max={2000} value={maxLoad} onChange={e => setMaxLoad(Number(e.target.value))} /></Field>
    </fieldset>
    <p role="status" className="text-sm text-muted">{plan}</p>
    {!query.isLoading && !query.data?.count ? <EmptyState title="No judging rounds yet" description="Create a rubric or a top-three round to begin." /> : null}
    {query.data?.results.map(round => <article key={round.id} className="grid gap-4 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="title-section">{round.key}</h3><StatusPill label={round.state ?? 'Draft'} /></div>
      <p className="text-sm text-muted">{round.mode === 'top3' ? 'Top-three ranking · fixed six points per ballot' : `Weighted 1–5 · ${round.normalization === 'zscore' ? 'z-score ranking' : 'weighted average'}`} · At least {round.min_reviews} reviews per project.</p>
      {round.closes_at ? <p className="text-sm">Closes {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone }).format(new Date(round.closes_at))} ({timezone})</p> : null}
      <ProgressBar label={`Submitted assignments for ${round.key}`} value={round.assigned ? round.submitted / round.assigned : 0} />
      <p className="text-sm">{round.submitted} of {round.assigned} assignments submitted · {round.recused} recused · {round.skipped} skipped</p>
      <p className="text-sm text-muted">Estimated judges: {round.estimated_judges} at {round.minutes_per_view} minutes per project in a {round.judging_minutes}-minute judging window.</p>
      {round.rows.length ? <CoverageTable rows={round.rows} /> : null}
      <div className="flex flex-wrap gap-2">
        {round.state === 'draft' ? <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending} onClick={() => setConfirm({ round, action: 'open' })}>Open and freeze rubric</button> : null}
        {round.state === 'open' ? <><button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !judges.trim()} onClick={() => run(round, 'assign', true)}>Preview assignments</button>
          <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || !judges.trim()} onClick={() => run(round, 'assign')}>Assign judges</button>
          <button type="button" className="desk-button min-h-11" disabled={mutate.isPending} onClick={() => setConfirm({ round, action: 'close' })}>Close scoring</button></> : null}
        {round.state === 'closed' && fullManager ? <><Field label="Coverage exception reason (only if needed)"><textarea className="desk-input min-h-24" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
          <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || (!round.coverage_complete && !reason.trim())} onClick={() => setConfirm({ round, action: 'finalize' })}>Finalize round</button></> : null}
      </div>
    </article>)}
    <Pagination page={page} count={query.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} disabled={mutate.isPending} />
    {fullManager ? <><MentorShortlistBoard scope={scope} /><ResultsPanel scope={scope} rounds={query.data?.results ?? []} galleryEnabled={galleryEnabled} /></> : null}
    <ConfirmDialog open={!!confirm} title={confirm?.action === 'open' ? 'Freeze this judging rubric?' : confirm?.action === 'close' ? 'Close scoring?' : 'Finalize this round?'}
      message={confirm?.action === 'open' ? 'Opening freezes the method, criteria and eligible submission set.' : 'This action is recorded in the event history. Review coverage before continuing.'}
      pending={mutate.isPending} onCancel={() => setConfirm(null)} onConfirm={() => confirm && run(confirm.round, confirm.action)} />
  </section>;
}

export function JudgingPanel(props: Parameters<typeof JudgingPanelContent>[0]) {
  return <PrivateProgrammeBoundary identity={`${props.scope.context}:${props.scope.actorId}:${props.scope.makerspaceId}:${props.scope.eventId}`}><JudgingPanelContent {...props} /></PrivateProgrammeBoundary>;
}
