import { SiteFooter } from "../../components/SiteFooter";
import { MakerspaceBrand } from "../../components/MakerspaceBrand";
import { FlowLayout } from "../../components/layouts";
import { KitChecklistCapture, useKitChecklist, type KitPreview } from "./KitChecklist";
import { tenantPublicRequest } from "../../lib/api";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { SegmentedControl } from "../../components/ui";
import QrScanner from "../../components/ui/QrScanner";
import { featureEnabled } from "../../lib/features";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "./PublicInventoryParts";
import { PublicEvidenceUpload } from "./PublicEvidenceUpload";
import { checkoutTool, returnTool } from "./selfCheckoutApi";
import { ResultCard } from "./PublicToolResultCard";
import { invalidatePublicInventory } from "../staff/queryInvalidation";
import { useTenantBootstrap } from "./usePublicInventory";

type Mode = "checkout" | "return";

type MutationInput = {
  payload: string;
};

export function PublicSelfCheckoutPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const [mode, setMode] = useState<Mode>("checkout");
  const [issueEvidenceId, setIssueEvidenceId] = useState<number | null>(null);
  const [returnEvidenceId, setReturnEvidenceId] = useState<number | null>(null);
  const [returnRemark, setReturnRemark] = useState("");
  const [uploadKey, setUploadKey] = useState(0);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannedPayload, setScannedPayload] = useState("");
  const kits = useKitChecklist(`/public/${makerspaceSlug}/tools/checklist`,
    { payload: scannedPayload, phase: mode === "checkout" ? "issue" : "return" }, Boolean(scannedPayload),
    (path, body) => tenantPublicRequest<KitPreview>(makerspaceSlug, path, { method: "POST", body: JSON.stringify(body) }));

  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const features = tenant.mode === "single" ? tenant.bootstrap?.features ?? [] : bootstrap?.features ?? [];
  const displayName =
    bootstrap?.branding.display_name ||
    bootstrap?.makerspace.name ||
    formatSlug(makerspaceSlug) ||
    "Makerspace";
  const enabled = featureEnabled(features, "inventory.self_checkout");

  const loanMutation = useMutation({
    mutationFn: ({ payload }: MutationInput) =>
      mode === "checkout"
        ? checkoutTool(makerspaceSlug, {
            payload,
            evidence_id: issueEvidenceId as number,
            kit_checklist: kits.counts,
          })
        : returnTool(makerspaceSlug, {
            payload,
            evidence_id: returnEvidenceId as number,
            remark: returnRemark.trim(),
            kit_checklist: kits.counts,
          }),
    onSuccess: () => {
      setScannedPayload("");
      invalidatePublicInventory(queryClient, makerspaceSlug);
      if (mode === "checkout") {
        setIssueEvidenceId(null);
      } else {
        setReturnEvidenceId(null);
        setReturnRemark("");
      }
      setUploadKey((key) => key + 1);
    },
  });
  const canScan =
    mode === "checkout"
      ? issueEvidenceId !== null
      : returnEvidenceId !== null &&
        returnRemark.trim().length > 0;

  function scanTool(payload: string) {
    if (!canScan) {
      return;
    }
    setScannerOpen(false);
    setScannedPayload(payload);
  }

  useEffect(() => {
    if (scannedPayload && kits.ready && !kits.components.length) {
      const payload = scannedPayload;
      setScannedPayload("");
      loanMutation.mutate({ payload });
    }
  }, [scannedPayload, kits.ready, kits.components.length]);

  const phase = !canScan ? "photo" : scannedPayload && kits.components.length ? "kit" : "scan";
  const state = bootstrapQuery.isLoading ? { status: "loading" as const } : bootstrapQuery.isError
    ? { status: "error" as const, error: "Couldn't load checkout access. Try again.", onRetry: () => { void bootstrapQuery.refetch(); } } : { status: "ready" as const };
  return <div style={brandStyle}>
    <FlowLayout title="Borrow or return a tool" subject={displayName} state={state} compact
      isEmpty={!enabled} empty={{ message: `Self-checkout isn't on at ${displayName}.`, action: { label: "Back to catalogue", href: tenantPath() } }}
      current={phase} steps={[
        { key: "photo", label: mode === "return" ? "Photo and condition notes" : "Photo", state: phase === "photo" ? "current" : "done", required: true },
        { key: "scan", label: "Scan the tool", state: phase === "scan" ? "current" : phase === "kit" ? "done" : "todo", required: true },
        ...(kits.components.length ? [{ key: "kit", label: "Check the kit", state: phase === "kit" ? "current" as const : "todo" as const, required: true }] : []),
      ]}
      onCancel={() => navigate(tenantPath())}
      footer={{ next: { label: scannedPayload && kits.components.length ? `Confirm ${mode === "checkout" ? "checkout" : "return"}` : "Scan QR",
        pending: loanMutation.isPending, disabled: !canScan || (Boolean(scannedPayload) && !kits.ready),
        disabledReason: mode === "return" ? "Upload a return photo and add condition notes before scanning." : "Upload a photo of the tool before scanning.",
        onClick: () => scannedPayload && kits.components.length ? loanMutation.mutate({ payload: scannedPayload }) : setScannerOpen(true) } }}
      error={loanMutation.isError ? { size: "panel", tone: "danger", lead: "Couldn't complete this handover.", body: loanMutation.error.message } : undefined}
      result={loanMutation.isSuccess ? { tone: "success", title: mode === "checkout" ? "You've got it." : "Returned. Thanks!", summary: <ResultCard result={loanMutation.data} />,
        next: { label: mode === "checkout" ? "Borrow another" : "Return another", onClick: () => loanMutation.reset() } } : undefined}
      work={<div className="grid gap-5"><MakerspaceBrand name={displayName} logoUrl={bootstrap?.makerspace.logo_url} />
        <SegmentedControl label="Checkout mode" value={mode} options={[{ value: "checkout", label: "Borrow" }, { value: "return", label: "Return" }]} onChange={value => { setMode(value as Mode); setScannedPayload(""); }} />
        <p className="text-sm text-muted">{mode === "checkout" ? "Take a photo of the tool, then scan its QR label." : "Take a return photo and describe its condition, then scan its QR label."}</p>
        {mode === "checkout" ? <PublicEvidenceUpload key={`issue-${uploadKey}`} slug={makerspaceSlug} evidenceType="issue" disabled={loanMutation.isPending} onUploaded={setIssueEvidenceId} />
          : <><PublicEvidenceUpload key={`return-${uploadKey}`} slug={makerspaceSlug} evidenceType="return" disabled={loanMutation.isPending} onUploaded={setReturnEvidenceId} />
            <label className="grid gap-2 text-sm font-semibold">Return condition notes<textarea className="desk-input min-h-24 w-full" required value={returnRemark} onChange={event => setReturnRemark(event.target.value)} /></label></>}
        <KitChecklistCapture checklist={kits} />
      </div>} />
    {scannerOpen ? <QrScanner onClose={() => setScannerOpen(false)} onScan={scanTool} /> : null}
    <SiteFooter branding={bootstrap?.branding} />
  </div>;
}
