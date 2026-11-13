import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";

type Suggestion = { applies: boolean; suggested_amount: string | null; currency: string; band: string };

/** X20 + X21 on a membership refund case: the policy's suggestion if cancelled today, and the
 * "keep membership" tick (unticked, approving ends the term the payment bought). */
export function MembershipRefundExtras({ makerspaceId, caseId, keepMembership, onKeepMembership }: {
  makerspaceId: number; caseId: number; keepMembership: boolean; onKeepMembership: (keep: boolean) => void;
}) {
  const suggestion = useQuery({ queryKey: ["refund-cases", makerspaceId, "membership-suggestion", caseId],
    queryFn: () => staffRequest<Suggestion>(`/admin/makerspaces/${makerspaceId}/refund-cases/${caseId}/membership-suggestion`), retry: false });
  const data = suggestion.data;
  return <div className="grid gap-2">
    {data?.applies && data.suggested_amount != null ? <p className="text-sm text-ink">{t`If cancelled today the membership policy suggests${" "}`}
      <strong>{data.suggested_amount} {data.currency.toUpperCase()}</strong>{data.band ? ` (${data.band.replace("_", " ")})` : ""}.</p> : null}
    <label className="flex min-h-11 items-center gap-2 text-sm">
      <input className="h-4 w-4" type="checkbox" checked={keepMembership} onChange={(event) => onKeepMembership(event.target.checked)} />
      {t`Keep the membership (do not end the term this payment bought)`}</label>
    {!keepMembership ? <p className="text-sm text-muted">{t`Approving ends that term now, so its card stops verifying. An early-paid term that has not started is cancelled.`}</p> : null}
  </div>;
}
