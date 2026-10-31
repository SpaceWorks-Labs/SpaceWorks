import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useLocation, useNavigate } from "react-router-dom";
import { Callout, DataTable, type Action } from "../../components/ui";
import { DetailLayout, ListLayout } from "../../components/layouts";
import { paymentColumns } from "./PaymentsRows";
import { PayLinkDialog } from "../finance/PayLinkDialog";
import { PaymentsFilters } from "./PaymentsFilters";
import { StructuredApiError, staffRequest } from "../../lib/api";
import {
  amendSettlement,
  invalidatePaymentViews,
  paymentListKey,
  paymentListPath,
  reconcilePayment,
  type PaymentRow,
  type Settlement,
} from "./paymentsApi";
import { PaymentRefundDialog } from "./PaymentRefundDialog";
import { SettlementDialog } from "./SettlementDialog";
import { useUrlListState } from "../../lib/useUrlListState";
import type { Paginated } from "../../lib/usePaginatedQuery";
import { paymentAccess } from "./paymentAccess";
import { RefundReceiptAmendDialog } from "./RefundReceiptAmendDialog";
import type { RefundRow } from "./paymentsApi";
import { PaymentDocuments } from "../payments/PaymentDocuments";

type PaymentAction = "mark-offline" | "waive";

export function PaymentsPanel({ makerspaceId, makerspaceName, actorActions = [], isSuperadmin = false }: {
  makerspaceId: number; makerspaceName?: string; actorActions?: readonly string[]; isSuperadmin?: boolean;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [documentsOpen, setDocumentsOpen] = useState(false);
  // An Event Manager holds manage_events but no finance action: the API admits them to
  // event-registration charges only, so the panel pins that subject and drops the
  // finance-only surfaces (receipts drawer, subject filter, saved views).
  const eventOnly = !isSuperadmin && !actorActions.includes("view_finance") && !actorActions.includes("record_payment")
    && actorActions.includes("manage_events");
  const forRecording = !isSuperadmin && !actorActions.includes("view_finance") && !eventOnly;
  const access = (row: PaymentRow) => paymentAccess(actorActions, isSuperadmin, row);
  useEffect(() => { setDocumentsOpen(false); }, [makerspaceId, forRecording, eventOnly]);
  const queryClient = useQueryClient();
  const list = useUrlListState({ status: "pending", subject_type: "", due_state: "", ordering: "due_at", page: "1" });
  const status = list.values.status;
  const subject = eventOnly ? "event_registration" : list.values.subject_type;
  const dueState = list.values.due_state;
  const [correctingRefund, setCorrectingRefund] = useState<{ paymentId: number; refund: RefundRow } | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [conflict, setConflict] = useState("");
  const [refundRow, setRefundRow] = useState<PaymentRow | null>(null);
  const [payLinkRow, setPayLinkRow] = useState<PaymentRow | null>(null);
  const payments = useQuery({
    queryKey: [...paymentListKey(makerspaceId, status, subject, forRecording, dueState), list.page, list.values.ordering],
    queryFn: () => staffRequest<Paginated<PaymentRow>>(paymentListPath(makerspaceId, status, subject, forRecording, dueState) + `${status || subject || forRecording || dueState ? "&" : "?"}page=${list.page}&ordering=${encodeURIComponent(list.values.ordering)}`),
  });
  useEffect(() => { setSelected([]); }, [makerspaceId, list.query]);
  // Marking paid offline is a two-step now: the API requires a receipt, so the click
  // opens the form rather than firing the mutation.
  const [settling, setSettling] = useState<{ ids: number[]; bulk: boolean } | null>(null);
  // A receipt correction appends a new receipt; the payment itself stays settled.
  const [amending, setAmending] = useState<PaymentRow | null>(null);
  const amend = useMutation({
    mutationFn: ({ id, settlement }: { id: number; settlement: Settlement }) =>
      amendSettlement(makerspaceId, id, settlement),
    onSuccess: () => {
      setAmending(null);
      invalidatePaymentViews(queryClient, makerspaceId);
    },
  });
  const mutation = useMutation({
    mutationFn: ({ action, ids, bulk, settlement }: {
      action: PaymentAction; ids: number[]; bulk: boolean; settlement?: Settlement;
    }) => reconcilePayment(makerspaceId, action, ids, bulk, settlement),
    onSuccess: () => {
      setConflict("");
      setSelected([]);
      setSettling(null);
      invalidatePaymentViews(queryClient, makerspaceId);
    },
    onError: (error) => {
      if (error instanceof StructuredApiError && error.status === 409) {
        setConflict(error.message || "This payment was already reconciled.");
        void payments.refetch();
      }
    },
  });
  const run = (action: PaymentAction, ids: number[], bulk: boolean) => {
    setConflict("");
    if (action === "mark-offline") {
      setSettling({ ids, bulk });
      return;
    }
    mutation.mutate({ action, ids, bulk });
  };
  const columns = paymentColumns({ access, pending: mutation.isPending, amendPending: amend.isPending, run,
    onAmend: setAmending, onRefund: setRefundRow,
    onCorrectRefund: (paymentId, refund) => setCorrectingRefund({ paymentId, refund }), onPayLink: setPayLinkRow });
  const statuses = [["pending", "To collect"], ["paid_online", "Paid online"], ["paid_offline", "Paid in person"], ["waived", "Waived"], ["canceled", "Cancelled"], ["", "All"]];
  const tabs = statuses.filter(([value]) => !forRecording || ["pending", "paid_offline", ""].includes(value)).map(([value, label]) => {
    const params = new URLSearchParams(location.search);
    params.set("status", value);
    params.delete("page");
    if (value !== "pending") params.delete("due_state");
    return { key: value || "all", label, href: `${location.pathname}?${params}`, count: status === value ? payments.data?.count : undefined };
  });
  const bulkActions: Action[] = [];
  if (selected.length && selected.every(id => payments.data?.results.some(row => row.id === id && row.status === "pending" && access(row).record))) bulkActions.push({ label: "Mark paid in person", pending: mutation.isPending, onClick: () => run("mark-offline", selected, true) });
  if (selected.length && selected.every(id => payments.data?.results.some(row => row.id === id && row.status === "pending" && access(row).waive))) bulkActions.push({ label: "Waive", pending: mutation.isPending, onClick: () => run("waive", selected, true) });
  return <div onClickCapture={event => {
    const anchor = (event.target as HTMLElement).closest('nav[aria-label="Page sections"] a');
    if (!anchor || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const destination = new URL((anchor as HTMLAnchorElement).href);
    navigate(destination.pathname + destination.search);
  }}><ListLayout
    header={{ title: "Payments", subtitle: eventOnly ? `Event registration fees owed to ${makerspaceName ?? "your makerspace"}, and how they were paid.` : `Money owed to ${makerspaceName ?? "your makerspace"}, and how it was paid.`,
      secondary: !forRecording && !eventOnly ? { label: "Billing documents", onClick: () => setDocumentsOpen(true) } : undefined }}
    state={payments.isLoading ? { status: "loading" } : payments.error && !payments.data
      ? { status: "error", error: "Couldn't load payments. Try again.", onRetry: () => { void payments.refetch(); } } : { status: "ready" }}
    isEmpty={payments.data?.count === 0}
    empty={{ message: status === "pending" ? "Nothing to collect. Every charge here is paid or waived." : "No payments yet. Charges appear here when someone books, registers or borrows." }}
    filtered={Boolean(list.values.subject_type || dueState)} filteredEmpty={{ message: "No matching payments. Try another filter.", action: { label: "Clear filters", onClick: () => list.update({ subject_type: "", due_state: "" }) } }}
    tabs={tabs} activeTab={status || "all"}
    filters={{ toolbar: <PaymentsFilters list={list} makerspaceId={makerspaceId} eventOnly={eventOnly} /> }}
    bulkBar={{ count: selected.length, actions: bulkActions, onClear: () => setSelected([]) }}
    pagination={{ page: list.page, count: payments.data?.count ?? 0, pageSize: 24, onChange: list.setPage }}
    body={{ kind: "table", table: <DataTable listState={list} columns={columns} data={payments.data?.results ?? []}
      selectedIds={selected} onSelectionChange={ids => setSelected(ids.map(Number))} emptyTitle="No matching payments" /> }}
    detail={<>
      {!forRecording && !eventOnly && documentsOpen ? <DetailLayout presentation="drawer" open onClose={() => setDocumentsOpen(false)}
        title="Billing documents" state={{ status: "ready" }}
        main={<PaymentDocuments key={makerspaceId} makerspaceId={makerspaceId} audience="staff" initiallyExpanded />} /> : null}
      {settling ? (
        <SettlementDialog
          count={settling.ids.length}
          pending={mutation.isPending}
          error={mutation.error?.message}
          onCancel={() => setSettling(null)}
          onConfirm={(settlement) =>
            mutation.mutate({
              action: "mark-offline",
              ids: settling.ids,
              bulk: settling.bulk,
              settlement,
            })
          }
        />
      ) : null}
      {amending ? (
        <SettlementDialog
          count={1}
          pending={amend.isPending}
          error={amend.error?.message}
          title="Correct the receipt"
          onCancel={() => { setAmending(null); amend.reset(); }}
          onConfirm={(settlement) => amend.mutate({ id: amending.id, settlement })}
        />
      ) : null}
      {amend.error && !amending ? <p role="alert" className="mb-3 text-sm text-danger">{amend.error.message}</p> : null}
      {conflict ? <div role="alert"><Callout size="inline" tone="warn" lead="Someone else updated this charge. Refreshed." body={conflict} /></div> : null}
      {mutation.error && !conflict && !settling ? <p role="alert" className="mb-3 text-sm text-danger">{mutation.error.message}</p> : null}
      {refundRow ? (
        <PaymentRefundDialog
          key={refundRow.id}
          makerspaceId={makerspaceId}
          payment={refundRow}
          releaseDeposit={refundRow.subject_type === "loan_deposit" && refundRow.status === "paid_offline"}
          onClose={() => setRefundRow(null)}
        />
      ) : null}
      {payLinkRow ? <PayLinkDialog makerspaceId={makerspaceId} paymentId={payLinkRow.id} label={payLinkRow.subject_label}
        onClose={() => setPayLinkRow(null)} /> : null}
      {correctingRefund ? <RefundReceiptAmendDialog makerspaceId={makerspaceId}
        paymentId={correctingRefund.paymentId} refund={correctingRefund.refund}
        onClose={() => setCorrectingRefund(null)} /> : null}
    </>}
  /></div>;
}
