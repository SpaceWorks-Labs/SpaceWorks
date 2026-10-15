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
import { OperatorsTab } from "./OperatorsTab";
import { OverviewTab } from "./OverviewTab";
import { UsageTab } from "./UsageTab";
import { WarrantyTab } from "./WarrantyTab";

const BASE_TABS = ["Overview", "Operators", "Consumables", "Usage", "Documents", "Errors"] as const;
type MachineTab = (typeof BASE_TABS)[number] | "Maintenance" | "Warranty";

export function MachineDrawer({
  machineId, makerspaceId, canManageMachines, maintenanceEnabled, onClose, enabledFeatures = [],
}: {
  machineId: number;
  enabledFeatures?: string[];
  makerspaceId: number;
  canManageMachines: boolean;
  maintenanceEnabled: boolean;
  onClose: () => void;
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
    ...(details?.can_edit ? ["Warranty" as const] : []),
  ];

  return <DetailLayout presentation="drawer" open onClose={onClose} drawerWidth={720}
    title={details?.name ?? "Machine details"} state={opsQueryState(machine, "machine")}
    identity={details?.image_url ? { kind: "image", src: details.image_url } : { kind: "icon", icon: "Cog", tone: "accent" }}
    status={details ? <><StatusBadge status={details.status} label={machineStatusLabel(details.status)} />{!details.is_active ? <StatusPill label="Retired" tone="warn" /> : null}</> : undefined}
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
            {activeTab === "Warranty" && details.can_edit ? (
              <WarrantyTab machineId={machineId} />
            ) : null}</Tabs>
    </div> : null} />;
}
