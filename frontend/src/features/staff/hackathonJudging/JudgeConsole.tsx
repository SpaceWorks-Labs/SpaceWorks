import { useState, type ReactNode } from 'react';
import { DetailLayout } from '../../../components/layouts';
import { EmptyState, ErrorBlock, Field, Pagination, StatusPill } from '../../../components/ui';
import { useAssignments } from './api';
import { PairwiseDesk } from './PairwiseDesk';
import { ScoreNextBar } from './ScoreNextBar';
import { PrivateProgrammeBoundary } from '../../events/hackathonGallery/PrivateProgrammeBoundary';
import { StructuredApiError } from '../../../lib/api';
import type { Assignment, Scope } from './types';

function JudgeConsoleContent({ scope, renderAssets, pairwiseEnabled = false }: { scope: Scope; renderAssets: (assetIds: number[]) => ReactNode; pairwiseEnabled?: boolean }) {
  const [page, setPage] = useState(1); const { query, submit } = useAssignments(scope, page);
  const [resets, setResets] = useState<Record<number, number>>({});
  if (submit.error instanceof StructuredApiError && [401, 403, 404].includes(submit.error.status)) return <ErrorBlock error={submit.error} />;
  return <DetailLayout title="Your judging desk" state={{ status: query.isLoading ? 'loading' : query.isError ? 'error' : 'ready',
    error: query.error?.message, onRetry: () => void query.refetch() }} main={<div className="grid gap-6">
      {pairwiseEnabled ? <PairwiseDesk scope={scope} renderAssets={renderAssets} /> : null}
      <ScoreNextBar scope={scope} assignments={query.data?.results ?? []} />
      {!query.data?.count ? <EmptyState title="No assigned projects" description="Your projects will appear here when the organizer assigns this round." /> : null}
      {query.data?.results.map(row => <JudgeAssignmentEditor key={`${scope.context}:${scope.actorId}:${row.id}:${resets[row.id] ?? 0}`} assignment={row}
        pending={submit.isPending} error={submit.error} renderAssets={renderAssets}
        onReload={async () => { await query.refetch(); setResets(value => ({ ...value, [row.id]: (value[row.id] ?? 0) + 1 })); }}
        onSubmit={(action, fields) => submit.mutate({ assignment: row, action, fields })} />)}
      <Pagination page={page} count={query.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} disabled={submit.isPending} />
    </div>} />;
}

export function JudgeConsole(props: Parameters<typeof JudgeConsoleContent>[0]) {
  return <PrivateProgrammeBoundary identity={`${props.scope.context}:${props.scope.actorId}:${props.scope.makerspaceId}:${props.scope.eventId}`}><JudgeConsoleContent {...props} /></PrivateProgrammeBoundary>;
}

