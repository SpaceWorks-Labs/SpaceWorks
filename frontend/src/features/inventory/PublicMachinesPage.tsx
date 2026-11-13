import { t } from "@lingui/core/macro";
import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import { publicPageChrome } from "./PublicPageChrome";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { CollapsibleSection, ListRow, StatusPill, RelativeTime, EmptyState } from "../../components/ui";
import { publicErrorState } from "./publicErrorState";
import type { ApiPath } from "../../generated/api";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "./PublicInventoryParts";
import { useTenantBootstrap } from "./usePublicInventory";
import { MachineIntakeForm } from "./MachineIntakeForm";
import { machineIntakeAvailable } from "./machineIntakeAvailability";
import { QueueSummary } from "../machine-service/QueueSummary";
import type { MachineQueueSummary } from "../machine-service/types";
import { fetchJobTypes, jobKeys } from "../machine-jobs/api";
import { Pagination } from "../../components/ui/Pagination";

type PublicMachine = {
  id?: number;
  status_since?: string;
  training_required?: boolean | null;
  queue?: MachineQueueSummary | null;
  name: string;
  machine_type: { id?: number; name: string; icon: string };
  image_url: string | null;
  status: "idle" | "running" | "reserved" | "maintenance" | "offline";
  usage_hours: string;
};

type PaginatedMachines = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PublicMachine[];
};

// Maintenance and offline mean different things to a visitor (planned work vs. not available at all).
const MACHINE_STATUS: Record<PublicMachine["status"], string> = { idle: "Available", running: "In use", reserved: "Reserved", maintenance: "Maintenance", offline: "Offline" };

const PUBLIC_MACHINES_PATH: ApiPath = "/api/v1/public/{makerspace_slug}/machines";

function publicMachinesPath(slug: string) {
  return PUBLIC_MACHINES_PATH.replace("/api/v1", "").replace(
    "{makerspace_slug}", encodeURIComponent(slug),
  );
}

