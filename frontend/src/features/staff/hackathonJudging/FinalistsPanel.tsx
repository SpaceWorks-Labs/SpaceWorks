import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { Trophy } from 'lucide-react';
import { EmptyState, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import { useFinalists, type FinalistPreview, type FinalistSelection } from './l21bApi';
import type { Round, Scope } from './types';

/** Advance finalists from a finalized round into a draft round, then publish them separately. */
export function FinalistsPanel({ scope, rounds }: { scope: Scope; rounds: Round[] }) {
  const { list, preview, apply, publish } = useFinalists(scope, true);
  const finalized = rounds.filter(round => round.state === 'finalized');
  const drafts = rounds.filter(round => round.state === 'draft');
  const [source, setSource] = useState(0); const [target, setTarget] = useState(0);
  const [mode, setMode] = useState<'top_n' | 'manual'>('top_n'); const [topN, setTopN] = useState(5);
  const [picked, setPicked] = useState(''); const [plan, setPlan] = useState<FinalistPreview | null>(null);
  const selection = (): FinalistSelection => ({ source_round_id: source, target_round_id: target, selection: mode,
    ...(mode === 'top_n' ? { top_n: topN } : { snapshot_ids: picked.split(',').map(v => Number(v.trim())).filter(v => Number.isSafeInteger(v) && v > 0) }) });
  const targetRound = drafts.find(round => round.id === target);
  const busy = preview.isPending || apply.isPending || publish.isPending;
  return <section className="grid gap-4" aria-label={t`Finalists`}>
    <div className="flex items-start gap-3"><Trophy className="mt-1 text-accent-ink" aria-hidden="true" /><div>
      <h3 className="title-section">{t`Finalists`}</h3>
      <p className="text-sm text-muted">{t`Advance the top projects of a finished round into the next one. Disqualified and withdrawn projects never advance. Results and prizes come from the final round.`}</p></div></div>
    <ErrorBlock error={list.error || preview.error || apply.error || publish.error} />
    {!finalized.length || !drafts.length ? <p className="text-sm text-muted" role="status">{t`Finalize a round and create a draft round for the finalists first.`}</p> : <fieldset className="grid gap-3 rounded-xl border border-line p-4" disabled={busy}>
      <legend className="px-1 font-semibold">{t`Choose finalists`}</legend>
      <Field label={t`From finalized round`}><select className="desk-input min-h-11" value={source} onChange={e => { setSource(Number(e.target.value)); setPlan(null); }}>
        <option value={0}>{t`Choose a round`}</option>{finalized.map(round => <option key={round.id} value={round.id}>{round.key}</option>)}</select></Field>
      <Field label={t`Into draft round`}><select className="desk-input min-h-11" value={target} onChange={e => { setTarget(Number(e.target.value)); setPlan(null); }}>
        <option value={0}>{t`Choose a round`}</option>{drafts.filter(round => round.id !== source).map(round => <option key={round.id} value={round.id}>{round.key}</option>)}</select></Field>
      <Field label={t`How to choose`}><select className="desk-input min-h-11" value={mode} onChange={e => { setMode(e.target.value as 'top_n' | 'manual'); setPlan(null); }}>
        <option value="top_n">{t`Top projects by rank`}</option><option value="manual">{t`Hand-picked projects`}</option></select></Field>
      {mode === 'top_n' ? <Field label={t`How many advance`} hint={t`Projects tied at the cutoff all advance.`}><input className="desk-input min-h-11" type="number" min={1} max={500} value={topN} onChange={e => { setTopN(Number(e.target.value)); setPlan(null); }} /></Field>
        : <Field label={t`Project snapshot IDs`} hint={t`Separate the IDs with commas.`}><input className="desk-input min-h-11" value={picked} onChange={e => { setPicked(e.target.value); setPlan(null); }} /></Field>}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button min-h-11" disabled={!source || !target} onClick={() => preview.mutate(selection(), { onSuccess: setPlan })}>{t`Preview finalists`}</button>
        <button type="button" className="desk-button-primary min-h-11" disabled={!plan || !targetRound || !plan.finalists.length}
          onClick={() => plan && targetRound && apply.mutate({ selection: selection(), fingerprint: plan.fingerprint, version: targetRound.version }, { onSuccess: () => setPlan(null) })}>{t`Advance these finalists`}</button>
      </div>
      {plan ? <div className="grid gap-2" role="status"><p className="text-sm">{t`${plan.finalists.length} projects advance.`}{plan.tied_at_cutoff ? t` Projects tied at the cutoff are all included.` : ''}</p>
        <ol className="grid gap-1 text-sm">{plan.finalists.map(row => <li key={row.snapshot_id}>{row.source_rank ? `#${row.source_rank} · ` : ''}{row.title}</li>)}</ol></div> : null}
    </fieldset>}
    {!list.isLoading && !list.data?.count ? <EmptyState title={t`No finalists yet`} description={t`Advanced finalists appear here, ready to publish.`} /> : null}
    {list.data?.results.map(row => <article key={row.id} className="grid gap-2 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{t`${row.finalists.length} finalists`}</p>
        <StatusPill label={row.published_at ? t`Published` : row.current ? t`Current` : t`Replaced`} /></div>
      <ol className="grid gap-1 text-sm">{row.finalists.map(item => <li key={item.snapshot_id}>{item.title}</li>)}</ol>
      {row.allowed_actions.includes('publish') ? <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={busy}
        onClick={() => publish.mutate({ advance: row.id, version: rounds.find(round => round.id === row.target_round_id)?.version ?? 0 })}>{t`Publish finalists`}</button> : null}
    </article>)}
  </section>;
}
