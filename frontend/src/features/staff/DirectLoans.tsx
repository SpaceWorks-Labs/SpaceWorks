import { KitChecklistCapture, useKitChecklist } from "../inventory/KitChecklist";
import { featureEnabled } from "../../lib/features";
import { DirectHandoverWizard } from "./handover/DirectHandoverWizard";
import { useQuickCreate } from "./quickCreate";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import QrScanner from "../../components/ui/QrScanner";
import { ListLayout } from "../../components/layouts";
import { useSearchParams } from "react-router-dom";
import { staffRequest } from "../../lib/api";
import { usePaginatedQuery } from "../../lib/usePaginatedQuery";
import { DirectLoanList, type DirectLoan } from "./DirectLoanList";
import { invalidateInventoryViews } from "./queryInvalidation";
import { DirectLoanReturnModal } from "./DirectLoanReturnModal";
import { type Makerspace, useStaffGet } from "./StaffPanels";
import { MemberClaimCodes } from "./MemberClaimCodes";
import { DirectLoanCompactWork } from "./DirectLoanCompactWork";
import { useDirectLoanReturn } from "./useDirectLoanReturn";
import {
  labelForTarget,
  type ContainerResponse,
  type DirectLoanMemberResponse,
  type LineDraft,
  type ProductOption,
  type QrResolveResponse,
  type ScannedPayload,
} from "./DirectLoansTypes";

