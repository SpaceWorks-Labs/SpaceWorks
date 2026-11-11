import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, StatusPill } from "../../../components/ui";
import { formatDate, formatDateTime } from "../../../lib/format";
import { guestErrorText } from "../../guestPasses/api";
import { communityKeys, communityStaffApi, type ConsentHistoryRow } from "../api";

const methodLabel = (method: string) => ({
  guardian_account: t`Signed in the guardian's account`, staff_recorded: t`Recorded at the desk`,
} as Record<string, string>)[method] ?? method;

function rowState(row: ConsentHistoryRow) {
  if (row.revoked_at) return <StatusPill tone="danger" label={t`Revoked ${formatDate(row.revoked_at)}`} />;
  if (row.is_live) return <StatusPill tone="success" label={t`Live until ${formatDate(row.valid_until)}`} />;
  return <StatusPill label={t`Expired ${formatDate(row.valid_until)}`} />;
}

/**
 * Every guardian consent of one minor, newest first (decision 223 k, 0.12.0). Any consent that is
 * still live can be revoked here — including an OLDER one the list row's "current consent" hides.
 */
export function MinorConsentHistory({ makerspaceId, profileId }: { makerspaceId: number; profileId: number }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState<ConsentHistoryRow | null>(null);
  const history = useQuery({ queryKey: communityKeys.consents(makerspaceId, profileId), queryFn: () => communityStaffApi.consents(makerspaceId, profileId) });
  const revoke = useMutation({
    mutationFn: (consentId: number) => communityStaffApi.revokeConsent(makerspaceId, consentId),
    onSuccess: () => { setConfirming(null); void client.invalidateQueries({ queryKey: communityKeys.all(makerspaceId) }); },
  });
  const rows = [...(history.data ?? [])].sort((a, b) => b.signed_at.localeCompare(a.signed_at) || b.id - a.id);
  return <section aria-label={t`Consent history`} className="grid w-full gap-2 border-t border-line pt-3">
    {history.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading consent history…`}</p> : null}
    {history.isError ? <p role="alert" className="text-sm text-danger">{guestErrorText(history.error)}</p> : null}
    {history.isSuccess && !rows.length ? <p className="text-sm text-muted">{t`No consent has been signed yet.`}</p> : null}
    <ul className="grid gap-2">
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-start gap-3 rounded-xl border border-line p-3">
        <div className="min-w-0 flex-1 basis-56 text-sm">
          <p className="font-semibold text-ink">{t`Version ${row.terms_version}`} · {methodLabel(row.method)}</p>
          <p className="text-muted [overflow-wrap:anywhere]">{row.signer ? t`Signed by ${row.signer}, ${formatDateTime(row.signed_at)}` : t`Signed ${formatDateTime(row.signed_at)}`}
            {row.recorded_by_name ? ` · ${t`recorded by ${row.recorded_by_name}`}` : ""}</p>
          {row.revoked_at && row.revoked_by_name ? <p className="text-muted">{t`Revoked by ${row.revoked_by_name}`}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {rowState(row)}
          {row.is_live ? <button type="button" className="desk-button-ghost min-h-11" disabled={revoke.isPending}
            onClick={() => setConfirming(row)}>{t`Revoke`}</button> : null}
        </div>
      </li>)}
    </ul>
    {revoke.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(revoke.error)}</p> : null}
    <ConfirmDialog open={Boolean(confirming)} tone="danger" title={t`Revoke this consent?`} confirmLabel={t`Revoke consent`} pending={revoke.isPending}
      message={t`The minor is refused again until a guardian signs a new consent. The revoked consent stays in the history.`}
      onCancel={() => setConfirming(null)} onConfirm={() => { if (confirming) revoke.mutate(confirming.id); }} />
  </section>;
}
