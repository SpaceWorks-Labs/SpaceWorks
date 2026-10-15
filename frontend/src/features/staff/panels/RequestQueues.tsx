import { StaffLoanRenew } from "../StaffLoanRenew";
import { featureEnabled } from "../../../lib/features";
import { useContext, useEffect, useState } from "react";
import { StaffListContext } from "../StaffListContext";
import { HandoverWizard } from "../handover/HandoverWizard";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ListLayout } from "../../../components/layouts";
import type { Action, CalloutProps } from "../../../components/ui";
import { requestTabHref, requestTabLabels, visibleRequestTabs, type RequestTab } from "./requestTabs";
import { useRequestQueues } from "./useRequestQueues";
import { staffRequest } from "../../../lib/api";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { useUrlListState } from "../../../lib/useUrlListState";
import { ListViewControls } from "../ListViewControls";
import { issueErrorMessage } from "../issueErrors";
import { type Makerspace } from "./shared";
import { RequestList } from "./QueuesList";
import { actionInvalidationScope, invalidateRequestQueues } from "./QueuesInvalidation";
import {
  AssignIssueModal,
  RejectRequestModal,
  ReturnDueModal,
  ReturnRequestModal,
  type AssignIssueValues,
  type RejectRequestValues,
  type ReturnDueValues,
  type ReturnRequestValues,
} from "./QueuesModals";
import { AcceptRequestModal } from "./QueuesAcceptModal";

export type RequestItem = {
  id: number;
  product_id: number;
  product_name: string;
  storage_location: string;
  tracking_mode: string;
  requires_asset_qr: boolean;
  requested_quantity: number;
  accepted_quantity: number;
  issued_quantity: number;
  returned_quantity: number;
  damaged_quantity: number;
  missing_quantity: number;
  needs_fix_quantity: number;
  issued_assets?: Array<{ asset_id: number; asset_tag: string; serial_number: string }>;
};
export type HardwareRequest = {
  id: number;
  has_kit_checklist?: boolean;
  status: string;
  requester_username: string;
  requester_display?: string;
  requester_contact_email?: string;
  requester_contact_phone?: string;
  rejection_reason?: string;
  issue_evidence_id?: number | null;
  return_evidence_ids?: number[];
  requested_for: string;
  return_due_at: string | null;
  return_reminder_sent_at: string | null;
  items: RequestItem[];
  // AdminRequestSerializer serializes the assigned container as the flat `assigned_box_label`.
  assigned_box_label?: string | null;
  assigned_box?: { code: string; label: string };
};

