import { useState } from 'react';
import { ConfirmDialog, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import { useDefinitions, useJudging } from './api';
import { GalleryPublishPanel } from './GalleryPublishPanel';
import { IntegrityFlag } from './IntegrityFlag';
import type { Round, Scope } from './types';

type Award = { prize_id: number; snapshot_id: number; rank: number; public_requested: boolean; tie_reason: string };
export function ResultsPanel({ scope, rounds, galleryEnabled = false }: { scope: Scope; rounds: Round[]; galleryEnabled?: boolean }) {
  const { result, mutate } = useJudging(scope, true, true); const { prizes } = useDefinitions(scope);
  const [selected, setSelected] = useState<number[]>([]); const [awards, setAwards] = useState<Award[]>([]);
  const [integrity, setIntegrity] = useState(false); const [reason, setReason] = useState('');
  const [preview, setPreview] = useState(''); const [confirm, setConfirm] = useState<'finalize' | 'publish' | null>(null);
  const current = result.data;
  const version = current?.version ?? 0;
  const snapshots = [...new Set(rounds.filter(row => selected.includes(row.id)).flatMap(row => row.rows.map(row => row.snapshot_id)))];
  const update = (index: number, patch: Partial<Award>) => setAwards(awards.map((row, i) => i === index ? { ...row, ...patch } : row));
  const submit = (action: 'finalize' | 'publish' | 'preview') => {
    const suffix = action === 'finalize' && version ? 'correct' : action;
    const fields = action === 'publish' ? { result_revision_id: current?.id } : action === 'preview' ? { round_ids: selected } : {
      round_ids: selected, awards: awards.map(row => row.tie_reason.trim() ? row : { prize_id: row.prize_id, snapshot_id: row.snapshot_id, rank: row.rank, public_requested: row.public_requested }),
      integrity_reviewed: integrity, ...(reason.trim() ? { reason: reason.trim() } : {}),
    };
    mutate.mutate({ suffix: `results/${suffix}/`, version, fields }, {
      onSuccess: response => { setConfirm(null); setPreview(action === 'preview' ? JSON.stringify(response.rounds, null, 2) : 'Result saved.'); },
    });
  };
  if (result.isError) return <ErrorBlock error={result.error} onRetry={() => void result.refetch()} />;
  return <section className="grid gap-4 border-t border-line pt-6" aria-label="Result publication">
    <div className="flex flex-wrap items-center gap-3"><h3 className="title-section">Finalize and announce results</h3>
      <StatusPill label={current?.state ?? 'Draft'} /></div>
    <p className="text-sm text-muted">Finalizing freezes the calculations and awards. Announcing is a separate action. Corrections create a new revision.</p>
    {current?.sponsor_proposals?.length ? <div className="grid gap-2 rounded-xl border border-line p-3"><h4 className="font-semibold">Sponsor winner proposals</h4>
      <p className="text-sm text-muted">These are suggestions. The full event manager selects the final awards.</p>
      <ul>{current.sponsor_proposals.map(proposal => <li key={proposal.id} className="text-sm">Prize {proposal.prize_id} · Project {proposal.submission_snapshot_id}</li>)}</ul>
    </div> : null}
    <fieldset className="grid gap-2" disabled={mutate.isPending}><legend className="mb-2 text-sm font-semibold">Rounds to include</legend>
      {rounds.filter(row => row.state === 'finalized').map(row => <label key={row.id} className="flex min-h-11 items-center gap-3">
        <input type="checkbox" checked={selected.includes(row.id)} onChange={e => setSelected(e.target.checked ? [...selected, row.id] : selected.filter(id => id !== row.id))} />{row.key}</label>)}
    </fieldset>
    {awards.map((row, index) => <fieldset key={index} className="grid gap-3 rounded-xl border border-line p-4" disabled={mutate.isPending}>
      <legend className="px-1 font-semibold">Award {index + 1}</legend>
      <Field label="Prize"><select className="desk-input min-h-11" value={row.prize_id} onChange={e => update(index, { prize_id: Number(e.target.value) })}>
        <option value={0}>Choose a prize</option>{prizes.data?.results.map(prize => <option key={prize.id} value={prize.id}>{prize.name}</option>)}</select></Field>
      <Field label="Winning frozen project"><select className="desk-input min-h-11" value={row.snapshot_id} onChange={e => update(index, { snapshot_id: Number(e.target.value) })}>
        <option value={0}>Choose a project</option>{snapshots.map(id => <option key={id} value={id}>Project {id}</option>)}</select></Field>
      <Field label="Prize rank"><input className="desk-input min-h-11" type="number" min={1} max={100} value={row.rank} onChange={e => update(index, { rank: Number(e.target.value) })} /></Field>
      <Field label="Tie selection reason (when tied)"><textarea className="desk-input min-h-24" maxLength={2000} value={row.tie_reason} onChange={e => update(index, { tie_reason: e.target.value })} /></Field>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={row.public_requested} onChange={e => update(index, { public_requested: e.target.checked })} />Include in the public award list when the team has opted in</label>
      <button className="desk-button min-h-11" type="button" onClick={() => setAwards(awards.filter((_, i) => i !== index))}>Remove award {index + 1}</button>
    </fieldset>)}
    <button className="desk-button min-h-11" type="button" disabled={mutate.isPending} onClick={() => setAwards([...awards, { prize_id: 0, snapshot_id: 0, rank: 1, public_requested: false, tie_reason: '' }])}>Add award</button>
    <IntegrityFlag scope={scope} snapshotIds={snapshots} />
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={integrity} onChange={e => setIntegrity(e.target.checked)} />I reviewed integrity flags and coverage exceptions</label>
    {version > 0 ? <Field label="Correction reason"><textarea className="desk-input min-h-24" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></Field> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !selected.length} onClick={() => submit('preview')}>Preview calculations</button>
      <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || !selected.length || !integrity || (version > 0 && !reason.trim())} onClick={() => setConfirm('finalize')}>{version ? 'Create result correction' : 'Finalize results'}</button>
      <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || !version || current?.state === 'published'} onClick={() => setConfirm('publish')}>Announce results</button>
    </div>
    <ErrorBlock error={mutate.error} /><p className="whitespace-pre-wrap break-words text-sm text-muted" role="status">{preview}</p>
    {mutate.error ? <p className="text-sm text-muted">Your selections are retained. Refresh the server revision before reapplying a stale change.</p> : null}
    {galleryEnabled ? <GalleryPublishPanel scope={scope} snapshots={[...new Set(rounds.flatMap(row => row.rows.map(row => row.snapshot_id)))]} resultRevisionId={current?.id ?? null} /> : null}
    <ConfirmDialog open={confirm !== null} title={confirm === 'publish' ? 'Announce these results?' : 'Freeze this result revision?'}
      message={confirm === 'publish' ? 'Participants will be notified. The first announcement starts the file-retention deadline; later corrections do not extend it.' : 'Review selected rounds, prize assignments and tie reasons. This revision becomes immutable.'}
      pending={mutate.isPending} onCancel={() => setConfirm(null)} onConfirm={() => confirm && submit(confirm)} />
  </section>;
}
