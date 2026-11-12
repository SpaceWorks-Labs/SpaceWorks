import { plural, t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { useEffect, useMemo, useState } from "react";
import { LinkedJob } from "./machine/LinkedJob";
import { Navigate, useLocation, useSearchParams } from "react-router-dom";
import { useTransitionNavigate } from "../../../lib/motion";
import { useQuery } from "@tanstack/react-query";

import type { PrinterPool } from "../../../generated/api";
import { collectionResults, getMachines, getMachineTypes, machineKeys, type MachineStatus, type MachineType } from "../machinesApi";
import { machineTypeSegment, parseMachineTypeSegment, staffSubPathFromPath, staffTabPath } from "../staffTabs";
import { MachineDrawer } from "./machine/MachineDrawer";
import { MachineTypeCards } from "./machine/MachineTypeCards";
import { MachineTypePage } from "./machine/MachineTypePage";
import { SharedConsumablesSection } from "./machine/SharedConsumablesSection";
import { poolPath, poolQueryKey } from "./machine/servicePools";
import { useServiceDrafts } from "./machine/serviceDrafts";
import { MachineTypesPanel } from "./MachineTypesPanel";
import { MachineTypeWizard } from "./machine/typeWizard/MachineTypeWizard";
import { TemplateCataloguePanel } from "./machine/typeWizard/TemplateCataloguePanel";
import { NotificationRecipientPicker } from "../NotificationRecipientPicker";
import { DomainSettingsDisclosure } from "../DomainSettingsSection";
import { useAreaPaymentsDrawer } from "../areaPayments/useAreaPaymentsDrawer";
import { DomainPublicStats } from "../../stats/settings/DomainPublicStats";
import { useStaffGet } from "./shared";
import { ListLayout } from "../../../components/layouts";
import { opsQueryState } from "../opsPresentation";
import { DashboardMachineQueue, isDashboardMachineQueue } from "./DashboardMachineQueue";
import { WorkOrdersScreen } from "./machine/workOrders/WorkOrdersScreen";
import { SessionsScreen } from "./machine/sessions/SessionsScreen";
import { AllJobsScreen } from "./machine/AllJobsScreen";
import { AdaptersScreen } from "./machine/adapters/AdaptersScreen";
import { MachineAccessScreen } from "../../machine-access/MachineAccessScreen";
import { adapterSwitches } from "./machine/adapters/adaptersApi";

type StatusFilter = "all" | MachineStatus;
/** The type page's tab views (MachineTypePage); `work-orders` and `sessions` stay `?view=` screens. */
const TYPE_VIEWS = ["machines", "queue", "board", "consumables", "access", "settings"];

type Props = {
  enabledFeatures?: string[];
  makerspaceId: number;
  canManage: boolean;
  canConfigureMachineTypes: boolean;
  maintenanceEnabled: boolean;
  machineServiceEnabled: boolean;
  printingEnabled: boolean;
  reportsEnabled?: boolean;
  publicSiteEnabled?: boolean;
  delegatedRecipientRulesEnabled: boolean;
  guestOnly?: boolean;
  makerspaceSlug?: string | null;
  singleTenantLocked?: boolean;
  printerAdapter?: boolean;
  /** Device adapters console: manage_devices + devices module + machines.integrations (decision 312). */
  adapterConsole?: boolean;
};

export function MachinesPanel(props: Props) {
  const [params] = useSearchParams();
  const queue = params.get("work_queue") ?? "";
  if (isDashboardMachineQueue(queue)) return <DashboardMachineQueue makerspaceId={props.makerspaceId} slug={props.makerspaceSlug} single={props.singleTenantLocked ?? false} guest={props.guestOnly ?? false} enabled={queue === "maintenance_overdue" ? props.maintenanceEnabled : props.printingEnabled && props.machineServiceEnabled} />;
  const job = Number(params.get("job"));
  if (Number.isInteger(job) && job > 0 && props.machineServiceEnabled) return <><LinkedJob jobId={job} /><MachinesWorkspace {...props} /></>;
  return <MachinesWorkspace {...props} />;
}

function MachinesWorkspace({
  enabledFeatures = [],
  makerspaceId,
  canManage,
  canConfigureMachineTypes,
  maintenanceEnabled,
  machineServiceEnabled,
  printingEnabled,
  reportsEnabled = true,
  publicSiteEnabled = false,
  delegatedRecipientRulesEnabled,
  guestOnly = false,
  makerspaceSlug = null,
  singleTenantLocked = false,
  printerAdapter = false,
  adapterConsole = false,
}: Props) {
  const location = useLocation();
  const navigate = useTransitionNavigate();
  const [params, setParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sharedOpen, setSharedOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  // Decision 242(a): job and session charges of the manager's own machine types, from inside Machines.
  const machinePayments = useAreaPaymentsDrawer(makerspaceId, "machines");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const linkedId = params.get("machine");
  useEffect(() => { setSelectedId(Number(linkedId) || null); }, [linkedId]);
  const closeSelection = () => { setSelectedId(null); setParams((current) => { const next = new URLSearchParams(current); next.delete("machine"); return next; }); };
  // Lives HERE, in the container that survives index-to-type navigation, not in
  // `MachineTypePage`. Only one type is mounted at a time now, so a hook inside the page
  // would discard a half-typed service form on every navigation -- the drafts previously
  // survived section collapse for exactly that reason.
  const { draftFor, setDraft } = useServiceDrafts();

  const machines = useQuery({ queryKey: machineKeys.list(makerspaceId), queryFn: () => getMachines(makerspaceId) });
  const machineTypes = useQuery({ queryKey: machineKeys.types(makerspaceId), queryFn: () => getMachineTypes(makerspaceId) });
  const poolQuery = useStaffGet<PrinterPool[]>(
    poolQueryKey(makerspaceId),
    poolPath(makerspaceId),
    canManage && machineServiceEnabled,
  );
  const types = collectionResults(machineTypes.data);
  const allMachines = useMemo(() => machines.data?.results ?? [], [machines.data]);
  const pools = useMemo(() => poolQuery.data ?? [], [poolQuery.data]);
  const sharedPools = useMemo(
    () => pools.filter((pool) => pool.machine_id === null && pool.machine_type_id === null),
    [pools],
  );

  // The machine and machine-type requests are independent, so the type response can fail, go
  // stale, or omit a type while machines of it loaded fine. Building the index from `types`
  // alone then makes those machines VANISH. Nested `machine.machine_type` is the fallback and
  // is display-only: it carries no `can_create_machine`, which correctly reads as no creation
  // authority. It is still NAVIGABLE -- the machines list is server-scoped too, so a machine
  // the server returned implies a type this actor may open.
  const reachableTypes = useMemo(() => {
    const known = new Set(types.map((type) => type.id));
    const extras: MachineType[] = [];
    for (const machine of allMachines) {
      if (known.has(machine.machine_type.id)) continue;
      known.add(machine.machine_type.id);
      extras.push(machine.machine_type);
    }
    return [...types, ...extras];
  }, [allMachines, types]);

  const hrefFor = (machineType: MachineType) =>
    consoleSessionHref(staffTabPath("machines", guestOnly, makerspaceSlug, singleTenantLocked, machineTypeSegment(machineType)));
  const indexHref = consoleSessionHref(staffTabPath("machines", guestOnly, makerspaceSlug, singleTenantLocked));
  const tabHref = (tab: string) => consoleSessionHref(staffTabPath(tab, guestOnly, makerspaceSlug, singleTenantLocked));

  // `/machines/<id-slug>/<view>` on a type page, `/machines/<view>` for a sole type shown
  // inline on the index (0.12.0 row 14: views are routed, like settings subpages).
  const segments = staffSubPathFromPath(location.pathname, guestOnly).split("/").filter(Boolean);
  const requestedTypeId = parseMachineTypeSegment(segments[0] ?? "");
  const routedView = (requestedTypeId !== null ? segments[1] : segments[0]) ?? "";
  // Both server-scoped sources must have SETTLED SUCCESSFULLY before an id can be called
  // unreachable. Judging on the type query alone would bounce a type known only through the
  // nested fallback; judging while either is loading would bounce every direct link on first
  // paint; judging after a failure would turn a network blip into what looks like a revoked
  // permission.
  const sourcesSettled =
    !machineTypes.isLoading && !machineTypes.isError && !machines.isLoading && !machines.isError;
  const selectedType = reachableTypes.find((type) => type.id === requestedTypeId) ?? null;
  const unknownType = requestedTypeId !== null && sourcesSettled && !selectedType;

  // NO auto-redirect when a single type is reachable. Redirecting would make this index --
  // and with it machine-type configuration, shared consumable pools and the delegated
  // recipient picker -- permanently unreachable for exactly the scoped maintainer those
  // controls are meant for. A single-type actor gets that type's page rendered inline below
  // instead, which lands them on their machines without hiding anything, and removes the
  // redirect loop and the flash-redirect at the same time.
  const soleType = reachableTypes.length === 1 ? reachableTypes[0] : null;
  const shownType = selectedType ?? (requestedTypeId === null ? soleType : null);

  // Work orders (machines.maintenance) are a screen of their own, reached from the index, a type page or a drawer.
  const openWorkOrders = () => setParams(new URLSearchParams({ view: "work-orders" }));
  // Machine sessions (L23, machines.sessions): live, to check and closed, from the index.
  const sessionsEnabled = enabledFeatures.includes("machines.sessions");
  const openSessions = (typeId?: number) => setParams(new URLSearchParams({ view: "sessions", ...(typeId ? { s_machine_type: String(typeId) } : {}) }));
  // A15: every job across the types this person manages, grouped by type then machine.
  const jobsEnabled = machineServiceEnabled && canManage;
  const openJobs = () => setParams(new URLSearchParams({ view: "jobs" }));
  if (jobsEnabled && params.get("view") === "jobs") {
    return <AllJobsScreen makerspaceId={makerspaceId} machines={allMachines} onBack={() => setParams(new URLSearchParams())} />;
  }
  if (canManage && params.get("view") === "access") {
    return <MachineAccessScreen makerspaceId={makerspaceId} machines={allMachines}
      onBack={() => setParams(current => { const next = new URLSearchParams(current); next.delete("view"); return next; })} />;
  }
  if (adapterConsole && params.get("view") === "adapters") {
    return <AdaptersScreen makerspaceId={makerspaceId} switches={adapterSwitches(enabledFeatures)}
      onBack={() => setParams(current => { const next = new URLSearchParams(current); ["view", "adapter", "adapter_tab", "adapter_view"].forEach(key => next.delete(key)); return next; })} />;
  }
  if (sessionsEnabled && params.get("view") === "sessions") {
    return <SessionsScreen makerspaceId={makerspaceId} machines={allMachines}
      onBack={() => setParams(current => { const next = new URLSearchParams(current); [...next.keys()].filter(key => key === "view" || key === "session_status" || key.startsWith("s_")).forEach(key => next.delete(key)); return next; })} />;
  }
  if (maintenanceEnabled && params.get("view") === "work-orders") {
    return <WorkOrdersScreen makerspaceId={makerspaceId} machines={allMachines}
      onBack={() => setParams(current => { const next = new URLSearchParams(current); ["view", "work_order", "wo_status", "wo_machine"].forEach(key => next.delete(key)); return next; })} />;
  }

  // Normalise an unknown or unreachable type id back to the index -- the console's existing
  // behaviour for a stale deep link, rather than a dead denial page. `replace` so the bad
  // URL does not sit in history waiting for the back button.
  if (unknownType) {
    return <Navigate replace to={indexHref} />;
  }

  // A deep link whose type is known only through the nested machines fallback resolves once
  // the machines query lands. Rendering the index in the meantime would flash the card grid
  // in front of someone who asked for one specific type, so hold with a skeleton instead --
  // an honest "still resolving", which is also what stops the redirect above from firing
  // early.
  if (requestedTypeId !== null && !selectedType && !sourcesSettled) {
    return (
      <ListLayout header={{ title: t`Machines` }} state={opsQueryState(machines.isLoading || machines.isError ? machines : machineTypes, "machine type")}
        body={{ kind: "rows", rows: null }} empty={{ message: t`No machine types available. Ask your space manager to configure your machine access.` }} />
    );
  }

  const typeMachines = shownType
    ? allMachines.filter((machine) => machine.machine_type.id === shownType.id)
    : [];
  const machineIds = new Set(typeMachines.map((machine) => machine.id));
  const typePools = pools.filter((pool) =>
    pool.machine_type_id === shownType?.id ||
    (pool.machine_id !== null && machineIds.has(pool.machine_id)),
  );
  const onTypePage = shownType !== null && selectedType !== null;
  const viewHref = (view: string) => {
    const rest = new URLSearchParams(params);
    rest.delete("view");
    const segment = [onTypePage && shownType ? machineTypeSegment(shownType) : "", view === "machines" ? "" : view].filter(Boolean).join("/");
    const query = rest.toString();
    return consoleSessionHref(`${staffTabPath("machines", guestOnly, makerspaceSlug, singleTenantLocked, segment)}${query ? `?${query}` : ""}`);
  };
  // Pre-0.12.0 bookmarks and links (`?view=settings`, the dashboard's `?view=queue`) move to the routed view.
  const legacyView = params.get("view");
  if (shownType && legacyView && TYPE_VIEWS.includes(legacyView)) return <Navigate replace to={viewHref(legacyView)} />;

  const settingsVisible = !shownType || routedView === "settings";
  const viewMenu = [...(canManage ? [{ label: t`Machine access`, onClick: () => setParams(new URLSearchParams({ view: "access" })) }] : []),
    ...(jobsEnabled ? [{ label: t`All jobs`, onClick: openJobs }] : []),
    ...(maintenanceEnabled ? [{ label: t`Work orders`, onClick: openWorkOrders }] : []),
    ...(sessionsEnabled ? [{ label: t`Sessions`, onClick: () => openSessions() }] : []),
    ...(adapterConsole ? [{ label: t`Device adapters`, onClick: () => setParams(new URLSearchParams({ view: "adapters" })) }] : [])];
  const settings = !onTypePage ? <>
    {canConfigureMachineTypes && settingsVisible ? <TemplateCataloguePanel makerspaceId={makerspaceId} /> : null}
    <MachineTypesPanel visible={settingsVisible} makerspaceId={makerspaceId} canConfigureMachineTypes={canConfigureMachineTypes} />
    {maintenanceEnabled && delegatedRecipientRulesEnabled ? <NotificationRecipientPicker visible={settingsVisible} delegated makerspaceId={makerspaceId} /> : null}
    {canManage && settingsVisible ? <DomainSettingsDisclosure makerspaceId={makerspaceId} domain="machines" /> : null}
    {canManage && settingsVisible && publicSiteEnabled ? <DomainPublicStats makerspaceId={makerspaceId} area="machines" /> : null}
    {canManage && machineServiceEnabled ? <SharedConsumablesSection visible={settingsVisible} makerspaceId={makerspaceId} pools={sharedPools} existingPools={pools} poolError={poolQuery.error} open={sharedOpen} onToggle={() => setSharedOpen(current => !current)} /> : null}
  </> : null;
  const detail = selectedId !== null ? <MachineDrawer enabledFeatures={enabledFeatures} publicBase={singleTenantLocked || !makerspaceSlug ? "" : `/m/${makerspaceSlug}`} key={selectedId} machineId={selectedId} makerspaceId={makerspaceId} canManageMachines={canManage} maintenanceEnabled={maintenanceEnabled} onClose={closeSelection} /> : null;
  return <div onClickCapture={event => {
    if (event.button || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const link = (event.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="/"]');
    if (link?.getAttribute('href')?.startsWith(indexHref.split("?")[0])) { event.preventDefault(); navigate(link.getAttribute('href')!); }
  }}>
    {shownType ? <MachineTypePage enabledFeatures={enabledFeatures} makerspaceId={makerspaceId} canManage={canManage}
      canConfigureMachineTypes={canConfigureMachineTypes} machineServiceEnabled={machineServiceEnabled} printingEnabled={printingEnabled}
      reportsEnabled={reportsEnabled} machineType={shownType} allMachines={typeMachines}
      visibleMachines={typeMachines.filter(machine => statusFilter === "all" || machine.status === statusFilter)}
      typePools={typePools} formPools={[...sharedPools, ...typePools]} existingPools={pools}
      machinesLoading={machines.isLoading} machinesFailed={machines.isError} onSelectMachine={setSelectedId}
      draft={draftFor(shownType.id)} setDraft={update => setDraft(shownType.id, update)}
      detail={detail} indexHref={onTypePage ? indexHref : undefined} settings={settings} statusFilter={statusFilter}
      onStatusFilter={setStatusFilter} onRetry={() => { void machines.refetch(); void machineTypes.refetch(); }}
      poolError={poolQuery.error instanceof Error ? poolQuery.error.message : undefined} onRetryPools={() => { void poolQuery.refetch(); }}
      onWorkOrders={maintenanceEnabled ? openWorkOrders : undefined} onSessions={sessionsEnabled ? () => openSessions(shownType.id) : undefined} printerAdapter={printerAdapter}
      routedView={{ active: routedView, href: viewHref }} tabHref={tabHref} /> :
      <ListLayout header={{ title: t`Machines`, overflow: machinePayments.actions, subtitle: t`${plural(allMachines.length, { one: "# machine", other: "# machines" })} across ${plural(reachableTypes.length, { one: "# type", other: "# types" })}`,
        primary: canConfigureMachineTypes ? { label: t`Add machine type`, icon: "Plus", onClick: () => setWizardOpen(true) } : undefined, secondary: viewMenu.length > 1 ? { label: t`Views`, menu: viewMenu } : viewMenu[0] }} state={reachableTypes.length ? { status: "ready" } : opsQueryState(machines.isError ? machines : machineTypes, "machines")}
        callout={machineTypes.isError || machines.isError ? { size: "banner", tone: "warn", lead: "Some machine information couldn’t be loaded.", action: { label: t`Retry`, onClick: () => { void machines.refetch(); void machineTypes.refetch(); } } }
          : poolQuery.isError ? { size: "banner", tone: "warn", lead: "Couldn’t load consumable pools. Try again before starting work.", action: { label: t`Retry`, onClick: () => { void poolQuery.refetch(); } } } : undefined}
        body={{ kind: "rows", rows: <><MachineTypeCards machineTypes={reachableTypes} machines={allMachines}
          machinesLoading={machines.isLoading} machinesFailed={machines.isError} typesLoading={machineTypes.isLoading}
          typesFailed={machineTypes.isError} hrefFor={hrefFor} />{settings}</> }}
        empty={{ message: t`No machine types available. Add your first machine type or ask your space manager for access.` }} detail={detail} />}
    {machinePayments.dialog}
    {wizardOpen ? <MachineTypeWizard makerspaceId={makerspaceId} onClose={() => setWizardOpen(false)} enabledFeatures={enabledFeatures} machineServiceEnabled={machineServiceEnabled}
      printerAdapter={printerAdapter} hrefFor={tabHref} /> : null}
  </div>;
}
