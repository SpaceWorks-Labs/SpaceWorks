import { t } from "@lingui/core/macro";
import { useContext, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useLocation, useNavigate } from "react-router-dom";
import { Callout, DataTable, type Action } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { capabilityOn } from "../../lib/features";
import { paymentColumns } from "./PaymentsRows";
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
import { useUrlListState } from "../../lib/useUrlListState";
import type { Paginated } from "../../lib/usePaginatedQuery";
import { paymentAccess } from "./paymentAccess";
import type { RefundRow } from "./paymentsApi";
import { StaffListContext } from "./StaffListContext";
import { MAKER_CHECKER_NOTICE } from "./PaymentReconcileActions";
import { PaymentsPanelDialogs } from "./PaymentsPanelDialogs";
import { TestModeBadge, usePaymentTestMode } from "./paymentTestMode";
import { AreaPaymentGroups } from "./areaPayments/AreaPaymentGroups";
import { AreaClaimsList } from "./areaPayments/AreaClaimsList";
import {
  areaErrorText, areaKeys, areaLabel, areaPaymentsApi, ownedAreas, type AreaKey, type AreaQueueRow,
} from "./areaPayments/areaPaymentsApi";

type PaymentAction = "mark-offline" | "waive";

/**
 * Money owed to the space. Finance staff read the whole ledger, grouped by area above the list
 * (decision 241/242: the Space Manager's combined view). Everyone else who owns a charge type --
 * the Inventory, Machine, Event, Booking and Shop Managers -- gets the own-area queue
 * (`area-queue`, decision 242(a)): only their own charges, never donations or payouts.
 * `area` pins the queue to one area (an area console's own Payments drawer).
 */