export function PublicMachinesPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const detailEnabled = bootstrap?.features.includes("machines.public_detail");
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState("");
  const [trainingOnly, setTrainingOnly] = useState(false);
  useEffect(() => { setPage(1); setKind(""); setTrainingOnly(false); }, [makerspaceSlug, detailEnabled]);
  const machines = useQuery({
    queryKey: ["public-machines", makerspaceSlug, detailEnabled, page],
    queryFn: () => tenantPublicRequest<PaginatedMachines>(
      makerspaceSlug, publicMachinesPath(makerspaceSlug) + (detailEnabled ? "/details" : "") + `?page=${page}&page_size=24`,
    ),
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });

  // The public payload carries no type id, so the type name is the grouping key.
  const groups = useMemo(() => {
    const byType = new Map<string, { icon: string; machines: PublicMachine[] }>();
    for (const machine of machines.data?.results ?? []) {
      const key = machine.machine_type.name;
      const existing = byType.get(key);
      if (existing) existing.machines.push(machine);
      else byType.set(key, { icon: machine.machine_type.icon, machines: [machine] });
    }
    return [...byType.entries()].map(([name, group]) => ({ name, ...group }));
  }, [machines.data]);

  // Types taking job requests go through the one "Request a job" form (#140), not the per-machine dialog.
  const intakeAvailable = machineIntakeAvailable(bootstrap, makerspaceSlug);
  const jobsOn = intakeAvailable && Boolean(bootstrap?.features.includes("machines.job_requests"));
  const jobTypes = useQuery({ queryKey: jobKeys.types(makerspaceSlug), queryFn: () => fetchJobTypes(makerspaceSlug), enabled: jobsOn && Boolean(makerspaceSlug), retry: false });
  const jobTypeIds = new Set((jobsOn ? jobTypes.data ?? [] : []).map(type => type.machine_type_id));

  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const toggleGroup = (name: string) => setCollapsed((current) => {
    const next = new Set(current);
    if (!next.delete(name)) next.add(name);
    return next;
  });

  const visibleGroups = groups.filter(group => !kind || group.name === kind).map(group => ({ ...group, machines: group.machines.filter(machine => !trainingOnly || machine.training_required === true) })).filter(group => group.machines.length);
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  return <div style={brandStyle}>
    <PageMetadata title={t`Machines · ${displayName}`} description={t`What you can use at ${displayName}`} path={tenantPath("machines")}
      image={bootstrap?.makerspace.cover_image_url || bootstrap?.makerspace.logo_url} siteName={displayName} />
    <PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)}
      header={{ title: t`Machines`, subtitle: t`What you can use at ${displayName}`, ...(jobTypeIds.size
        ? { primary: { label: t`Request a job`, href: tenantPath("machine-jobs/new") }, secondary: { label: t`Member area`, href: tenantPath("member") } }
        : { primary: { label: t`Member area`, href: tenantPath("member") } }) }}
      state={machines.isLoading ? { status: "loading" } : machines.error ? publicErrorState(machines.error, { surface: "machines" }, () => { void machines.refetch(); }) : { status: "ready" }}
      isEmpty={!groups.length} empty={{ message: t`No machines listed yet. Check back soon.` }}>
      {!intakeAvailable && bootstrap ? <p role="status">{t`Online machine requests aren't available here. Ask space staff for help.`}</p> : null}
      <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label={t`Filter machines`}>
        <button className={!kind ? "desk-button-brand" : "desk-button"} type="button" aria-pressed={!kind} onClick={() => setKind("")}>{t`All kinds`}</button>
        {groups.map(group => <button key={group.name} className={kind === group.name ? "desk-button-brand" : "desk-button"} type="button" aria-pressed={kind === group.name} onClick={() => setKind(group.name)}>{group.name}</button>)}
        {detailEnabled ? <button className={trainingOnly ? "desk-button-brand" : "desk-button"} type="button" aria-pressed={trainingOnly} onClick={() => setTrainingOnly(value => !value)}>{t`Training required`}</button> : null}
      </div>
      {!visibleGroups.length ? <EmptyState message={t`No machines match these filters. Choose another kind or clear the filters.`} action={{ label: t`Clear filters`, onClick: () => { setKind(""); setTrainingOnly(false); } }} /> : null}
      <div className="grid gap-6">{visibleGroups.map(group => <CollapsibleSection key={group.name} title={group.name} icon={group.icon || null}
        count={group.machines.length} open={!collapsed.has(group.name)} onToggle={() => toggleGroup(group.name)}>
        <div className="grid gap-3 p-3">{group.machines.map(machine => <div key={machine.name}>
          <ListRow title={machine.name} identity={machine.image_url ? { kind: "image", src: machine.image_url } : { kind: "icon", icon: "Wrench", tone: "neutral" }}
            meta={<>{t`${machine.usage_hours} h logged`}{machine.status_since ? <> {t` · Status since `}<RelativeTime date={machine.status_since} /></> : null}
              {machine.training_required != null ? <span className="mt-1 block">{machine.training_required ? t`Training required` : t`No service training required`}</span> : null}
              {machine.queue ? <span className="mt-1 block"><QueueSummary summary={machine.queue} /></span> : null}</>}
            right={<StatusPill label={MACHINE_STATUS[machine.status] ?? machine.status} tone={machine.status === "idle" ? "success" : machine.status === "maintenance" || machine.status === "offline" ? "warn" : "info"} />} />
          {machine.machine_type.id && jobTypeIds.has(machine.machine_type.id) ? <Link className="desk-button mt-3" to={tenantPath(`machine-jobs/new?type=${machine.machine_type.id}`)}>{t`Request a job`}</Link>
            : intakeAvailable && bootstrap?.features.includes("machines.structured_intake") && machine.id && machine.machine_type.id ? <MachineIntakeForm key={machine.id} slug={makerspaceSlug} machineId={machine.id} typeId={machine.machine_type.id} available={intakeAvailable} dialog trackingPath={token => tenantPath(`machine-service/requests/${token}`)} /> : null}
        </div>)}</div>
      </CollapsibleSection>)}</div>
      <Pagination page={page} onChange={setPage} totalPages={Math.max(1, Math.ceil((machines.data?.count ?? 0) / 24))} count={machines.data?.count} pageSize={24} disabled={machines.isFetching} />
    </PublicLayout>
  </div>;
}
