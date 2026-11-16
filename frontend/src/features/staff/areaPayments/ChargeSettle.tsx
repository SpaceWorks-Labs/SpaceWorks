import { useContext } from "react";

import { StaffListContext } from "../StaffListContext";
import { PaymentReconcileActions } from "../PaymentReconcileActions";
import { paymentAccess } from "../paymentAccess";
import type { PaymentRow } from "../paymentsApi";

export type SettleableCharge = {
  id: number; status?: string; amount: string; currency: string; subject_type: string;
};

/**
 * Decision 242(a): "Mark offline" (with the receipt) and "Waive" on one charge wherever the record is
 * shown: a machine job, a machine session, a loan charge. Each button appears only when the signed-in
 * staff member may take it (`paymentAccess`, the twin of `reconciliation_authority`); the server
 * re-checks subject authority, machine-type scope and maker-checker on every request.
 */
export function ChargeSettle({ makerspaceId, charge, invalidateKeys }: {
  /** Defaults to the console's selected space (records shown in a space console belong to it). */
  makerspaceId?: number; charge: SettleableCharge | null | undefined; invalidateKeys?: readonly (readonly unknown[])[];
}) {
  const { actions = [], isSuperadmin = false, makerspace } = useContext(StaffListContext);
  const spaceId = makerspaceId ?? makerspace?.id;
  if (!charge || charge.status !== "pending" || !spaceId) return null;
  const access = paymentAccess(actions, isSuperadmin, {
    subject_type: charge.subject_type as PaymentRow["subject_type"], status: "pending",
  });
  if (!access.record && !access.waive) return null;
  return <PaymentReconcileActions makerspaceId={spaceId} invalidateKeys={invalidateKeys}
    payment={{ id: charge.id, status: "pending", amount: charge.amount, currency: charge.currency }}
    canRecordPayment={access.record} canWaive={access.waive} />;
}