export function Queues({ makerspace, guestOnly, canViewAudit = false, recovery, callout }: { makerspace: Makerspace; guestOnly: boolean; canViewAudit?: boolean; recovery?: ReactNode; callout?: CalloutProps }) {
  const queryClient = useQueryClient();
  // Tab counts reuse the dashboard numbers the shell already caches; no extra request is made.
  const counts = queryClient.getQueryData<{ pending_requests?: number; awaiting_issue?: number }>(["dashboard", makerspace.id]);
  const authority = useContext(StaffListContext);
  const can = (action: string) => authority.isSuperadmin || authority.actions?.includes(action);
  const [guided, setGuided] = useState<{ row: HardwareRequest; mode: "issue" | "return" } | null>(null);
  const [acceptRow, setAcceptRow] = useState<HardwareRequest | null>(null);
  const [dueRow, setDueRow] = useState<HardwareRequest | null>(null);
  const [rejectRow, setRejectRow] = useState<HardwareRequest | null>(null);
  const [assignIssueRow, setAssignIssueRow] = useState<HardwareRequest | null>(null);
  const [returnRow, setReturnRow] = useState<HardwareRequest | null>(null);
  const [modalError, setModalError] = useState("");
  const [defaultLoanDays, setDefaultLoanDays] = useState(String(makerspace.default_loan_days ?? 7));
  const location = useLocation();
  const list = useUrlListState({ request: "", requestView: "overview", queue: "", id: "", search: "", ordering: "-created_at", pendingPage: "1", acceptedPage: "1", activePage: "1", historyPage: "1", history: "false" });
  const visible = visibleRequestTabs(guestOnly, authority.actions, authority.isSuperadmin);
  const search = list.values.search;
  const debouncedSearch = useDebouncedValue(search);
  const queues = useRequestQueues(makerspace.id, list.values, visible, debouncedSearch, list.setPage);
  const { tab, selected } = queues;
  const openGuided = (row: HardwareRequest, mode: "issue" | "return") => {
    // Close the detail before opening its task dialog, so focus stays in one overlay.
    list.update({ request: "", id: "", queue: tab ?? "", history: "false", requestView: "overview" }, false);
    setGuided({ row, mode });
  };

  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: object }) => staffRequest(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
    onSuccess: (_data, { path }) => invalidateRequestQueues(queryClient, makerspace.id, actionInvalidationScope(path)),
  });
  useEffect(() => {
    setDefaultLoanDays(String(makerspace.default_loan_days ?? 7));
  }, [makerspace.default_loan_days, makerspace.id]);

  const openModal = (setter: (row: HardwareRequest | null) => void, row: HardwareRequest) => {
    list.update({ request: "", id: "", queue: tab ?? "", history: "false", requestView: "overview" }, false);
    setModalError("");
    setter(row);
  };
  const closeModals = () => {
    if (action.isPending) return;
    setAcceptRow(null);
    setDueRow(null);
    setRejectRow(null);
    setAssignIssueRow(null);
    setReturnRow(null);
    setModalError("");
  };
  const runAction = async (path: string, body?: object, onDone = closeModals) => {
    setModalError("");
    try {
      await action.mutateAsync({ path, body });
      onDone();
    } catch (error) {
      setModalError(error instanceof Error ? error.message : "Action failed.");
    }
  };
  const submitReturnDue = (values: ReturnDueValues) => {
    if (dueRow) void runAction(`/admin/requests/${dueRow.id}/return-due`, { return_due_at: values.returnDueAt ? new Date(values.returnDueAt).toISOString() : null });
  };
  const submitAccept = (acceptedQuantities: { item_id: number; quantity: number }[]) => {
    if (acceptRow) void runAction(`/admin/requests/${acceptRow.id}/accept`, { accepted_quantities: acceptedQuantities });
  };
  const submitReject = (values: RejectRequestValues) => {
    if (rejectRow) void runAction(`/admin/requests/${rejectRow.id}/reject`, { reason: values.reason });
  };
  const submitReturn = (values: ReturnRequestValues) => {
    if (returnRow) void runAction(`/admin/requests/${returnRow.id}/return`, { evidence_id: values.evidenceId, box_code: values.boxCode, remark: values.remark, resolutions: values.resolutions, kit_checklist: values.kitChecklist ?? [] });
  };
  const submitAssignIssue = async (values: AssignIssueValues) => {
    if (!assignIssueRow) return;
    setModalError("");
    let boxAssigned = false;
    try {
      await action.mutateAsync({ path: `/admin/requests/${assignIssueRow.id}/assign-box`, body: { box_code: values.boxCode } });
      boxAssigned = true;
      await action.mutateAsync({
        path: `/admin/requests/${assignIssueRow.id}/issue`,
        body: { evidence_id: values.evidenceId, remark: values.remark, rejects: values.rejects, asset_qr_payloads: values.assetQrPayloads, kit_checklist: values.kitChecklist ?? [] },
      });
      closeModals();
    } catch (error) {
      const message = issueErrorMessage(error);
      setModalError(boxAssigned ? `Box assigned, but issue failed: ${message} The request still needs the issue step; retry with the assigned box.` : message);
    }
  };

  const primary = (row: HardwareRequest): Action | undefined => {
    if (tab === "pending") return { label: "Accept", onClick: () => openModal(setAcceptRow, row), disabled: action.isPending };
    if (tab === "accepted") return can("issue_request") && can("assign_box") && can("upload_evidence")
      ? { label: "Start handover", onClick: () => openGuided(row, "issue") }
      : { label: "Assign + issue", onClick: () => openModal(setAssignIssueRow, row) };
    if (tab === "active") return can("return_request") && can("upload_evidence")
      ? { label: "Record return", onClick: () => openGuided(row, "return") }
      : { label: "Return", onClick: () => openModal(setReturnRow, row) };
  };
  const menu = (row: HardwareRequest): Action[] => tab === "history" ? [] : [
    { label: "Set due", onClick: () => openModal(setDueRow, row), disabled: action.isPending },
    ...(tab === "accepted" ? [{ label: "Assign + issue (quick form)", onClick: () => openModal(setAssignIssueRow, row), disabled: action.isPending }] : []),
    ...(tab === "active" ? [{ label: "Partial return (quick form)", onClick: () => openModal(setReturnRow, row), disabled: action.isPending }] : []),
  ];
  const messages: Record<RequestTab, string> = {
    pending: "No requests waiting for review. Check Ready for handover for the next step.",
    accepted: "Nothing to hand over. Accepted requests land here.",
    active: "Nothing is out on loan. Check Ready for handover to issue a request.",
    history: "Returned and closed requests will appear here. Check the other queues for work in progress.",
  };
  const retry = () => { if (queues.probeError) queues.retry(); else void selected.refetch(); };
  const state = queues.finding || selected.isLoading ? { status: "loading" as const }
    : queues.probeError || selected.isError ? { status: "error" as const,
      error: queues.probeError ? `Couldn't open request #${list.values.id || list.values.request}. Try again.` : "Couldn't load requests. Try again.", onRetry: retry }
    : { status: "ready" as const };
  return <div onClickCapture={event => {
    const anchor = (event.target as HTMLElement).closest('nav[aria-label="Page sections"] a');
    if (!anchor || anchor.closest('[role="dialog"]') || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const next = new URL((anchor as HTMLAnchorElement).href).searchParams.get("queue");
    if (next && visible.includes(next as RequestTab)) { event.preventDefault(); list.update({ queue: next, history: "false", request: "", requestView: "overview" }); }
  }}>
    <ListLayout header={{ title: "Requests", subtitle: "Borrow requests from members, from review to return.",
      meta: queues.finding ? <span role="status">Finding request #{list.values.id || list.values.request}…</span> : undefined,
      primary: tab === "accepted" && selected.count === 1 && selected.results[0] ? primary(selected.results[0]) : undefined }}
      callout={callout}
      tabs={visible.map(key => ({ key, label: requestTabLabels[key], href: requestTabHref(location.pathname, location.search, key),
        count: key === "pending" ? counts?.pending_requests : key === "accepted" ? counts?.awaiting_issue : undefined }))}
      activeTab={tab} state={state} isEmpty={!visible.length || queues.notFound || !selected.results.length}
      empty={{ message: !visible.length ? "You don't have access to request queues in this makerspace."
        : queues.notFound ? `We couldn't find request #${list.values.id || list.values.request} in your queues.` : messages[tab ?? "pending"] }}
      filtered={Boolean(search || list.values.id || list.values.request)}
      filteredEmpty={{ message: queues.notFound ? `We couldn't find request #${list.values.id || list.values.request} in your queues.` : "No requests match these filters. Clear filters to see your queue.",
        action: { label: "Clear filters", onClick: () => list.update({ search: "", id: "", request: "", requestView: "overview" }) } }}
      filters={{ toolbar: <ListViewControls searchControl={{ label: "Search requests", placeholder: "Search by name, email, phone or purpose", value: search, onChange: value => list.setFilter("search", value) }} state={list} makerspaceId={makerspace.id} entity="requests" search={false} sorts={[["-created_at", "Newest"], ["created_at", "Oldest"], ["return_due_at", "Due first"]]} /> }}
      body={{ kind: "rows", rows: <div role="region" aria-label={requestTabLabels[tab ?? "pending"]}>
        <RequestList rows={selected.results} canViewAudit={canViewAudit} primary={primary} menu={menu}
          reject={tab === "pending" ? row => ({ label: "Reject", tone: "danger", onClick: () => openModal(setRejectRow, row) }) : undefined}
          extra={tab === "active" && makerspace.enabled_features?.includes("loans.renewals") ? row => <StaffLoanRenew makerspaceId={makerspace.id} requestId={row.id} /> : undefined} />
      </div> }}
      pagination={visible.length && !queues.finding ? { page: selected.page, pageSize: selected.pageSize, count: selected.count, onChange: selected.setPage } : undefined}
      detail={<><div className="mt-8">{recovery}</div>
      <AcceptRequestModal row={acceptRow} open={Boolean(acceptRow)} pending={action.isPending} error={modalError} onClose={closeModals} onSubmit={submitAccept} />
      {guided ? <HandoverWizard key={`${makerspace.id}:${guided.row.id}:${guided.mode}`} row={guided.row} mode={guided.mode} makerspace={makerspace} canScanCards={Boolean(can("scan_member_cards"))} onClose={() => setGuided(null)} /> : null}
      <ReturnDueModal row={dueRow} defaultValue={dueRow?.return_due_at ? localDateTimeValue(dueRow.return_due_at) : localDateTimeValue(defaultDueDate(Number(defaultLoanDays) || 7).toISOString())} open={Boolean(dueRow)} pending={action.isPending} error={modalError} onClose={closeModals} onSubmit={submitReturnDue} />
      <RejectRequestModal row={rejectRow} open={Boolean(rejectRow)} pending={action.isPending} error={modalError} onClose={closeModals} onSubmit={submitReject} />
      <AssignIssueModal row={assignIssueRow} open={Boolean(assignIssueRow)} pending={action.isPending} error={modalError} onClose={closeModals} onSubmit={submitAssignIssue} makerspaceId={makerspace.id} kitEnabled={featureEnabled(makerspace.enabled_features ?? [], "loans.kit_checklist")} />
      <ReturnRequestModal row={returnRow} open={Boolean(returnRow)} pending={action.isPending} error={modalError} onClose={closeModals} onSubmit={submitReturn} makerspaceId={makerspace.id} />
      </>} />
  </div>;
}

function defaultDueDate(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date;
}
function localDateTimeValue(value: string) {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
