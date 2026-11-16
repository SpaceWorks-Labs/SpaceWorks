import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { OverflowMenu, StatusPill } from "../../components/ui";
import {
  formatMoney,
  invalidatePaymentViews,
  paymentStatusLabel,
  reconcilePayment,
  type Settlement,
} from "./paymentsApi";
import { SettlementDialog } from "./SettlementDialog";
import { areaErrorText } from "./areaPayments/areaPaymentsApi";
import { StaffListContext } from "./StaffListContext";
import { capabilityOn } from "../../lib/features";

/** What a recorded payment means while the space's two-person check is on (decision 242(b)). */
export const MAKER_CHECKER_NOTICE = t`Recorded. It counts as paid once a second person who can record payments confirms it. Online payment is paused for the member until then.`;

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
  const [notice, setNotice] = useState("");
  const makerChecker = capabilityOn(useContext(StaffListContext).makerspace, "billing.maker_checker");
  const mutation = useMutation({
    mutationFn: ({ action, settlement }: {
      action: "mark-offline" | "waive"; settlement?: Settlement;
    }) => reconcilePayment(makerspaceId, action, [payment!.id], false, settlement),
    onSuccess: (result, { action }) => {
      setSettling(false);
      // Two-person check (billing.maker_checker): the charge stays pending until a second
      // person who can record payments confirms it, so say so instead of looking unsaved.
      const row = Array.isArray(result) ? result[0] : result;
      setNotice(makerChecker && action === "mark-offline" && row?.status === "pending" ? MAKER_CHECKER_NOTICE : "");
      invalidatePaymentViews(queryClient, makerspaceId);
      for (const queryKey of invalidateKeys) {
        queryClient.invalidateQueries({ queryKey });
      }
    },
  });

  if (!payment) return null;
  const amount = formatMoney(payment.amount, payment.currency);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <span className="tabular-nums font-semibold text-ink">{t`Payment ${amount}`}</span>
      <StatusPill label={paymentStatusLabel(payment.status)} tone={payment.status === "pending" ? "warn" : payment.status.startsWith("paid_") ? "success" : "neutral"} />
      {payment.status === "pending" ? (
        <>
          {canRecordPayment ? <button
            className="desk-button"
            type="button"
            disabled={mutation.isPending}
            onClick={() => setSettling(true)}
          >
            {t`Mark offline`}</button> : null}
          {canWaive ? <OverflowMenu label={t`Payment actions`} actions={[{ label: t`Waive`, disabled: mutation.isPending,
            onClick: () => mutation.mutate({ action: "waive" }) }]} /> : null}
        </>
      ) : null}
      {notice ? <span role="status" className="w-full text-muted">{notice}</span> : null}
      {mutation.error && !settling ? (
        <span className="text-danger" role="alert">{areaErrorText(mutation.error)}</span>
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
