import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog } from "../../components/ui";
import { memberRequest } from "../../lib/api";

export const WITHDRAWABLE = ["pending_approval", "accepted"];

/** Withdraw my own request before anything is handed over (`loans.withdrawals`). */
export function MemberRequestWithdraw({ makerspaceId, makerspaceSlug, requestId }: { makerspaceId: number; makerspaceSlug: string; requestId: number }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const withdraw = useMutation({
    mutationFn: () => memberRequest<{ id: number; status: string; closed_at: string | null }>(
      `/member/makerspaces/${makerspaceId}/requests/${requestId}/withdraw`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      setConfirming(false);
      void client.invalidateQueries({ queryKey: ["member", makerspaceSlug, "activity"] });
      // The account-only borrowing history page lists the same request.
      void client.invalidateQueries({ queryKey: ["member", "borrowing-history"] });
    },
  });
  if (withdraw.isSuccess) return <p role="status" className="text-sm text-muted">{t`Request withdrawn.`}</p>;
  return <div className="grid gap-1">
    <button type="button" className="desk-button-ghost" disabled={withdraw.isPending} onClick={() => setConfirming(true)}>{t`Withdraw`}</button>
    <ConfirmDialog open={confirming} title={t`Withdraw this request?`} message={t`Staff stop preparing it and any items held for you go back on the shelf.`}
      confirmLabel={t`Withdraw request`} cancelLabel={t`Keep it`} tone="danger" pending={withdraw.isPending}
      onConfirm={() => withdraw.mutate()} onCancel={() => setConfirming(false)} />
    {withdraw.error ? <p role="alert" className="text-sm text-danger">{withdraw.error.message}</p> : null}
  </div>;
}
