import { t } from "@lingui/core/macro";

import { DetailLayout } from "../../components/layouts";
import { PayLinkDialog } from "../finance/PayLinkDialog";
import { PaymentDocuments } from "../payments/PaymentDocuments";
import { PaymentRefundDialog } from "./PaymentRefundDialog";
import { RefundReceiptAmendDialog } from "./RefundReceiptAmendDialog";
import { SettlementDialog } from "./SettlementDialog";
import type { PaymentRow, RefundRow, Settlement } from "./paymentsApi";

type FormState = { pending: boolean; error?: string; cancel: () => void; confirm: (settlement: Settlement) => void };

/** The Payments panel's drawers and dialogs, split out at the file-size ceiling. State stays in the panel. */
export function PaymentsPanelDialogs({ makerspaceId, documentsOpen, onCloseDocuments, settling, settle, amending, amend,
  refundRow, onCloseRefund, payLinkRow, onClosePayLink, createLink, correctingRefund, onCloseCorrection }: {
  makerspaceId: number; documentsOpen: boolean; onCloseDocuments: () => void;
  settling: { ids: number[] } | null; settle: FormState;
  amending: PaymentRow | null; amend: FormState;
  refundRow: PaymentRow | null; onCloseRefund: () => void;
  payLinkRow: PaymentRow | null; onClosePayLink: () => void;
  createLink?: (email: string) => Promise<{ url: string; expires_at: string; emailed: boolean }>;
  correctingRefund: { paymentId: number; refund: RefundRow } | null; onCloseCorrection: () => void;
}) {
  return <>
    {documentsOpen ? <DetailLayout presentation="drawer" open onClose={onCloseDocuments}
      title={t`Billing documents`} state={{ status: "ready" }}
      main={<PaymentDocuments key={makerspaceId} makerspaceId={makerspaceId} audience="staff" initiallyExpanded />} /> : null}
    {settling ? <SettlementDialog count={settling.ids.length} pending={settle.pending} error={settle.error}
      onCancel={settle.cancel} onConfirm={settle.confirm} /> : null}
    {amending ? <SettlementDialog count={1} pending={amend.pending} error={amend.error} title={t`Correct the receipt`}
      onCancel={amend.cancel} onConfirm={amend.confirm} /> : null}
    {refundRow ? <PaymentRefundDialog key={refundRow.id} makerspaceId={makerspaceId} payment={refundRow}
      releaseDeposit={refundRow.subject_type === "loan_deposit" && refundRow.status === "paid_offline"}
      onClose={onCloseRefund} /> : null}
    {payLinkRow ? <PayLinkDialog makerspaceId={makerspaceId} paymentId={payLinkRow.id} label={payLinkRow.subject_label}
      onClose={onClosePayLink} createLink={createLink} /> : null}
    {correctingRefund ? <RefundReceiptAmendDialog makerspaceId={makerspaceId}
      paymentId={correctingRefund.paymentId} refund={correctingRefund.refund} onClose={onCloseCorrection} /> : null}
  </>;
}