export function PaymentsPanel({ makerspaceId, makerspaceName, actorActions = [], isSuperadmin = false, area, embedded = false }: {
  makerspaceId: number; makerspaceName?: string; actorActions?: readonly string[]; isSuperadmin?: boolean;
  area?: AreaKey; embedded?: boolean;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { makerspace } = useContext(StaffListContext);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const finance = isSuperadmin || actorActions.includes("view_finance");
  // The handout desk with record_payment keeps the recording ledger; nobody else gets it.
  const forRecording = !finance && !area && actorActions.includes("record_payment");
  const areaMode = Boolean(area) || (!finance && !forRecording);
  const access = (row: PaymentRow) => paymentAccess(actorActions, isSuperadmin, row);
  const prefix = embedded ? "pay_" : "";
  useEffect(() => { setDocumentsOpen(false); }, [makerspaceId, forRecording, areaMode]);
  const queryClient = useQueryClient();
  const list = useUrlListState({ status: "pending", subject_type: "", due_state: "", area: "", view: "", ordering: "due_at", page: "1" }, prefix);
  // `?payment=<id>` (search, schedule): that charge, whatever its status.
  const linkedPayment = Number(new URLSearchParams(location.search).get(`${prefix}payment`)) || 0;
  const status = linkedPayment ? "" : list.values.status;
  const subject = areaMode ? "" : list.values.subject_type;
  const dueState = list.values.due_state;
  const areaFilter = area ?? list.values.area;
  // An area filter on the finance ledger reads the queue too.
  const useQueue = areaMode || Boolean(areaFilter);
  const claimsOn = capabilityOn(makerspace, "billing.offline_claims");
  const makerChecker = capabilityOn(makerspace, "billing.maker_checker");
  const testMode = usePaymentTestMode(makerspaceId); // Parity C20
  const showClaims = claimsOn && list.values.view === "claims";
  const filters = { area: areaFilter, status: status || "all", subject_type: subject, due_state: dueState, ordering: list.values.ordering, page: list.page };
  const [correctingRefund, setCorrectingRefund] = useState<{ paymentId: number; refund: RefundRow } | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [conflict, setConflict] = useState("");
  const [notice, setNotice] = useState("");
  const [refundRow, setRefundRow] = useState<PaymentRow | null>(null);
  const [payLinkRow, setPayLinkRow] = useState<PaymentRow | null>(null);
  const payments = useQuery({
    queryKey: useQueue ? areaKeys.list(makerspaceId, filters)
      : [...paymentListKey(makerspaceId, status, subject, forRecording, dueState), list.page, list.values.ordering],
    queryFn: () => useQueue ? areaPaymentsApi.list(makerspaceId, filters)
      : staffRequest<Paginated<PaymentRow>>(paymentListPath(makerspaceId, status, subject, forRecording, dueState) + `${status || subject || forRecording || dueState ? "&" : "?"}page=${list.page}&ordering=${encodeURIComponent(list.values.ordering)}`),
    enabled: !showClaims,
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
    onSuccess: (result, { action }) => {
      setConflict("");
      setSelected([]);
      setSettling(null);
      // Two-person check: a recorded payment stays pending until a second person confirms it.
      const rows = Array.isArray(result) ? result : [result];
      setNotice(makerChecker && action === "mark-offline" && rows.some(row => row?.status === "pending") ? MAKER_CHECKER_NOTICE : "");
      invalidatePaymentViews(queryClient, makerspaceId);
    },
    onError: (error) => {
      setNotice("");
      if (error instanceof StructuredApiError && error.status === 409) {
        setConflict(areaErrorText(error) || "This payment was already reconciled.");
        void payments.refetch();
      }
    },
  });
  const reminder = useMutation({
    mutationFn: (row: PaymentRow) => areaPaymentsApi.reminder(makerspaceId, row.id),
    onSuccess: () => setNotice(t`Reminder sent to the payer's email.`),
    onError: () => setNotice(""),
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
    onCorrectRefund: (paymentId, refund) => setCorrectingRefund({ paymentId, refund }), onPayLink: setPayLinkRow,
    onReminder: areaMode ? { send: row => reminder.mutate(row), pending: reminder.isPending,
      available: row => Boolean((row as AreaQueueRow).member_id) } : undefined });
  const statuses = [["pending", t`To collect`], ["paid_online", t`Paid online`], ["paid_offline", t`Paid in person`], ["waived", t`Waived`], ["canceled", t`Cancelled`], ["", t`All`]];
  const tab = (key: string, label: string, patch: Record<string, string | null>, count?: number) => {
    const params = new URLSearchParams(location.search);
    // `null` drops a key; "" is kept, because `status=` is how the All tab says "every status".
    for (const [name, value] of Object.entries(patch)) { if (value === null) params.delete(prefix + name); else params.set(prefix + name, value); }
    params.delete(`${prefix}page`);
    return { key, label, href: `${location.pathname}?${params}`, count };
  };
  const statusTabs = statuses.filter(([value]) => !forRecording || ["pending", "paid_offline", ""].includes(value))
    .map(([value, label]) => tab(value || "all", label, { status: value, view: null, ...(value !== "pending" ? { due_state: null } : {}) },
      !showClaims && status === value ? payments.data?.count : undefined));
  const tabs = claimsOn && !forRecording ? [...statusTabs, tab("claims", t`Say they paid`, { view: "claims", status: null })] : statusTabs;
  const bulkActions: Action[] = [];
  if (selected.length && selected.every(id => payments.data?.results.some(row => row.id === id && row.status === "pending" && access(row).record))) bulkActions.push({ label: t`Mark paid in person`, pending: mutation.isPending, onClick: () => run("mark-offline", selected, true) });
  if (selected.length && selected.every(id => payments.data?.results.some(row => row.id === id && row.status === "pending" && access(row).waive))) bulkActions.push({ label: t`Waive`, pending: mutation.isPending, onClick: () => run("waive", selected, true) });
  const owner = makerspaceName ?? t`your makerspace`;
  const subtitle = area ? t`${areaLabel(area)} charges owed to ${owner}, and how they were paid.`
    : areaMode ? t`Charges for the areas you run, owed to ${owner}, and how they were paid.`
    : t`Money owed to ${owner}, and how it was paid.`;
  return <div onClickCapture={event => {
    const anchor = (event.target as HTMLElement).closest('nav[aria-label="Page sections"] a');
    if (!anchor || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const destination = new URL((anchor as HTMLAnchorElement).href);
    navigate(destination.pathname + destination.search);
  }}><ListLayout standalone={embedded ? false : undefined}
    header={{ title: t`Payments`, subtitle, meta: testMode ? <TestModeBadge /> : undefined,
      secondary: finance ? { label: t`Billing documents`, onClick: () => setDocumentsOpen(true) } : undefined }}
    callout={makerChecker ? { size: "inline", tone: "warn", lead: t`Two-person check is on.`,
      body: t`A payment you record waits until a second person who can record payments confirms it. You can't confirm your own. Online payment is paused for the member while it waits.` } : undefined}
    state={showClaims ? { status: "ready" } : payments.isLoading ? { status: "loading" } : payments.error && !payments.data
      ? { status: "error", error: t`Couldn't load payments. Try again.`, onRetry: () => { void payments.refetch(); } } : { status: "ready" }}
    isEmpty={!showClaims && payments.data?.count === 0}
    empty={{ message: status === "pending" ? t`Nothing to collect. Every charge here is paid or waived.` : t`No payments yet. Charges appear here when someone books, registers or borrows.` }}
    filtered={Boolean(list.values.subject_type || dueState || list.values.area)} filteredEmpty={{ message: t`No matching payments. Try another filter.`, action: { label: t`Clear filters`, onClick: () => list.update({ subject_type: "", due_state: "", area: "" }) } }}
    tabs={tabs} activeTab={showClaims ? "claims" : status || "all"}
    filters={showClaims ? undefined : { toolbar: <div className="grid min-w-0 gap-3">
      {forRecording ? null : <AreaPaymentGroups makerspaceId={makerspaceId} pinned={area} active={areaFilter}
        onSelect={value => list.update({ area: value })} />}
      <PaymentsFilters list={list} makerspaceId={makerspaceId} eventOnly={areaMode}
        areas={area || forRecording ? undefined : ownedAreas(actorActions, finance)} />
    </div> }}
    bulkBar={{ count: selected.length, actions: bulkActions, onClear: () => setSelected([]) }}
    pagination={showClaims ? undefined : { page: list.page, count: payments.data?.count ?? 0, pageSize: 24, onChange: list.setPage }}
    body={showClaims ? { kind: "rows", rows: <AreaClaimsList makerspaceId={makerspaceId} area={areaFilter || undefined} /> }
      : { kind: "table", table: <DataTable listState={list} columns={columns} data={(payments.data?.results ?? []).filter(row => !linkedPayment || row.id === linkedPayment)}
      selectedIds={selected} onSelectionChange={ids => setSelected(ids.map(Number))} emptyTitle={t`No matching payments`} /> }}
    detail={<>
      {notice ? <p role="status" className="mb-3 text-sm text-ink">{notice}</p> : null}
      {reminder.error ? <p role="alert" className="mb-3 text-sm text-danger">{areaErrorText(reminder.error)}</p> : null}
      {amend.error && !amending ? <p role="alert" className="mb-3 text-sm text-danger">{amend.error.message}</p> : null}
      {conflict ? <div role="alert"><Callout size="inline" tone="warn" lead={t`Someone else updated this charge. Refreshed.`} body={conflict} /></div> : null}
      {mutation.error && !conflict && !settling ? <p role="alert" className="mb-3 text-sm text-danger">{areaErrorText(mutation.error)}</p> : null}
      <PaymentsPanelDialogs makerspaceId={makerspaceId} documentsOpen={finance && documentsOpen} onCloseDocuments={() => setDocumentsOpen(false)}
        settling={settling} settle={{ pending: mutation.isPending, error: mutation.error?.message, cancel: () => setSettling(null),
          confirm: settlement => settling && mutation.mutate({ action: "mark-offline", ids: settling.ids, bulk: settling.bulk, settlement }) }}
        amending={amending} amend={{ pending: amend.isPending, error: amend.error?.message, cancel: () => { setAmending(null); amend.reset(); },
          confirm: settlement => amending && amend.mutate({ id: amending.id, settlement }) }}
        refundRow={refundRow} onCloseRefund={() => setRefundRow(null)}
        payLinkRow={payLinkRow} onClosePayLink={() => setPayLinkRow(null)}
        createLink={areaMode && payLinkRow ? email => areaPaymentsApi.payLink(makerspaceId, payLinkRow.id, email) : undefined}
        correctingRefund={correctingRefund} onCloseCorrection={() => setCorrectingRefund(null)} />
    </>}
  /></div>;
}