export function JudgeAssignmentEditor({ assignment: row, onSubmit, pending, error, renderAssets, onReload }: {
  assignment: Assignment; onSubmit: (action: 'score' | 'rank' | 'recuse' | 'skip', fields: Record<string, unknown>) => void;
  pending: boolean; error: unknown; renderAssets: (assetIds: number[]) => ReactNode;
  onReload?: () => Promise<void>;
}) {
  const [scores, setScores] = useState(row.scores); const [notes, setNotes] = useState(row.notes);
  const [feedback, setFeedback] = useState((row as Assignment & { team_feedback?: string }).team_feedback ?? ''); // S4
  const [ranked, setRanked] = useState<string[]>(['', '', '']); const [reason, setReason] = useState('');
  const rankCount = Math.min(3, row.batch_projects.length);
  const ranks = ranked.slice(0, rankCount).map(Number);
  const rankValid = ranks.length > 0 && ranks.every(value => value > 0) && new Set(ranks).size === ranks.length;
  const rubricValid = row.configuration.criteria.every(c => Number.isInteger(scores[c.key]) && scores[c.key] >= 1 && scores[c.key] <= 5);
  return <article className="grid gap-4 rounded-xl border border-line bg-panel p-4" aria-label={`Judge ${row.title}`}>
    <div className="flex flex-wrap items-center gap-3"><h2 className="title-section">{row.title}</h2><StatusPill label={row.state ?? 'Assigned'} /></div>
    <p className="whitespace-pre-wrap break-words text-sm">{row.description}</p>{renderAssets(row.asset_ids)}
    {row.mode === 'pairwise' ? <p className="text-sm text-muted">You compare this project in the pairwise desk above. Declare a conflict here if you find one later.</p>
    : row.mode === 'weighted_1_5' ? <fieldset className="grid gap-4" disabled={pending || !row.allowed_actions.includes('score')}>
      <legend className="mb-3 font-semibold">Weighted 1–5 rubric</legend>
      {row.configuration.criteria.map(c => <Field key={c.key} label={`${c.label} · weight ${c.weight}`} hint="Choose the description that best matches this project.">
        <select className="desk-input min-h-11" value={scores[c.key] ?? ''} onChange={e => setScores({ ...scores, [c.key]: Number(e.target.value) })}>
          <option value="">Choose a score</option>{[1, 2, 3, 4, 5].map(score => <option key={score} value={score}>{score} — {c.anchors[String(score)]}</option>)}</select>
      </Field>)}
      <Field label="Private notes" hint="Visible only to you in this judging assignment. Never shown to the team."><textarea className="desk-input min-h-24" maxLength={4000} value={notes} onChange={e => setNotes(e.target.value)} /></Field>
      <Field label="Feedback for the team" hint="Shown to the team, without your name, only if the organisers share this round's feedback."><textarea className="desk-input min-h-24" maxLength={4000} value={feedback} onChange={e => setFeedback(e.target.value)} /></Field>
      <div className="flex flex-wrap gap-2"><button type="button" className="desk-button min-h-11" onClick={() => onSubmit('score', { scores, notes, team_feedback: feedback, submit: false })}>Save private draft</button>
        <button type="button" className="desk-button-primary min-h-11" disabled={!rubricValid} onClick={() => onSubmit('score', { scores, notes, team_feedback: feedback, submit: true })}>Submit judgment</button></div>
    </fieldset> : <fieldset className="grid gap-3" disabled={pending || !row.allowed_actions.includes('rank')}>
      <legend className="mb-3 font-semibold">Rank your batch</legend><p className="text-sm text-muted">Rank {rankCount} distinct projects. Every submitted ballot has a six-point budget; a smaller batch is normalized.</p>
      {Array.from({ length: rankCount }, (_, index) => <Field key={index} label={`Rank ${index + 1}`}><select className="desk-input min-h-11" value={ranked[index]}
        onChange={e => setRanked(ranked.map((value, i) => i === index ? e.target.value : value))}><option value="">Choose a project</option>
        {row.batch_projects.map(project => <option key={project.snapshot_id} value={project.snapshot_id}>{project.title}</option>)}</select></Field>)}
      <button type="button" className="desk-button-primary min-h-11" disabled={!rankValid} onClick={() => onSubmit('rank', { ordered_top3: ranks })}>Submit top-three ballot</button>
    </fieldset>}
    {row.allowed_actions.includes('recuse') || row.allowed_actions.includes('skip') ? <fieldset className="grid gap-3" disabled={pending}>
      <legend className="mb-3 font-semibold">Unable to judge this project?</legend>
      <Field label="Private reason"><textarea className="desk-input min-h-24" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
      <div className="flex flex-wrap gap-2"><button className="desk-button min-h-11" type="button" disabled={!reason.trim()} onClick={() => onSubmit('recuse', { reason })}>Declare conflict and recuse</button>
        <button className="desk-button min-h-11" type="button" disabled={!reason.trim()} onClick={() => onSubmit('skip', { reason })}>Skip for reassignment</button></div>
    </fieldset> : null}
    <ErrorBlock error={error} />{error ? <p className="text-sm text-muted">Your draft is still here. Reload the assignment to review a changed version before trying again.</p> : null}
    {error && onReload ? <button className="desk-button min-h-11" type="button" disabled={pending} onClick={() => void onReload()}>Discard this draft and reload the assignment</button> : null}
  </article>;
}
