import { t } from "@lingui/core/macro";
import { plural } from "../../../../lib/plural";
import { QueueSummary } from "../../../machine-service/QueueSummary";
import { machineStatusLabel } from "./machineStatusLabel";
import { MaterialCataloguePanel } from "./MaterialCataloguePanel";
import { CertificationsPanel } from "./CertificationsPanel";
import { MachineReminderPolicy } from "./MachineReminderPolicy";
import { JobBoard } from "./JobBoard";
import { JobSettingsEditor } from "./JobSettingsEditor";
import { SessionSettingsEditor } from "./sessions/SessionSettingsEditor";
import { EmptyState, StatusBadge, Tabs, DataTable } from "../../../../components/ui";
import { ImageThumbnail } from "../../../../components/ui/ImageThumbnail";
import { DetailLayout, FlowLayout } from "../../../../components/layouts";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { machineTypeIdentity } from "./MachineTypeCards";
import { useOpsTabs } from "../../opsPresentation";
import type { PrinterPool } from "../../../../generated/api";
import { isBuiltinPrinterType } from "../../machinesApi";
import type { Machine, MachineType } from "../../machinesApi";
import { MachineServiceConsole } from "./MachineServiceConsole";
import { PrinterServiceConsole } from "./PrinterServiceConsole";
import { ConsumablePoolCreateForm } from "./ConsumablePoolCreateForm";
import { MachineCreateForm } from "./MachineCreateForm";
import { ConsumablePoolList } from "./SharedConsumablesSection";
import type { ServiceDraft } from "./serviceDrafts";

type Props = {
  detail?: ReactNode; indexHref?: string; settings?: ReactNode; statusFilter: string; onStatusFilter: (value: "all" | Machine["status"]) => void; onRetry: () => void; poolError?: string; onRetryPools: () => void;
  enabledFeatures?: string[];
  makerspaceId: number;
  canManage: boolean;
  canConfigureMachineTypes?: boolean;
  machineServiceEnabled: boolean;
  printingEnabled: boolean;
  reportsEnabled?: boolean;
  machineType: MachineType;
  allMachines: Machine[];
  visibleMachines: Machine[];
  typePools: PrinterPool[];
  formPools: PrinterPool[];
  existingPools: PrinterPool[];
  machinesLoading: boolean;
  machinesFailed: boolean;
  onSelectMachine: (machineId: number) => void;
  draft: ServiceDraft;
  setDraft: (update: (draft: ServiceDraft) => ServiceDraft) => void;
  /** Opens the work-order screen (present only when machines.maintenance is on). */
  onWorkOrders?: () => void;
};



/** One machine type's whole world: its machines, its bound consumables, its service queue.
 *
 * This replaces the collapsible `MachineTypeSection`. Every content rule that section
 * carried is preserved verbatim, because each was a bug someone already hit:
 * both empty states require a SUCCESSFUL load, and `type_payload.model` is displayed for
 * any type that records one -- the retired printer roster was the only place it was ever
 * shown, and `run_machine_model` reads it.
 */
