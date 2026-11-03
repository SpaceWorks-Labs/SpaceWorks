import { plural } from "../../../../lib/plural";
import { machineStatusLabel } from "./machineStatusLabel";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge, Tabs, StatusPill } from "../../../../components/ui";
import { DetailLayout } from "../../../../components/layouts";
import { opsQueryState } from "../../opsPresentation";
import { useMachineStatus } from "./useMachineStatus";
import { getMachine, machineKeys } from "../../machinesApi";
import { ConsumablesTab } from "./ConsumablesTab";
import { DocumentsTab } from "./DocumentsTab";
import { ErrorsTab } from "./ErrorsTab";
import { MaintenanceTab } from "./MaintenanceTab";
import { LockoutBadge } from "./DowntimePanel";
import { OperatorsTab } from "./OperatorsTab";
import { OverviewTab } from "./OverviewTab";
import { UsageTab } from "./UsageTab";
import { WarrantyTab } from "./WarrantyTab";
import { SessionList } from "./sessions/SessionsScreen";
import { SessionQrCard } from "./sessions/SessionQrCard";

const BASE_TABS = ["Overview", "Operators", "Consumables", "Usage", "Documents", "Errors"] as const;
type MachineTab = (typeof BASE_TABS)[number] | "Maintenance" | "Warranty" | "Sessions";

export function MachineDrawer({
  machineId, makerspaceId, canManageMachines, maintenanceEnabled, onClose, enabledFeatures = [], publicBase = "",
}: {
  machineId: number;
  enabledFeatures?: string[];
  makerspaceId: number;
  canManageMachines: boolean;
  maintenanceEnabled: boolean;
  onClose: () => void;
  /** Member-site path prefix for the session QR (`/m/<slug>`, or "" on a single-space site). */
  publicBase?: string;
}) {
  const [params] = useSearchParams();
  const [activeTab, setActiveTab] = useState<MachineTab>(params.get("detail_tab") === "Maintenance" && maintenanceEnabled ? "Maintenance" : "Overview");
  const machine = useQuery({
    queryKey: machineKeys.detail(machineId),
    queryFn: () => getMachine(machineId),
  });
  const details = machine.data;
  const changeStatus = useMachineStatus(machineId, makerspaceId, details?.status === "idle" ? "running" : "idle");
  const maintenanceAllowed = maintenanceEnabled && details?.can_operate === true;
  // A tab tapped at the edge of the phone's scrolling tab row is brought fully into view
  // (iOS Safari does not focus a tapped button, so focus alone never scrolls it there).
  const mainRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    mainRef.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [activeTab]);
  const tabs: readonly MachineTab[] = [
    ...BASE_TABS.slice(0, 4),
    ...(maintenanceAllowed ? ["Maintenance" as const] : []),
    ...BASE_TABS.slice(4),
    // The machines parent's own warranty switch (#97, C-9).
    ...(details?.can_edit && enabledFeatures.includes("machines.warranty") ? ["Warranty" as const] : []),
    // Machine sessions (L23): this machine's live and finished sessions.
    ...(canManageMachines && enabledFeatures.includes("machines.sessions") ? ["Sessions" as const] : []),
  ];

  return <DetailLayout presentation="drawer" open onClose={onClose} drawerWidth={720}
    title={details?.name ?? "Machine details"} state={opsQueryState(machine, "machine")}
    identity={details?.image_url ? { kind: "image", src: details.image_url } : { kind: "icon", icon: "Cog", tone: "accent" }}
    status={details ? <><StatusBadge status={details.status} label={machineStatusLabel(details.status)} />{!details.is_active ? <StatusPill label="Retired" tone="warn" /> : null}{maintenanceAllowed ? <LockoutBadge machineId={machineId} /> : null}</> : undefined}
    actions={{ primary: details?.can_operate ? { label: details.status === "idle" ? "Mark running" : "Mark idle", pending: changeStatus.isPending, onClick: () => changeStatus.mutate() } : undefined }}
    meta={details ? [details.machine_type.name, plural(Number(details.usage_hours), "total hour")] : undefined}
    /* Phones keep the shared tab bar's single scrolling row (eight tabs wrapped into three ragged
       rows there); from `sm` the drawer is wide enough that every tab fits once wrapped, so the
       row wraps instead of hiding tabs behind a scroll. */
    main={details ? <div ref={mainRef} className="grid min-w-0 gap-6 sm:[&_[role=tablist]]:flex-wrap sm:[&_[role=tablist]]:overflow-visible sm:[&_[role=tablist]]:[mask-image:none]">
      {changeStatus.error ? <p role="alert" className="text-sm text-danger">{changeStatus.error.message}</p> : null}
      <Tabs label="Machine details" tabs={tabs.map(tab => ({ key: tab, label: tab, href: "#" }))} activeKey={activeTab} onChange={key => setActiveTab(key as MachineTab)}>
            {activeTab === "Overview" ? (
              <OverviewTab
                publicDetailsEnabled={enabledFeatures.includes("machines.public_detail")}
                machine={details}
                makerspaceId={makerspaceId}
                canManageMachines={canManageMachines}
                canEdit={details.can_edit}
                canOperate={details.can_operate}
                canRetire={details.can_retire}
                canUnretire={details.can_unretire}
              />
            ) : null}
            {activeTab === "Operators" ? (
              <OperatorsTab machineId={machineId} canDelegate={details.can_delegate} />
            ) : null}
            {activeTab === "Consumables" ? (
              <ConsumablesTab machineId={machineId} canEdit={details.can_edit}
                canOperate={details.can_operate} />
            ) : null}
            {activeTab === "Usage" ? (
              <UsageTab machineId={machineId} makerspaceId={makerspaceId} canOperate={details.can_operate} />
            ) : null}
            {activeTab === "Maintenance" && maintenanceAllowed ? (
              <MaintenanceTab
                metersEnabled={enabledFeatures.includes("maintenance.meters")}
                feedEnabled={enabledFeatures.includes("maintenance.calendar_feed")}
                makerspaceId={makerspaceId}
                machineId={machineId}
                canEdit={details.can_edit}
                canOperate={details.can_operate}
                enabled={activeTab === "Maintenance" && maintenanceAllowed}
                retired={!details.is_active}
              />
            ) : null}
            {activeTab === "Documents" ? (
              <DocumentsTab machineId={machineId} canEdit={details.can_edit} />
            ) : null}
            {activeTab === "Errors" ? (
              <ErrorsTab machineId={machineId} canOperate={details.can_operate} />
            ) : null}
            {activeTab === "Sessions" ? <div className="grid gap-4">
              <SessionQrCard machineId={machineId} machineName={details.name} basePath={publicBase} />
              {(["live", "review", "closed"] as const).map(status => <section key={status} className="grid gap-2" aria-label={`${status} sessions`}>
                <h3 className="title-section">{status === "live" ? "Live" : status === "review" ? "To check" : "Closed"}</h3>
                <SessionList makerspaceId={makerspaceId} machineId={machineId} status={status} /></section>)}
            </div> : null}
            {activeTab === "Warranty" && details.can_edit ? (
              <WarrantyTab machineId={machineId} />
            ) : null}</Tabs>
    </div> : null} />;
}
