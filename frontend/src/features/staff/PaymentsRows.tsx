import { t } from "@lingui/core/macro";
import { OverflowMenu, RelativeTime, StatusPill, type Action, type DataTableColumn } from "../../components/ui";
import { PaymentDueBadge } from "./PaymentDueBadge";
import { paymentAccess } from "./paymentAccess";
import { formatMoney, PAYMENT_STATUSES, PAYMENT_SUBJECTS, settlementLabel, type PaymentRow, type RefundRow } from "./paymentsApi";

export function paymentColumns({ access, pending, amendPending, run, onAmend, onRefund, onCorrectRefund, onPayLink, onReminder }: {
  access: (row: PaymentRow) => ReturnType<typeof paymentAccess>;
  pending: boolean; amendPending: boolean;
  run: (action: "mark-offline" | "waive", ids: number[], bulk: boolean) => void;
  onAmend: (row: PaymentRow) => void; onRefund: (row: PaymentRow) => void;
  onCorrectRefund: (paymentId: number, refund: RefundRow) => void;
  /** Lane L5: offered only when the server says a pay link is possible for the row. */
  onPayLink?: (row: PaymentRow) => void;
  /** Decision 242(b): the own-area queue's one-off email nudge, offered for charges an account owes. */
  onReminder?: { send: (row: PaymentRow) => void; available: (row: PaymentRow) => boolean; pending: boolean };
}): DataTableColumn<PaymentRow>[] {
  return [
    { key: "subject_label", header: t`Subject`, render: row => <span className="font-semibold text-ink">{row.subject_label}</span> },
    // Its own column again, so saved column choices that include Type keep it.
    { key: "subject_type", header: t`Type`, render: row => <span className="text-muted">{labelFor(PAYMENT_SUBJECTS, row.subject_type)}</span> },
    { key: "status", header: t`Status`, render: row => <StatusPill label={labelFor(PAYMENT_STATUSES, row.status)} tone={row.status === "pending" ? "warn" : row.status.startsWith("paid_") ? "success" : "neutral"} /> },
    { key: "due_at", header: t`Due`, render: row => <PaymentDueBadge payment={row} /> },
    { key: "amount", header: t`Amount`, render: row => formatMoney(row.amount, row.currency), className: "font-semibold tabular-nums text-ink md:text-right" },
    { key: "refunded_amount", header: t`Refunded`, render: row => Number(row.refunded_amount) > 0 ? formatMoney(row.refunded_amount, row.currency) : "—", className: "text-muted tabular-nums" },
    { key: "settlement", header: t`Received`, render: row => row.settlement ? <div className="grid justify-items-start gap-1"><span>{settlementLabel(row.settlement)}</span>{row.settlement.corrected ? <StatusPill label={t`Corrected`} /> : null}</div> : "—" },
    { key: "created_at", header: t`Created`, render: row => <RelativeTime date={row.created_at} /> },
    { key: "actions", header: t`Actions`, render: row => {
      const permissions = access(row);
      const actions: Action[] = [];
      if (row.status === "pending" && permissions.waive) actions.push({ label: t`Waive`, disabled: pending, onClick: () => run("waive", [row.id], false) });
      if (row.status === "paid_offline" && row.settlement && permissions.record) actions.push({ label: t`Correct receipt`, disabled: amendPending, onClick: () => onAmend(row) });
      if ((row.status === "paid_online" || row.status === "paid_offline") && permissions.refund) actions.push({ label: row.subject_type === "loan_deposit" && row.status === "paid_offline" ? t`Release deposit` : t`Refund`, onClick: () => onRefund(row) });
      if (onPayLink && row.ledger_flags?.pay_link_available && permissions.record) actions.push({ label: t`Pay link`, onClick: () => onPayLink(row) });
      if (onReminder && row.status === "pending" && permissions.record && onReminder.available(row)) actions.push({ label: t`Send reminder`, disabled: onReminder.pending, onClick: () => onReminder.send(row) });
      row.refunds?.filter(refund => refund.provider === "manual" && !refund.corrected).forEach(refund => {
        if (permissions.refund) actions.push({ label: t`Correct refund #${refund.id}`, onClick: () => onCorrectRefund(row.id, refund) });
      });
      return <div className="flex flex-wrap items-center gap-2">
        {/* Two-person check (billing.maker_checker): a recorded payment waits for a second person. */}
        {row.status === "pending" && row.ledger_flags?.awaiting_confirmation_id ? <StatusPill tone="info" label={t`Waiting for a second person`} />
          : row.status === "pending" && permissions.record ? <button className="desk-button" type="button" disabled={pending} onClick={() => run("mark-offline", [row.id], false)}>{t`Mark paid`}</button> : null}
        <OverflowMenu label={t`Actions for ${row.subject_label}`} actions={actions} />
      </div>;
    } },
  ];
}

function labelFor(options: readonly (readonly [string, string])[], value: string) {
  return options.find(([key]) => key === value)?.[1] ?? value.replace(/_/g, " ");
}
