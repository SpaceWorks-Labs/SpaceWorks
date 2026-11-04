import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { OverflowMenu, StatusPill } from "../../components/ui";
import {
  invalidatePaymentViews,
  reconcilePayment,
  type Settlement,
} from "./paymentsApi";
import { SettlementDialog } from "./SettlementDialog";

export type PaymentSummary = {
  id: number;
  status: "pending" | "paid_online" | "paid_offline" | "waived" | "canceled";
  amount: string;
  currency: string;
};

export function PaymentReconcileActions({
  makerspaceId,
  payment,
  invalidateKeys = [],
  canRecordPayment = true,
  canWaive = true,
}: {
  makerspaceId: number;
  payment: PaymentSummary | null;
  invalidateKeys?: readonly (readonly unknown[])[];
  canRecordPayment?: boolean;
  canWaive?: boolean;
}) {
  const queryClient = useQueryClient();
  // Marking paid offline needs the receipt the API requires, so the button opens the
  // form rather than settling straight away.
  const [settling, setSettling] = useState(false);
  const mutation = useMutation({
    mutationFn: ({ action, settlement }: {
      action: "mark-offline" | "waive"; settlement?: Settlement;
    }) => reconcilePayment(makerspaceId, action, [payment!.id], false, settlement),
    onSuccess: () => {
      setSettling(false);
      invalidatePaymentViews(queryClient, makerspaceId);
      for (const queryKey of invalidateKeys) {
        queryClient.invalidateQueries({ queryKey });
      }
    },
  });

  if (!payment) return null;
  const amount = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: payment.currency.toUpperCase(),
  }).format(Number(payment.amount));
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <span className="tabular-nums font-semibold text-ink">Payment {amount}</span>
      <StatusPill label={payment.status[0].toUpperCase() + payment.status.slice(1).replace(/_/g, " ")} tone={payment.status === "pending" ? "warn" : payment.status.startsWith("paid_") ? "success" : "neutral"} />
      {payment.status === "pending" ? (
        <>
          {canRecordPayment ? <button
            className="desk-button"
            type="button"
            disabled={mutation.isPending}
            onClick={() => setSettling(true)}
          >
            Mark offline
          </button> : null}
          {canWaive ? <OverflowMenu label="Payment actions" actions={[{ label: "Waive", disabled: mutation.isPending,
            onClick: () => mutation.mutate({ action: "waive" }) }]} /> : null}
        </>
      ) : null}
      {mutation.error && !settling ? (
        <span className="text-danger" role="alert">{mutation.error.message}</span>
      ) : null}
      {settling ? (
        <div className="w-full">
          <SettlementDialog
            count={1}
            pending={mutation.isPending}
            error={mutation.error?.message}
            onCancel={() => setSettling(false)}
            onConfirm={(settlement) =>
              mutation.mutate({ action: "mark-offline", settlement })
            }
          />
        </div>
      ) : null}
    </div>
  );
}
