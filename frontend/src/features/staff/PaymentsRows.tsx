import { t } from "@lingui/core/macro";
import { OverflowMenu, RelativeTime, StatusPill, type Action, type DataTableColumn } from "../../components/ui";
import { PaymentDueBadge } from "./PaymentDueBadge";
import { paymentAccess } from "./paymentAccess";
import { formatMoney, PAYMENT_STATUSES, PAYMENT_SUBJECTS, settlementLabel, type PaymentRow, type RefundRow } from "./paymentsApi";

export function paymentColumns({ access, pending, amendPending, run, onAmend, onRefund, onCorrectRefund, onPayLink }: {
  access: (row: PaymentRow) => ReturnType<typeof paymentAccess>;
  pending: boolean; amendPending: boolean;
  run: (action: "mark-offline" | "waive", ids: number[], bulk: boolean) => void;
  onAmend: (row: PaymentRow) => void; onRefund: (row: PaymentRow) => void;
  onCorrectRefund: (paymentId: number, refund: RefundRow) => void;
  /** Lane L5: offered only when the server says a pay link is possible for the row. */
  onPayLink?: (row: PaymentRow) => void;
}): DataTableColumn<PaymentRow>[] {
  return [
    { key: "subject_label", header: "Subject", render: row => <span className="font-semibold text-ink">{row.subject_label}</span> },
    // Its own column again, so saved column choices that include Type keep it.
    { key: "subject_type", header: "Type", render: row => <span className="text-muted">{labelFor(PAYMENT_SUBJECTS, row.subject_type)}</span> },
    { key: "status", header: "Status", render: row => <StatusPill label={labelFor(PAYMENT_STATUSES, row.status)} tone={row.status === "pending" ? "warn" : row.status.startsWith("paid_") ? "success" : "neutral"} /> },
    { key: "due_at", header: "Due", render: row => <PaymentDueBadge payment={row} /> },
    { key: "amount", header: "Amount", render: row => formatMoney(row.amount, row.currency), className: "font-semibold tabular-nums text-ink md:text-right" },
    { key: "refunded_amount", header: "Refunded", render: row => Number(row.refunded_amount) > 0 ? formatMoney(row.refunded_amount, row.currency) : "—", className: "text-muted tabular-nums" },
    { key: "settlement", header: "Received", render: row => row.settlement ? <div className="grid justify-items-start gap-1"><span>{settlementLabel(row.settlement)}</span>{row.settlement.corrected ? <StatusPill label={t`Corrected`} /> : null}</div> : "—" },
    { key: "created_at", header: "Created", render: row => <RelativeTime date={row.created_at} /> },
    { key: "actions", header: "Actions", render: row => {
      const permissions = access(row);
      const actions: Action[] = [];
      if (row.status === "pending" && permissions.waive) actions.push({ label: t`Waive`, disabled: pending, onClick: () => run("waive", [row.id], false) });
      if (row.status === "paid_offline" && row.settlement && permissions.record) actions.push({ label: t`Correct receipt`, disabled: amendPending, onClick: () => onAmend(row) });
      if ((row.status === "paid_online" || row.status === "paid_offline") && permissions.refund) actions.push({ label: row.subject_type === "loan_deposit" && row.status === "paid_offline" ? t`Release deposit` : t`Refund`, onClick: () => onRefund(row) });
      if (onPayLink && row.ledger_flags?.pay_link_available && permissions.record) actions.push({ label: t`Pay link`, onClick: () => onPayLink(row) });
      row.refunds?.filter(refund => refund.provider === "manual" && !refund.corrected).forEach(refund => {
        if (permissions.refund) actions.push({ label: t`Correct refund #${refund.id}`, onClick: () => onCorrectRefund(row.id, refund) });
      });
      return <div className="flex flex-wrap items-center gap-2">
        {row.status === "pending" && permissions.record ? <button className="desk-button" type="button" disabled={pending} onClick={() => run("mark-offline", [row.id], false)}>{t`Mark paid`}</button> : null}
        <OverflowMenu label={t`Actions for ${row.subject_label}`} actions={actions} />
      </div>;
    } },
  ];
}

function labelFor(options: readonly (readonly [string, string])[], value: string) {
  return options.find(([key]) => key === value)?.[1] ?? value.replace(/_/g, " ");
}