export function MachineTypePage({ enabledFeatures = [], makerspaceId, canManage, canConfigureMachineTypes = false,
  machineServiceEnabled, printingEnabled, reportsEnabled = true, machineType, allMachines, visibleMachines,
  typePools, formPools, existingPools, machinesLoading, machinesFailed, onSelectMachine, draft, setDraft,
  detail, indexHref, settings, statusFilter, onStatusFilter, onRetry, poolError, onRetryPools, onWorkOrders }: Props) {
  const [creating, setCreating] = useState(false);
  const [createdMachineId, setCreatedMachineId] = useState<number | null>(null);
  // Lifted here so the Service queue tab header can open manual usage in one click.
  const [logging, setLogging] = useState(false);
  const [params] = useSearchParams();
  const queueStatus = params.get("job_status") ?? undefined;
  const service = machineServiceEnabled && canManage;
  const choices = [{ key: "machines", label: t`Machines`, count: allMachines.length },
    ...(service ? [{ key: "queue", label: t`Service queue` }, { key: "board", label: t`Queue board` }, { key: "consumables", label: t`Consumables` }] : []),
    ...(machineType.can_create_machine === true ? [{ key: "certifications", label: t`Certifications` }] : []),
    ...(canConfigureMachineTypes || settings ? [{ key: "settings", label: t`Settings` }] : [])];
  const view = useOpsTabs("view", choices, "machines");
  const statuses = ["all", "idle", "running", "reserved", "maintenance", "offline"] as const;
  const main = <>
    {view.active === "machines" ? <section aria-label={`${machineType.name} machines`} className="grid gap-4">
      <Tabs label={t`Machine status`} activeKey={statusFilter} onChange={key => onStatusFilter(key as typeof statusFilter & ("all" | Machine["status"]))}
        tabs={statuses.map(key => ({ key, label: key === "all" ? t`All statuses` : key.charAt(0).toUpperCase() + key.slice(1), href: "#" }))}>
      {!allMachines.length ? <EmptyState message={t`No machines are registered for this type. Add the first one with Add machine.`} /> :
        !visibleMachines.length ? <EmptyState message={t`No machines match the selected status. Choose another status.`} /> :
        <DataTable data={visibleMachines} columns={[
          { key: "name", header: "Name", render: machine => <button className="desk-button-ghost min-h-11 max-w-full justify-start text-left" onClick={() => onSelectMachine(machine.id)}><ImageThumbnail src={machine.image_url} alt={machine.name} className="h-10 w-10 shrink-0" /><span className="min-w-0 break-words">
            <strong className="block">{machine.name}</strong><span className="block text-sm text-muted">{[machine.type_payload?.model, machine.location || "No location"].filter(Boolean).join(" · ")}</span>
          </span></button> },
          { key: "status", header: "Status", render: machine => <StatusBadge status={machine.status} label={machineStatusLabel(machine.status)} /> },
          { key: "usage_hours", header: "Usage", render: machine => <span className="tabular-nums">{machine.usage_hours} h</span> },
          ...(visibleMachines.some(machine => machine.service_queue_summary) ? [{ key: "service_queue", header: "Service queue",
            render: (machine: Machine) => <QueueSummary summary={machine.service_queue_summary} /> }] : []),
        ]} />}
      </Tabs>
    </section> : null}
    {service ? isBuiltinPrinterType(machineType) ?
      <PrinterServiceConsole visible={view.active === "queue"} makerspaceId={makerspaceId} canManage={canManage} printingEnabled={printingEnabled} reportsEnabled={reportsEnabled} machineType={machineType} machines={allMachines} pools={formPools} draft={draft} setDraft={setDraft} queueStatus={queueStatus} logging={logging} onLogging={setLogging} /> :
      <MachineServiceConsole visible={view.active === "queue"} makerspaceId={makerspaceId} canManage={canManage} machineType={machineType} machines={allMachines} pools={formPools} draft={draft} setDraft={setDraft} queueStatus={queueStatus} logging={logging} onLogging={setLogging} /> : null}
    {service ? <JobBoard visible={view.active === "board"} makerspaceId={makerspaceId} machineType={machineType} machines={allMachines} pools={formPools}
      batchEnabled={enabledFeatures.includes("machines.batch_start")} /> : null}
    {service ? <>
      <ConsumablePoolCreateForm visible={view.active === "consumables"} makerspaceId={makerspaceId} machineType={machineType} existingPools={existingPools} />
      <ConsumablePoolList visible={view.active === "consumables"} makerspaceId={makerspaceId} pools={typePools} />
    </> : null}
    {machineType.can_create_machine === true ? <CertificationsPanel visible={view.active === "certifications"} makerspaceId={makerspaceId} machineTypeId={machineType.id} /> : null}
    <>
      {canConfigureMachineTypes && (enabledFeatures.includes("machines.material_catalogue") || enabledFeatures.includes("machines.structured_intake")) ? <MaterialCataloguePanel visible={view.active === "settings"} makerspaceId={makerspaceId} typeId={machineType.id} custom={machineType.makerspace !== null} materialsEnabled={enabledFeatures.includes("machines.material_catalogue")} intakeEnabled={enabledFeatures.includes("machines.structured_intake")} /> : null}
      {canConfigureMachineTypes ? <MachineReminderPolicy visible={view.active === "settings"} makerspaceId={makerspaceId} machineTypeId={machineType.id} /> : null}
      {canConfigureMachineTypes && machineServiceEnabled ? <JobSettingsEditor visible={view.active === "settings"} makerspaceId={makerspaceId} machineTypeId={machineType.id} /> : null}
      {canConfigureMachineTypes && enabledFeatures.includes("machines.sessions") ? <SessionSettingsEditor visible={view.active === "settings"} makerspaceId={makerspaceId} machineTypeId={machineType.id} /> : null}{settings}
    </>
    {creating ? <FlowLayout presentation="dialog" open title={t`Add machine`} steps={[]} current="create" state={{ status: "ready" }} onCancel={() => { setCreating(false); setCreatedMachineId(null); }}
      work={<MachineCreateForm makerspaceId={makerspaceId} machineType={machineType} hideSubmit onCreated={setCreatedMachineId}
        onDone={() => { const id = createdMachineId; setCreating(false); setCreatedMachineId(null); if (id !== null) onSelectMachine(id); }} />}
      footer={createdMachineId === null ? { next: { label: t`Add machine`, onClick: () => document.querySelector<HTMLFormElement>("#machine-create-form")?.requestSubmit() } }
        : { next: { label: t`Done`, onClick: () => { const id = createdMachineId; setCreating(false); setCreatedMachineId(null); onSelectMachine(id); } } }} /> : null}
    {detail}
  </>;
  return <div onClickCapture={view.onClickCapture}>
    <DetailLayout title={indexHref ? machineType.name : t`Machines`} identity={machineTypeIdentity(machineType)}
      back={indexHref ? { label: t`All machine types`, href: indexHref } : undefined}
      meta={[...(indexHref ? [] : [machineType.name]), plural(allMachines.length, "machine"), `${allMachines.filter(machine => machine.status === "running").length} running`]}
      actions={{ primary: canManage && machineType.can_create_machine === true ? { label: t`Add machine`, icon: "Plus", onClick: () => setCreating(true) } : undefined,
        secondary: service && view.active === "queue" ? { label: t`Log usage`, onClick: () => setLogging(true) } : undefined,
        overflow: onWorkOrders ? [{ label: t`Work orders`, onClick: onWorkOrders }] : undefined }}
      banner={poolError ? { size: "banner", tone: "warn", lead: "Couldn’t load consumable pools. Try again before starting work.", action: { label: t`Retry`, onClick: onRetryPools } } : undefined}
      tabs={view.tabs} activeTab={view.active} main={main}
      state={view.active !== "machines" ? { status: "ready" } : machinesLoading ? { status: "loading" } : machinesFailed ? { status: "error", error: "Couldn't load machines. Try again.", onRetry } : { status: "ready" }} />

  </div>;
}
