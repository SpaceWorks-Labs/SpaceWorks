import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { memberRequest } from "../../lib/api";
import { eligibilityMessage } from "../../lib/eligibilityCopy";

export function MemberLoanRenew({ makerspaceId, makerspaceSlug, requestId }: {
  makerspaceId: number; makerspaceSlug: string; requestId: number;
}) {
  const client = useQueryClient();
  const renew = useMutation({
    mutationFn: () => memberRequest<{ return_due_at: string; renewal_count: number }>(
      `/member/makerspaces/${makerspaceId}/loans/${requestId}/renew`,
      { method: "POST", body: JSON.stringify({}) },
    ),
    // The membership dashboard and the account-only borrowing page both list the loan.
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: ["member", makerspaceSlug, "activity"] }),
      client.invalidateQueries({ queryKey: ["member", "borrowing-history"] }),
    ]),
  });
  return <div className="mt-1">
    <button type="button" className="desk-button" disabled={renew.isPending || renew.isSuccess} onClick={() => renew.mutate()}>
      {renew.isPending ? t`Renewing...` : renew.isSuccess ? t`Loan renewed` : t`Renew loan`}
    </button>
    {renew.error ? <p role="alert" className="text-sm text-danger">{eligibilityMessage(renew.error) ?? renew.error.message}</p> : null}
  </div>;
}
