import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { ErrorBlock } from '../../../components/ui';
import { useGalleryConsent, type MemberScope } from './api';
import { PrivateProgrammeBoundary } from './PrivateProgrammeBoundary';
import { isAccessLoss } from './accessLoss';

function GalleryPrivacyForm({ scope, teamId, snapshotId, leader, items }: {
  scope: MemberScope; teamId: number; snapshotId: number; leader: boolean;
  items: { id: number; kind: 'asset' | 'link'; label: string }[];
}) {
  const { query, mutate } = useGalleryConsent(scope, teamId);
  const [checked, setChecked] = useState<string[]>([]); const [metadata, setMetadata] = useState(false);
  const [consent, setConsent] = useState(false); const [message, setMessage] = useState('');
  const asset_ids = items.filter(i => i.kind === 'asset' && checked.includes(`${i.kind}:${i.id}`)).map(i => i.id);
  const link_ids = items.filter(i => i.kind === 'link' && checked.includes(`${i.kind}:${i.id}`)).map(i => i.id);
  const run = (action: 'grant' | 'withdraw', all = false) => mutate.mutate({
    suffix: `teams/${teamId}/gallery-consent/${action}/`, version: query.data?.version ?? 0,
    fields: action === 'grant' ? { snapshot_id: snapshotId, metadata_public: metadata, asset_ids, link_ids, consent }
      : all ? { scope: 'all' } : { scope: 'items', asset_ids, link_ids },
  }, { onSuccess: () => { setMessage(action === 'withdraw' ? t`Your privacy change is effective now.` : t`Consent saved. Publishing still requires an organizer action.`); setConsent(false); } });
  if (isAccessLoss(mutate.error)) return <ErrorBlock error={mutate.error} />;
  if (query.isError) return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  return <section className="grid gap-4" aria-label={t`Team gallery privacy`}>
    <h2 className="title-section">{t`Your team’s public project`}</h2>
    <p className="text-sm text-muted">{t`Any active member of the frozen team can make the project or individual items private immediately. Publishing requires the team leader’s explicit choice and an organizer’s selection.`}</p>
    {query.isLoading ? <p role="status">{t`Loading project privacy…`}</p> : <p className="text-sm">{query.data?.metadata_public ? t`Metadata is approved for publication` : t`Metadata is private`}{query.data?.publication_state ? ` · ${publicationStateLabel(query.data.publication_state)}` : ''}</p>}
    <fieldset className="grid gap-2" disabled={mutate.isPending || query.isLoading}><legend className="mb-2 text-sm font-semibold">{t`Choose individual items`}</legend>
      {items.map(item => { const key = `${item.kind}:${item.id}`; return <label key={key} className="flex min-h-11 items-center gap-3">
        <input type="checkbox" checked={checked.includes(key)} onChange={e => setChecked(e.target.checked ? [...checked, key] : checked.filter(value => value !== key))} />{item.label}
      </label>; })}
    </fieldset>
    <div className="flex flex-wrap gap-2"><button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !checked.length || !query.data?.version} onClick={() => run('withdraw')}>{t`Make chosen items private`}</button>
      <button type="button" className="desk-button min-h-11" disabled={mutate.isPending || !query.data?.version} onClick={() => run('withdraw', true)}>{t`Make the whole project private`}</button></div>
    {leader ? <fieldset className="grid gap-3 border-t border-line pt-4" disabled={mutate.isPending || query.isLoading}>
      <legend className="mb-2 font-semibold">{t`Leader’s publication choice`}</legend>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={metadata} onChange={e => setMetadata(e.target.checked)} />{t`Allow public project title and description`}</label>
      <label className="flex min-h-11 items-start gap-3"><input className="mt-1" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />{t`I approve this frozen project and only the chosen files and links for public publication.`}</label>
      <button type="button" className="desk-button-primary min-h-11" disabled={!metadata || !consent} onClick={() => run('grant')}>{t`Save public selection`}</button>
      <p className="text-sm text-muted">{t`Regranting consent does not restore an old public URL. The organizer must publish an explicit amendment.`}</p>
    </fieldset> : null}
    <ErrorBlock error={mutate.error} /><p role="status" className="text-sm text-muted">{message}</p>
  </section>;
}

const publicationStateLabel = (state: string) => ({ published: t`Published`, unpublished: t`Not published`,
  amendment_required: t`Changes needed before publishing` } as Record<string, string>)[state] ?? t`Status unknown`;

export function GalleryPrivacy(props: Parameters<typeof GalleryPrivacyForm>[0]) {
  return <PrivateProgrammeBoundary identity={`${props.scope.actorId}:${props.scope.makerspaceId}:${props.scope.eventId}:${props.teamId}`}><GalleryPrivacyForm {...props} /></PrivateProgrammeBoundary>;
}
