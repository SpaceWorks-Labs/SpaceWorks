import { t } from "@lingui/core/macro";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { FlowLayout, type FlowStep } from "../../components/layouts";
import type { Action, CalloutProps } from "../../components/ui";
import { SiteFooter } from "../../components/SiteFooter";
import { StructuredApiError } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { chargesOn } from "../../lib/charges";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { PricePreview } from "../payments/PricePreview";
import { jobErrorMessage } from "./api";
import { JobConfirmStep } from "./JobConfirmStep";
import { JobDetailsStep } from "./JobDetailsStep";
import { JobFilesStep, filesReady } from "./JobFilesStep";
import { detailsProblem } from "./jobDraft";
import { JobUploadError } from "./jobUploads";
import { JobTypeStep, extensionList } from "./JobTypeStep";
import { JOB_STEPS, useJobRequest, type JobStep } from "./useJobRequest";
import { useMemberIdentity } from "./useMemberIdentity";

const STEP_LABELS: Record<JobStep, string> = { type: t`Machine type`, files: t`Files`, details: t`Details`, confirm: t`Confirm and send` };

/** Where to send a member a refusal names; the member area holds check-in, the waiver and joining. */
function refusalAction(error: unknown, memberPath: string): Action | undefined {
  if (!(error instanceof StructuredApiError)) return undefined;
  if (error.code === "presence_required") return { label: t`Check in`, href: memberPath };
  if (error.code === "waiver_acceptance_required") return { label: t`Read the waiver`, href: `${memberPath}#current-waiver` };
  if (error.code === "membership_required") return { label: t`Membership options`, href: memberPath };
  return undefined;
}

/** "Request a job": one flow for every machine type that takes jobs (#140). Members only. */
export function JobRequestPage() {
  const { slug } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const showPrice = chargesOn(bootstrap, "machines"); // #184: no quote, prepay or price copy when machines are free
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const member = useMemberIdentity();
  const flow = useJobRequest(makerspaceSlug, bootstrap?.features ?? [], search, id => navigate(tenantPath(`member/machine-jobs/${id}`)));
  const { types, type, step, draft, submit } = flow;

  if (member.signedOut) return <div style={brandStyle}><MemberAuthPanel makerspaceSlug={makerspaceSlug}
    eyebrow={t`Request a job`} tenantBrand={bootstrap ? { name: displayName, logo: bootstrap.branding.logo_url || bootstrap.makerspace.logo_url || undefined } : undefined}
    onAuthenticated={() => { void member.identity.refetch(); }} /></div>;

  const accepted = type ? extensionList(type) : [];
  const problem = detailsProblem(draft, type, flow.intake.data);
  const acked = draft.acks.pickup && draft.acks.failure && draft.acks.content;
  const index = JOB_STEPS.indexOf(step);
  const busy = submit.isPending;
  const closed = types.error instanceof StructuredApiError && types.error.status === 404;
  const state = bootstrapQuery.isLoading || member.loading || types.isPending ? { status: "loading" as const }
    : types.isError && !closed ? { status: "error" as const, error: t`Couldn't load the machines taking jobs. Try again.`, onRetry: () => { void types.refetch(); } }
      : { status: "ready" as const };
  const steps: FlowStep[] = JOB_STEPS.map((key, position) => ({ key, label: STEP_LABELS[key], required: true,
    state: position < index ? "done" : position === index ? "current" : "todo",
    summary: key === "type" ? type?.name : key === "files" && flow.models.length ? t`${flow.models.length} design file${flow.models.length === 1 ? "" : "s"}`
      : key === "details" && position < index ? draft.title.trim() : undefined }));
  const go = (next: JobStep) => { if (!busy) flow.setStep(next); };
  const nextAction: Action = step === "type" ? { label: t`Next: files`, disabled: !type, disabledReason: "Choose a machine type.", onClick: () => go("files") }
    : step === "files" ? { label: t`Next: details`, disabled: !filesReady(flow.models, accepted), disabledReason: "Add at least one design file this machine accepts.", onClick: () => go("details") }
      : step === "details" ? { label: t`Next: confirm`, disabled: Boolean(problem), disabledReason: problem || undefined, onClick: () => go("confirm") }
        : { label: t`Send request`, pending: busy, pendingLabel: flow.progress || "Sending…", disabled: !acked,
          disabledReason: "Tick all three to send your request.", onClick: () => submit.mutate() };
  const error: CalloutProps | undefined = submit.isError && !(submit.error instanceof JobUploadError) ? { size: "panel", tone: "danger",
    lead: "Couldn't send your request.", body: jobErrorMessage(submit.error), action: refusalAction(submit.error, tenantPath("member")) } : undefined;

  const work = !type || step === "type" ? <JobTypeStep types={types.data ?? []} value={type?.queue_id ?? null} onChange={flow.chooseType} showPrice={showPrice} />
    : step === "files" ? <div className="grid gap-4">
      {submit.error instanceof JobUploadError ? <p className="text-sm text-danger" role="alert">{submit.error.message}</p> : null}
      <JobFilesStep accepted={accepted} typeName={type.name} models={flow.models} screenshots={flow.screenshots} errors={flow.fileErrors} onChange={flow.changeFiles} disabled={busy} /></div>
      : step === "details" ? <JobDetailsStep draft={draft} update={flow.update} type={type} intake={flow.intake.data} pools={flow.pools.data}
        poolsError={flow.pools.error} disabled={busy} />
        : <div className="grid gap-5">
          <JobConfirmStep type={type} draft={draft} fileCount={flow.models.length} screenshotCount={flow.screenshots.length} disabled={busy} showPrice={showPrice}
            onAck={(key, value) => flow.update({ acks: { ...draft.acks, [key]: value } })} />
          <PricePreview makerspaceSlug={makerspaceSlug} request={{ domain: "machines", machine_type_id: type.machine_type_id,
            pool_id: draft.poolId ? Number(draft.poolId) : undefined, quantity: Number(draft.grams) > 0 ? draft.grams.trim() : undefined }} />
          {flow.progress ? <p className="text-sm text-muted" role="status">{flow.progress}</p> : null}
        </div>;

  return <div style={brandStyle}>
    <FlowLayout title={t`Request a job`} subject={displayName} state={state} current={step} steps={steps}
      isEmpty={closed || (types.isSuccess && !types.data.length)}
      empty={{ message: t`${displayName} isn't taking job requests right now.`, action: { label: t`See the machines`, href: tenantPath("machines") } }}
      onStepSelect={key => go(key as JobStep)} onCancel={() => navigate(tenantPath("machines"))}
      leaveGuard={flow.models.length || draft.title.trim() ? "Your files and details will be lost." : undefined}
      footer={{ back: index > 0 ? { label: t`Back`, disabled: busy, disabledReason: "Wait until your request is sent.", onClick: () => go(JOB_STEPS[index - 1]) } : undefined, next: nextAction }}
      error={error} pending={busy} work={work} />
    <SiteFooter branding={bootstrap?.branding} />
  </div>;
}
