import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ConfirmDialog, ErrorBlock, Field } from '../../../components/ui';
import { staffRequest } from '../../../lib/api';
import { judgingKey, useJudging } from './api';
import type { Scope } from './types';

type GalleryState = { id: number | null; version: number; result_revision_id: number | null;
  entries: { id: number; version: number; snapshot_id: number; title: string; hidden: boolean }[] };
export function GalleryPublishPanel({ scope, snapshots, resultRevisionId }: { scope: Scope; snapshots: number[]; resultRevisionId: number | null }) {
  const { mutate } = useJudging(scope);
  const query = useQuery({ queryKey: [...judgingKey(scope), 'gallery'], retry: false,
    queryFn: () => staffRequest<GalleryState>(`/admin/events/${scope.eventId}/gallery/`) });
  const [selected, setSelected] = useState<number[]>([]); const [reason, setReason] = useState('');
  const [amendSnapshot, setAmendSnapshot] = useState(''); const [confirm, setConfirm] = useState(false);
  const publication = query.data;
  const publish = () => mutate.mutate({ suffix: 'gallery/publish/', version: 0,
    fields: { snapshot_ids: selected, result_revision_id: resultRevisionId } }, { onSuccess: () => setConfirm(false) });
  if (query.isError) return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  return <section className="grid gap-4" aria-label={t`Gallery publication`}>
    <h3 className="title-section">{t`Project gallery`}</h3><p className="text-sm text-muted">{t`The initial selection is published once. Only team-approved metadata and individually approved files or links can appear.`}</p>
    {!publication?.id ? <><fieldset className="grid gap-2" disabled={mutate.isPending}><legend className="mb-2 text-sm font-semibold">{t`Frozen projects to publish`}</legend>
      {snapshots.map(id => <label key={id} className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={selected.includes(id)}
        onChange={e => setSelected(e.target.checked ? [...selected, id] : selected.filter(value => value !== id))} />{t`Project ${id}`}</label>)}</fieldset>
      <button type="button" className="desk-button-primary min-h-11" disabled={mutate.isPending || !selected.length} onClick={() => setConfirm(true)}>{t`Publish gallery selection`}</button></> : <>
      <Field label={t`Publication change reason`}><textarea className="desk-input min-h-24" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
      {publication.entries.map(entry => <div key={entry.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-3">
        <p className="text-sm">{entry.title} · {entry.hidden ? t`Hidden` : t`Selected`}</p>
        <button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !reason.trim()} onClick={() => mutate.mutate({
          suffix: `gallery/entries/${entry.id}/hide/`, version: entry.version, fields: { hidden: !entry.hidden, reason } })}>{entry.hidden ? t`Unhide consented entry` : t`Hide entry`}</button>
      </div>)}
      <Field label={t`Frozen snapshot for an explicit amendment`}><input className="desk-input min-h-11" type="number" min={1} value={amendSnapshot} onChange={e => setAmendSnapshot(e.target.value)} /></Field>
      <button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !reason.trim() || !amendSnapshot} onClick={() => mutate.mutate({
        suffix: 'gallery/amend/', version: publication.version, fields: { snapshot_id: Number(amendSnapshot), reason } })}>{t`Publish renewed selection as an amendment`}</button>
      <button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !reason.trim() || !resultRevisionId} onClick={() => mutate.mutate({
        suffix: 'gallery/correct-result/', version: publication.version, fields: { result_revision_id: resultRevisionId, reason } })}>{t`Record corrected result reference`}</button>
    </>}
    <ErrorBlock error={mutate.error} />
    <ConfirmDialog open={confirm} title={t`Publish this gallery selection?`} message={t`The selected public projects will be visible immediately. New uploads require a separate, audited amendment. Teams can withdraw consent at any time.`}
      pending={mutate.isPending} onCancel={() => setConfirm(false)} onConfirm={publish} />
  </section>;
}
