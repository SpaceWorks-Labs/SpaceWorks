import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PublicDetailLayout, PublicLayout } from "../../components/layouts";
import { EmptyState, RelativeTime, StatusPill } from "../../components/ui";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { fetchServiceStatus, serviceKeys } from "./api";
import { OwnerCancel, OwnerJobLink } from "./OwnerCancel";
import { ServiceRequestEta } from "./ServiceRequestEta";
import { normalizeServiceStatus, serviceStatusLabel, serviceStatusTone, statusRefetchInterval } from "./types";

/** Accurate copy for a job that no longer has an estimate. */
function terminalMessage(status: string): string {
  if (status === "cancelled") return t`This job was cancelled. Nothing was charged for it.`;
  if (status === "completed") return t`Your job finished and is ready to collect.`;
  if (status === "collected") return t`This job is finished and has been collected.`;
  if (status === "rejected") return t`This request wasn't approved, so it won't be run. Contact the makerspace if you have questions.`;
  if (status === "failed") return t`This job couldn't be completed. Contact the makerspace about next steps.`;
  if (status === "changes_requested") return t`Staff need changes from you before this job can go ahead. Open it in your member area to reply.`;
  if (status === "quoted") return t`There is a quote waiting for you. Open the job in your member area to approve or decline it.`;
  if (status === "uncollected") return t`This job wasn't collected within 14 days, so it now belongs to the space.`;
  return t`There is no estimate for this job right now.`;
}

export function PublicMachineServiceStatusPage() {
  const { slug, publicToken = "" } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const statusQuery = useQuery({
    queryKey: serviceKeys.status(publicToken), queryFn: () => fetchServiceStatus(publicToken),
    enabled: Boolean(publicToken), refetchInterval: query => statusRefetchInterval(query.state.data?.status),
  });
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const job = statusQuery.data;
  const state = bootstrapQuery.isLoading || statusQuery.isPending
    ? { status: "loading" as const }
    : statusQuery.isError
      ? { status: "error" as const, error: t`We couldn't find that job, or it isn't trackable any more.`, onRetry: () => { void statusQuery.refetch(); } }
      : { status: "ready" as const };
  const status = job ? normalizeServiceStatus(job.status) : "";
  return <div style={brandStyle}><PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)} state={state}>
    <PublicDetailLayout state={state} title={job ? job.title : t`Machine job`}
      chips={job ? [{ label: job.machine_type_name, tone: "accent" }, { label: serviceStatusLabel(status), tone: serviceStatusTone(status) }] : []}
      sections={[{ id: "job-status", label: t`Status`, content: job ? <div className="grid gap-4">
        <p className="text-sm text-muted">{t`Requested `}<RelativeTime date={job.created_at} /></p>
        {job.eta ? <ServiceRequestEta eta={job.eta} status={job.status} /> : <EmptyState message={terminalMessage(status)} />}
        {job.queue_position != null ? <p className="text-sm text-muted">{t`Position ${job.queue_position} in this queue.`}</p> : null}
        <OwnerJobLink token={publicToken} path={tenantPath} />
        <OwnerCancel token={publicToken} title={job.title} makerspaceSlug={makerspaceSlug} />
      </div> : null }]}
      actionCard={{ title: t`Your job`, state: "open",
        summary: job ? <StatusPill label={serviceStatusLabel(status)} tone={serviceStatusTone(status)} /> : undefined,
        form: job ? <p className="text-sm text-muted">{t`Keep this link private: anyone with it can see this job's progress.`}</p> : undefined,
        mobileBar: { summary: job ? serviceStatusLabel(status) : t`Job status`, label: t`Your job` } }} />
  </PublicLayout></div>;
}
