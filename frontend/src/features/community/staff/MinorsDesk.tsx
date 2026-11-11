import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, EmptyState, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText } from "../../guestPasses/api";
import { MembershipPagination } from "../../staff/MembershipPagination";
import { communityKeys, communityStaffApi, type Consent, type MinorProfile } from "../api";
import { DeskConsentDialog, RecordMinorDialog } from "./MinorDialogs";
import { GuardianTermsPanel } from "./GuardianTermsPanel";
import { MinorConsentHistory } from "./MinorConsentHistory";

/**
 * Members › Minors (decision 223 k): who is recorded as under age, their guardian, and whether a
 * current consent is on file. Never the birth date. manage_members; publishing the consent text
 * needs manage_makerspace.
 */
export function MinorsDesk({ makerspaceId, canManageMakerspace }: { makerspaceId: number; canManageMakerspace: boolean }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [recording, setRecording] = useState(false);
  const [consentFor, setConsentFor] = useState<MinorProfile | null>(null);
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const [lastConsent, setLastConsent] = useState<{ profile: number; consent: Consent } | null>(null);
  // Revoking the current consent refuses the minor again, so it is confirmed like the history list.
  const [revoking, setRevoking] = useState<MinorProfile | null>(null);
  const minors = useQuery({ queryKey: communityKeys.minors(makerspaceId, page), queryFn: () => communityStaffApi.minors(makerspaceId, page) });
  const refresh = () => client.invalidateQueries({ queryKey: communityKeys.all(makerspaceId) });
  const clear = useMutation({ mutationFn: (profileId: number) => communityStaffApi.clearMinor(makerspaceId, profileId), onSuccess: refresh });
  const revoke = useMutation({ mutationFn: (consentId: number) => communityStaffApi.revokeConsent(makerspaceId, consentId),
    onSuccess: () => { setLastConsent(null); setRevoking(null); void refresh(); } });
  const rows = minors.data?.results ?? [];
  return <div className="grid gap-5">
    <section aria-label={t`Minors`} className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-prose text-sm text-muted">{t`People under the adult age need a current guardian consent. Staff see an age or an "under age" declaration, never a birth date.`}</p>
        <button type="button" className="desk-button-primary min-h-11" onClick={() => setRecording(true)}>{t`Record a minor`}</button>
      </div>
      {minors.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading minors…`}</p> : null}
      {minors.isError ? <p role="alert" className="text-sm text-danger">{guestErrorText(minors.error)}</p> : null}
      {minors.isSuccess && !rows.length ? <EmptyState message={t`No minors recorded.`} /> : null}
      <ul className="grid gap-3">
        {rows.map((row) => <li key={row.id} className="flex flex-wrap items-start gap-3 rounded-2xl border border-line bg-panel p-4">
          <div className="min-w-0 flex-1 basis-56">
            <p className="title-section break-words">{row.user_name}</p>
            <p className="text-sm text-muted">{row.age !== null ? t`Age ${row.age}` : t`Declared under age`}
              {row.guardian_name || row.guardian_email ? ` · ${t`Guardian: ${row.guardian_name || row.guardian_email}`}` : ` · ${t`No guardian recorded`}`}</p>
            {row.guardian_email || row.guardian_phone ? <p className="text-sm text-muted [overflow-wrap:anywhere]">{[row.guardian_email, row.guardian_phone].filter(Boolean).join(" · ")}</p> : null}
            {row.current_consent_id !== null && !row.cleared_at ? <p className="text-sm text-muted">
              {row.current_consent_signed_at ? t`Current consent: version ${row.current_consent_version ?? ""}, signed ${formatDate(row.current_consent_signed_at)}` : t`Current consent: version ${row.current_consent_version ?? ""}`}</p> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {row.cleared_at ? <StatusPill label={t`No longer a minor`} />
              : row.consent_state === "valid" ? <StatusPill tone="success" label={row.consent_valid_until ? t`Consent until ${formatDate(row.consent_valid_until)}` : t`Consent on file`} />
              : <StatusPill tone="warn" label={t`Consent needed`} />}
            {!row.cleared_at ? <>
              <button type="button" className="desk-button min-h-11" onClick={() => setConsentFor(row)}>{t`Record desk signature`}</button>
              {row.current_consent_id !== null && lastConsent?.profile !== row.id ? <button type="button" className="desk-button-ghost min-h-11" disabled={revoke.isPending}
                onClick={() => setRevoking(row)}>{t`Revoke consent`}</button> : null}
              <button type="button" className="desk-button-ghost min-h-11" disabled={clear.isPending} onClick={() => clear.mutate(row.id)}>{t`No longer a minor`}</button>
            </> : null}
            <button type="button" className="desk-button-ghost min-h-11" aria-expanded={historyFor === row.id}
              onClick={() => setHistoryFor(historyFor === row.id ? null : row.id)}>{historyFor === row.id ? t`Hide consent history` : t`Consent history`}</button>
          </div>
          {lastConsent?.profile === row.id ? <div role="status" className="flex w-full flex-wrap items-center gap-3 text-sm text-success-ink">
            {t`Consent recorded on version ${lastConsent.consent.terms_version}.`}
            <button type="button" className="desk-button-ghost min-h-11" disabled={revoke.isPending} onClick={() => revoke.mutate(lastConsent.consent.id)}>{t`Undo: revoke this consent`}</button>
          </div> : null}
          {historyFor === row.id ? <MinorConsentHistory makerspaceId={makerspaceId} profileId={row.id} /> : null}
        </li>)}
      </ul>
      {clear.error || revoke.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(clear.error ?? revoke.error)}</p> : null}
      <MembershipPagination label="minors" page={page} next={minors.data?.next} previous={minors.data?.previous} fetching={minors.isFetching} onPage={setPage} />
    </section>
    <GuardianTermsPanel makerspaceId={makerspaceId} canPublish={canManageMakerspace} />
    <ConfirmDialog open={Boolean(revoking)} tone="danger" title={revoking ? t`Revoke ${revoking.user_name}'s consent?` : t`Revoke this consent?`}
      confirmLabel={t`Revoke consent`} pending={revoke.isPending}
      message={t`The minor is refused again until a guardian signs a new consent. The revoked consent stays in the history.`}
      onCancel={() => setRevoking(null)} onConfirm={() => { if (revoking?.current_consent_id != null) revoke.mutate(revoking.current_consent_id); }} />
    {recording ? <RecordMinorDialog makerspaceId={makerspaceId} onClose={() => setRecording(false)} onSaved={() => { setRecording(false); void refresh(); }} /> : null}
    {consentFor ? <DeskConsentDialog makerspaceId={makerspaceId} minor={consentFor} onClose={() => setConsentFor(null)}
      onSaved={(consent) => { setLastConsent({ profile: consentFor.id, consent }); setConsentFor(null); void refresh(); }} /> : null}
  </div>;
}