export function DirectLoans({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const [guided, setGuided] = useState(false);
  const [params] = useSearchParams();
  const rawTab = params.get("handout");
  const tab = rawTab === "returned" || rawTab === "claim-codes" ? rawTab : "on-loan";
  const status = tab === "returned" ? "returned" : "checked_out";
  useQuickCreate("request", () => setGuided(true));
  const [borrowerId, setBorrowerId] = useState("");
  const [lineRows, setLineRows] = useState<LineDraft[]>([{ key: 1, productId: "", quantity: "1" }]);
  const [nextLineKey, setNextLineKey] = useState(2);
  const [scanned, setScanned] = useState<ScannedPayload[]>([]);
  const [showScanner, setShowScanner] = useState(false);
  const [qrPayloads, setQrPayloads] = useState("");
  const [containerId, setContainerId] = useState("");
  const [showContainerScanner, setShowContainerScanner] = useState(false);
  const [containerScanError, setContainerScanError] = useState("");
  const [issueEvidenceId, setIssueEvidenceId] = useState<number | null>(null);
  const [issueRemark, setIssueRemark] = useState("Issued from direct handout.");
  const [issueUploadKey, setIssueUploadKey] = useState(0);
  useEffect(() => {
    setBorrowerId("");
    setLineRows([{ key: 1, productId: "", quantity: "1" }]);
    setNextLineKey(2);
    setScanned([]);
    setShowScanner(false);
    setQrPayloads("");
    setContainerId("");
    setShowContainerScanner(false);
    setContainerScanError("");
    setIssueEvidenceId(null);
    setIssueRemark("Issued from direct handout.");
    setIssueUploadKey((key) => key + 1);
  }, [makerspace.id]);
  const returnFlow = useDirectLoanReturn(makerspace);
  const products = useStaffGet<{ results: ProductOption[] }>(
    ["inventory-all", makerspace.id],
    `/admin/makerspace/${makerspace.id}/inventory?page_size=1000`,
  );
  // Fetch ALL containers (distinct cache key from the shared ["containers"] entry so a
  // truncated first page can't leak in): the dropdown + the scan membership check both
  // need the complete list, else a valid container past page one falsely reads as "not found".
  const containers = useStaffGet<ContainerResponse>(
    ["containers-all", makerspace.id],
    `/admin/makerspace/${makerspace.id}/containers?page_size=1000`,
  );
  // The endpoint is a DRF ListAPIView, so it answers with the paginated envelope, not a
  // bare array — the same unwrap `containerOptions` below already does. Typing it as an
  // array made `.map` a runtime TypeError that took the whole panel down with it.
  const members = useStaffGet<DirectLoanMemberResponse>(
    ["direct-loan-members", makerspace.id],
    `/admin/makerspace/${makerspace.id}/direct-loan-members?page_size=1000`,
  );
  const memberOptions = Array.isArray(members.data)
    ? members.data
    : members.data?.results ?? [];
  const containerOptions = Array.isArray(containers.data)
    ? containers.data
    : containers.data?.results ?? [];
  const activeProducts = (products.data?.results ?? []).filter((product) => !product.is_archived);
  const productById = new Map(activeProducts.map((product) => [product.id, product]));
  const loans = usePaginatedQuery<DirectLoan>({
    key: ["direct-loans", makerspace.id, status],
    path: `/admin/makerspace/${makerspace.id}/direct-loans?status=${status}`,
    resetKey: `${makerspace.id}:${status}`,
    enabled: tab !== "claim-codes",
  });
  const pastedQrPayloads = qrPayloads.split("\n").map((value) => value.trim()).filter(Boolean);
  const validManualLines = lineRows.filter((line) => {
    const product = productById.get(Number(line.productId));
    return Boolean(product) && product?.tracking_mode !== "individual" && Number(line.quantity) > 0;
  });
  const kits = useKitChecklist(`/admin/makerspace/${makerspace.id}/kit-checklist-preview`,
    { phase: "issue", qr_payloads: Array.from(new Set([...scanned.map((item) => item.payload), ...pastedQrPayloads])),
      items: validManualLines.map((line) => ({ product_id: Number(line.productId), quantity: Number(line.quantity) })),
      container_id: containerId ? Number(containerId) : null },
    featureEnabled(makerspace.enabled_features ?? [], "loans.kit_checklist") && Boolean(containerId || scanned.length || pastedQrPayloads.length || validManualLines.length));
  const issue = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/direct-loans`, {
        method: "POST",
        body: JSON.stringify({
          kit_checklist: kits.counts,
          borrower_id: Number(borrowerId),
          evidence_id: issueEvidenceId as number,
          remark: issueRemark.trim(),
          container_id: containerId ? Number(containerId) : null,
          qr_payloads: Array.from(new Set([
            ...scanned.map((item) => item.payload),
            ...pastedQrPayloads,
          ])),
          items: validManualLines
            .map((line) => ({ product_id: Number(line.productId), quantity: Number(line.quantity) })),
        }),
      }),
    onSuccess: () => {
      setGuided(false);
      queryClient.invalidateQueries({ queryKey: ["direct-loans", makerspace.id] });
      invalidateInventoryViews(queryClient, makerspace.id, makerspace.slug);
      setLineRows([{ key: 1, productId: "", quantity: "1" }]);
      setNextLineKey(2);
      setScanned([]);
      setQrPayloads("");
      setContainerId("");
      setShowContainerScanner(false);
      setContainerScanError("");
      setIssueEvidenceId(null);
      setIssueRemark("Issued from direct handout.");
      setIssueUploadKey((key) => key + 1);
    },
  });
  const hasIssueContent =
    validManualLines.length > 0 || scanned.length > 0 || pastedQrPayloads.length > 0 || Boolean(containerId);
  const canIssue =
    Boolean(borrowerId) &&
    hasIssueContent &&
    issueEvidenceId !== null &&
    !issue.isPending && kits.ready;
  const addLine = () => {
    setLineRows((rows) => [...rows, { key: nextLineKey, productId: "", quantity: "1" }]);
    setNextLineKey((key) => key + 1);
  };
  const updateLine = (key: number, patch: Partial<LineDraft>) => {
    setLineRows((rows) => rows.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  };
  const removeLine = (key: number) => {
    setLineRows((rows) => rows.filter((line) => line.key !== key));
  };
  const removeScanned = (payload: string) => {
    setScanned((items) => items.filter((item) => item.payload !== payload));
  };
  const handleScan = async (payload: string) => {
    const cleanPayload = payload.trim();
    if (!cleanPayload || scanned.some((item) => item.payload === cleanPayload)) return;
    let label = cleanPayload;
    try {
      const result = await staffRequest<QrResolveResponse>("/admin/qr/resolve", {
        method: "POST",
        body: JSON.stringify({ payload: cleanPayload }),
      });
      label = labelForTarget(result.target, cleanPayload);
    } catch {
      label = cleanPayload;
    }
    setScanned((items) =>
      items.some((item) => item.payload === cleanPayload)
        ? items
        : [...items, { payload: cleanPayload, label }],
    );
  };
  const handleContainerScan = async (payload: string) => {
    try {
      const result = await staffRequest<QrResolveResponse>("/admin/qr/resolve", {
        method: "POST",
        body: JSON.stringify({ payload }),
      });
      const target = result.target;
      if (target.type !== "box") {
        setContainerScanError("Scanned QR is not a container.");
        return;
      }
      if (!containerOptions.some((container) => container.id === target.id)) {
        setContainerScanError("That container isn't available for handout (inactive or not found).");
        return;
      }
      setContainerId(String(target.id));
      setContainerScanError("");
    } catch {
      setContainerScanError("Could not resolve the scanned QR.");
    } finally {
      setShowContainerScanner(false);
    }
  };

  const compactWork = <DirectLoanCompactWork
    borrower={{ makerspaceId: makerspace.id, borrowerId, onBorrowerIdChange: setBorrowerId, memberOptions, membersLoading: members.isLoading, membersError: members.error?.message }}
    container={{ containerId, onContainerIdChange: setContainerId, containerOptions, containersLoading: containers.isLoading, scanError: containerScanError, onScanClick: () => { setContainerScanError(""); setShowContainerScanner(true); } }}
    items={{ lineRows, activeProducts, productById, productsLoading: products.isLoading, onAdd: addLine, onUpdate: updateLine, onRemove: removeLine }}
    qr={{ scanned, qrPayloads, onOpenScanner: () => setShowScanner(true), onRemoveScanned: removeScanned, onQrPayloadsChange: setQrPayloads }}
    evidence={{ uploadKey: issueUploadKey, makerspaceId: makerspace.id, disabled: issue.isPending, onUploaded: setIssueEvidenceId, remark: issueRemark, onRemarkChange: setIssueRemark }}>
        <KitChecklistCapture checklist={kits} />
        {issueEvidenceId === null ? <p className="mt-3 text-sm text-muted">Upload an issue photo before issuing.</p> : null}
        {!hasIssueContent ? <p className="mt-3 text-sm text-muted">Add at least one item, QR payload, or container before issuing.</p> : null}
        {issue.error ? <p className="mt-3 text-sm text-danger">{issue.error.message}</p> : null}
        {products.error ? <p className="mt-3 text-sm text-danger">{products.error.message}</p> : null}
        {containers.error ? <p className="mt-3 text-sm text-danger">{containers.error.message}</p> : null}
        {showScanner ? <QrScanner onScan={handleScan} onClose={() => setShowScanner(false)} /> : null}
        {showContainerScanner ? <QrScanner onScan={handleContainerScan} onClose={() => setShowContainerScanner(false)} /> : null}
  </DirectLoanCompactWork>;
  const shown = loans.results;
  const tabHref = (key: string) => { const next = new URLSearchParams(params); next.set("handout", key); return `?${next}`; };
  return <ListLayout standalone={false}
    header={{ title: "Direct handout", subtitle: "Lend tools straight from the shelf, without a request.", primary: { label: "New handout", icon: "Plus", onClick: () => setGuided(true) } }}
    state={tab === "claim-codes" ? { status: "ready" } : { status: loans.isLoading || loans.isPlaceholderData ? "loading" : loans.isError ? "error" : "ready", error: "Couldn't load direct handouts. Try again.", onRetry: () => void loans.refetch() }}
    tabs={[{ key: "on-loan", label: "On loan", count: tab === "on-loan" ? loans.count : undefined, href: tabHref("on-loan") }, { key: "returned", label: "Returned", count: tab === "returned" ? loans.count : undefined, href: tabHref("returned") }, { key: "claim-codes", label: "Claim codes", href: tabHref("claim-codes") }]} activeTab={tab}
    isEmpty={tab !== "claim-codes" && !shown.length}
    empty={{ message: tab === "returned" ? "No direct handouts returned yet." : "No tools are out on direct handout. Start one with New handout above.", action: tab === "returned" ? undefined : { label: "New handout", onClick: () => setGuided(true) } }}
    body={{ kind: "rows", rows: tab === "claim-codes" ? <MemberClaimCodes makerspaceId={makerspace.id} members={memberOptions} /> : <DirectLoanList loans={shown} onReturn={returnFlow.openReturnModal} /> }}
    pagination={tab === "claim-codes" ? undefined : { page: loans.page, pageSize: loans.pageSize, count: loans.count, onChange: loans.setPage }}
    detail={<>
      {guided ? <DirectHandoverWizard key={makerspace.id} makerspace={makerspace} onClose={() => setGuided(false)} compactWork={compactWork} compactAction={{ label: "Issue direct handout", disabled: !canIssue, pending: issue.isPending, onClick: () => issue.mutate() }} /> : null}
      <DirectLoanReturnModal
        loan={returnFlow.returningLoan} makerspaceId={makerspace.id}
        evidenceId={returnFlow.returnEvidenceId} notes={returnFlow.returnNotes} qrPayload={returnFlow.returnQrPayload}
        pending={returnFlow.pending} error={returnFlow.error} onEvidenceUploaded={returnFlow.setReturnEvidenceId}
        onNotesChange={returnFlow.setReturnNotes} onQrPayloadChange={returnFlow.setReturnQrPayload}
        onCancel={returnFlow.closeReturnModal} onSubmit={returnFlow.submitReturn}
      />
    </>}
  />;
}
