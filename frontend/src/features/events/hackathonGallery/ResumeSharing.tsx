import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { ErrorBlock, Field, Pagination, StatusPill } from '../../../components/ui';
import { useSharing, type MemberScope } from './api';
import { PrivateProgrammeBoundary } from './PrivateProgrammeBoundary';
import { isAccessLoss } from './accessLoss';
import { LogoLoader } from '../../../components/LogoLoader';

function ResumeSharingForm({ scope, readyResumes }: { scope: MemberScope; readyResumes: { id: number; label: string }[] }) {
  const [page, setPage] = useState(1); const { consents, mutate } = useSharing(scope, true, page);
  const [sponsorId, setSponsorId] = useState(''); const [assetId, setAssetId] = useState('');
  const [consent, setConsent] = useState(false); const [message, setMessage] = useState('');
  const sponsor = consents.data?.sponsors.find(row => row.id === Number(sponsorId));
  if (isAccessLoss(mutate.error)) return <ErrorBlock error={mutate.error} />;
  if (consents.isError) return <ErrorBlock error={consents.error} onRetry={() => void consents.refetch()} />;
  return <section className="grid gap-4" aria-label={t`Sponsor résumé sharing`}>
    <h2 className="title-section">{t`Choose who can read your résumé`}</h2>
    <p className="text-sm text-muted">{t`Sharing is optional and limited to recruiting by the sponsor you choose. Only that sponsor’s active track representatives can read it when your frozen project belongs to their track. A volunteer or mentor role alone does not qualify.`}</p>
    {consents.isLoading ? <LogoLoader label={t`Loading your sharing choices…`} size={48} className="min-h-16 py-3" /> : null}
    <form className="grid gap-3" onSubmit={e => {
      e.preventDefault(); if (!sponsor || !consent) return;
      const previous = consents.data?.results.find(row => row.sponsor_id === sponsor.id && row.asset_id === Number(assetId));
      mutate.mutate({ suffix: 'resume-consents/', version: previous?.version ?? 0, fields: {
        sponsor_id: sponsor.id, asset_id: Number(assetId), purpose: 'recruiting', consent: true, disclosure_revision: sponsor.disclosure_revision,
      } }, { onSuccess: () => { setConsent(false); setMessage(t`Your sharing choice was saved.`); } });
    }}>
      <Field label={t`Sponsor`}><select className="desk-input min-h-11" required value={sponsorId} onChange={e => { setSponsorId(e.target.value); setConsent(false); }}>
        <option value="">{t`Choose a sponsor`}</option>{consents.data?.sponsors.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
      <Field label={t`Ready event résumé`}><select className="desk-input min-h-11" required value={assetId} onChange={e => { setAssetId(e.target.value); setConsent(false); }}>
        <option value="">{t`Choose your résumé`}</option>{readyResumes.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></Field>
      {!readyResumes.length ? <p className="text-sm text-muted">{t`Upload an event résumé and wait for it to be ready before sharing it.`}</p> : null}
      <label className="flex min-h-11 items-start gap-3"><input className="mt-1" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
        <span>{t`I explicitly allow `}{sponsor?.name ?? t`the selected sponsor`} {t` to read this résumé for recruiting. I can revoke access at any time.`}</span></label>
      <button type="submit" className="desk-button-primary min-h-11" disabled={mutate.isPending || !consent || !sponsor || !assetId}>{t`Grant recruiting access`}</button>
    </form>
    <ul className="grid gap-3">{consents.data?.results.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-3">
      <div><p className="font-semibold">{row.sponsor_name}</p><p className="text-sm text-muted">{t`Résumé ${row.asset_id} · recruiting`}</p><StatusPill label={row.state === 'granted' ? t`Access granted` : t`Access revoked`} tone={row.state === 'granted' ? 'success' : 'neutral'} /></div>
      {row.state === 'granted' ? <button type="button" className="desk-button min-h-11" disabled={mutate.isPending} onClick={() => mutate.mutate({ suffix: `resume-consents/${row.id}/revoke/`, version: row.version }, { onSuccess: () => setMessage(t`Sponsor access was revoked.`) })}>{t`Revoke ${row.sponsor_name} access`}</button> : null}
    </li>)}</ul>
    <Pagination page={page} count={consents.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((consents.data?.count ?? 0) / 24)} onChange={setPage} disabled={mutate.isPending} />
    <ErrorBlock error={mutate.error} /><p role="status" className="text-sm text-muted">{message}</p>
    <p className="text-sm text-muted">{t`Replacing your résumé requires a new sharing choice. Revocation blocks future downloads; it cannot recall a file someone already downloaded.`}</p>
  </section>;
}

export function ResumeSharing(props: Parameters<typeof ResumeSharingForm>[0]) {
  return <PrivateProgrammeBoundary identity={`${props.scope.actorId}:${props.scope.makerspaceId}:${props.scope.eventId}`}><ResumeSharingForm {...props} /></PrivateProgrammeBoundary>;
}
