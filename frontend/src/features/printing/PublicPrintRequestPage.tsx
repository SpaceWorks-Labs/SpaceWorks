import { useParams } from "react-router-dom";
import { PublicDetailLayout, PublicLayout } from "../../components/layouts";
import { Callout, EmptyState } from "../../components/ui";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { tenantPublicRequest } from "../../lib/api";
import type { TypeIntake } from "../inventory/MachineIntakeForm";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { PrintDetailsForm, initialForm, optional, type FormState } from "./PublicPrintRequestForm";
import { fetchPrintQueues, fetchPublicConsumablePools, fetchPrintStatus, presignPrintUpload, submitPrintRequest, uploadToStorage } from "./publicApi";
import { PrintStatusPanel } from "./PublicPrintRequestPanels";
import { uploadPrintFilesBounded } from "./PublicPrintUploads";
import { statusRefetchInterval } from "../machine-service/types";

export function PublicPrintRequestPage() {
  const queryClient = useQueryClient();
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const [form, setForm] = useState<FormState>(initialForm);
  const [modelFiles, setModelFiles] = useState<File[]>([]);
  const [screenshotFiles, setScreenshotFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [activeStatusToken, setActiveStatusToken] = useState("");
  const [website, setWebsite] = useState("");
  const statusLinkHandledRef = useRef(false);
  const trackerRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (submitted) trackerRef.current?.scrollIntoView?.({ behavior: "smooth", block: "center" }); }, [submitted]);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const modules = useMemo(() => tenant.mode === "single" ? tenant.modules : new Set(bootstrap?.modules ?? []), [bootstrap?.modules, tenant]);
  const moduleEnabled = modules.has("machine_service");
  const queuesQuery = useQuery({ queryKey: ["public-printer-queues", makerspaceSlug], queryFn: () => fetchPrintQueues(makerspaceSlug), enabled: Boolean(makerspaceSlug) && moduleEnabled });
  const poolsQuery = useQuery({ queryKey: ["public-printer-consumable-pools", makerspaceSlug], queryFn: () => fetchPublicConsumablePools(makerspaceSlug), enabled: Boolean(makerspaceSlug) && moduleEnabled });
  const catalogueQuery = useQuery({ queryKey: ["print-materials", makerspaceSlug, queuesQuery.data?.[0]?.machine_type_id], queryFn: () => tenantPublicRequest<TypeIntake>(makerspaceSlug, `/public/${encodeURIComponent(makerspaceSlug)}/machine-types/${queuesQuery.data?.[0]?.machine_type_id}/intake`), enabled: Boolean(queuesQuery.data?.[0]?.machine_type_id) && Boolean(bootstrap?.features.includes("machines.material_catalogue")) });
  const printerAvailable = Boolean(queuesQuery.data?.length);
  const enabled = moduleEnabled && printerAvailable;
  const statusQuery = useQuery({ queryKey: ["public-printer-status", activeStatusToken], queryFn: () => fetchPrintStatus(activeStatusToken), enabled: Boolean(activeStatusToken), refetchInterval: (query) => statusRefetchInterval(query.state.data?.status) });
  const statusStorageKey = makerspaceSlug ? `tinkerspace.printStatus.${makerspaceSlug}` : "";
  useEffect(() => { if (statusLinkHandledRef.current) return; statusLinkHandledRef.current = true; const token = new URLSearchParams(window.location.search).get("token")?.trim(); const stored = statusStorageKey ? window.localStorage.getItem(statusStorageKey)?.trim() : ""; if (token || stored) setActiveStatusToken(token || stored || ""); }, [statusStorageKey]);
  useEffect(() => { if (statusStorageKey && activeStatusToken) window.localStorage.setItem(statusStorageKey, activeStatusToken); }, [activeStatusToken, statusStorageKey]);
  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) { setForm((current) => ({ ...current, [key]: value })); }
  const submitMutation = useMutation({ mutationFn: async () => {
    const files = [...modelFiles.map((file) => ({ file, kind: "stl" as const })), ...screenshotFiles.map((file) => ({ file, kind: "screenshot" as const }))];
    const fileIds = await uploadPrintFilesBounded(files, async (item) => { const presigned = await presignPrintUpload(makerspaceSlug, { kind: item.kind, filename: item.file.name, content_type: item.kind === "stl" ? item.file.type || "application/octet-stream" : item.file.type }); await uploadToStorage(presigned.upload, item.file); return presigned.file_id; }, setUploadProgress);
    const chosenPool = poolsQuery.data?.find((pool) => String(pool.id) === form.consumablePoolId);
    return submitPrintRequest(makerspaceSlug, { website, queue_id: queuesQuery.data?.[0]?.id ?? null, title: form.title.trim(), project_brief: optional(form.projectBrief), preferred_settings: optional(form.preferredSettings), material: chosenPool?.material || optional(form.material), color: chosenPool?.color || optional(form.color), consumable_pool_id: form.consumablePoolId ? Number(form.consumablePoolId) : null, estimated_filament_grams: form.estimatedFilamentGrams.trim() || null, quantity: form.quantity, source_link: optional(form.sourceLink), file_ids: fileIds });
  }, onSuccess: (response) => { queryClient.invalidateQueries({ queryKey: ["public-printer-consumable-pools", makerspaceSlug] }); setUploadProgress(""); setSubmitted(true); setActiveStatusToken(response.public_token); }, onError: () => setUploadProgress("") });
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const trackingUrl = new URL(window.location.href);
  if (activeStatusToken) trackingUrl.searchParams.set("token", activeStatusToken);
  const loading = bootstrapQuery.isLoading || (moduleEnabled && queuesQuery.isLoading);
  const failed = bootstrapQuery.isError || queuesQuery.isError;
  const state = loading ? { status: "loading" as const } : failed ? { status: "error" as const, error: "Couldn't reach the print service. Try again.", onRetry: () => { void bootstrapQuery.refetch(); void queuesQuery.refetch(); } } : { status: "ready" as const };
  return <div style={brandStyle}><PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)} state={state}>
    <PublicDetailLayout state={state} title={`Send a print job to ${displayName}`}
      chips={[{ label: "3D printing", tone: "accent" }]} sections={[{ id: "your-print", label: "Your print", content:
        submitted ? <Callout size="panel" tone="success" lead="Request sent." body="We'll update this page as it moves." action={{ label: "Send another request", onClick: () => setSubmitted(false) }} />
          : enabled ? <PrintDetailsForm catalogue={catalogueQuery.data} form={form} updateField={updateField} poolsQuery={poolsQuery}
            modelFiles={modelFiles} setModelFiles={setModelFiles} screenshotFiles={screenshotFiles} setScreenshotFiles={setScreenshotFiles}
            submitPending={submitMutation.isPending} submitError={submitMutation.error} uploadProgress={uploadProgress} website={website} onWebsiteChange={setWebsite}
            onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (form.title.trim()) submitMutation.mutate(); }} />
          : <EmptyState message="3D printing isn't open for requests right now." action={{ label: "Back to catalogue", href: tenantPath() }} /> } ]}
      actionCard={{ title: "Track your job", state: "open", summary: !activeStatusToken ? "After you send it, you'll get a private link to follow progress here." : undefined,
        form: <div ref={trackerRef} id="print-tracker"><PrintStatusPanel submitted={submitted} tokenStatus={statusQuery.data} tokenStatusPending={Boolean(activeStatusToken) && statusQuery.isPending} tokenStatusError={statusQuery.error} trackingHref={activeStatusToken ? trackingUrl.href : undefined} onRetry={() => { void statusQuery.refetch(); }} publicToken={activeStatusToken || undefined} makerspaceSlug={makerspaceSlug} /></div>,
        mobileBar: { summary: submitted ? "Request sent" : "Follow your print", label: "Track your job" } }} />
  </PublicLayout></div>;
}
