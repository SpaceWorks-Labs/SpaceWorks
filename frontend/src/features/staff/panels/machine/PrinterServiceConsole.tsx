import { machineStatusLabel } from "./machineStatusLabel";
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { MachineServiceRequest, PrinterPool, PrinterServiceReport, TypedManualUsageResponse } from "../../../../generated/api";
import { ErrorBlock, ListRow, StatusBadge, OverflowMenu, Modal, EmptyState } from "../../../../components/ui";
import { ServiceConsoleSections, ServiceQueueTabs } from "./ServiceConsoleSections";
import { staffRequest } from "../../../../lib/api";
import { machineKeys } from "../../machinesApi";
import { CancelNotice, ServiceEtaLine } from "./ServiceEtaLine";
import type { Machine, MachineType } from "../../machinesApi";
import { useStaffGet } from "../shared";
import { clearedActionDraft } from "./serviceDrafts";
import type { ServiceActionName, ServiceDraft } from "./serviceDrafts";
import { poolQueryKey, usablePools } from "./servicePools";

type Props = {
  visible?: boolean;
  makerspaceId: number;
  canManage: boolean;
  printingEnabled: boolean;
  reportsEnabled?: boolean;
  machineType: MachineType;
  machines: Machine[];
  pools: PrinterPool[];
  draft: ServiceDraft;
  setDraft: (update: (draft: ServiceDraft) => ServiceDraft) => void;
  /** Queue sub-tab to open first (`?job_status=` deep link). */
  queueStatus?: string;
  /** Manual-usage dialog state, lifted to the type page so its header can open it. */
  logging?: boolean;
  onLogging?: (open: boolean) => void;
};

const focusRing = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
// Mirrors backend `printer_capabilities.PRINTER_SLUG`.
const PRINTER_SLUG = "3d_printer";

export function PrinterServiceConsole({ makerspaceId, canManage, printingEnabled, reportsEnabled = true, machineType, machines, pools, draft, setDraft, visible = true, queueStatus, logging: liftedLogging, onLogging: setLiftedLogging }: Props) {
  const [ownLogging, setOwnLogging] = useState(false);
  const logging = liftedLogging ?? ownLogging;
  const setLogging = setLiftedLogging ?? setOwnLogging;
  const queryClient = useQueryClient();
  // Filter by the stable machine-type ID, not the slug: slugs are not unique across the
  // global/tenant split, so a makerspace-local type sharing a built-in's slug would pull in
  // the other type's jobs and let a manager mutate them from the wrong section.
  const typeFilter = `machine_type_id=${machineType.id}`;
  const requests = useStaffGet<MachineServiceRequest[]>(
    ["machine-service-requests", makerspaceId, machineType.id],
    `/admin/makerspaces/${makerspaceId}/machine-service/requests?${typeFilter}`,
    canManage && printingEnabled,
  );
  const manualUsage = useStaffGet<TypedManualUsageResponse[]>(
    ["machine-service-manual", makerspaceId, machineType.id],
    `/admin/makerspaces/${makerspaceId}/machine-service/typed-manual-usage?${typeFilter}`,
    canManage,
  );
  const report = useStaffGet<PrinterServiceReport>(
    ["printer-service-report", makerspaceId, machineType.id],
    // The REPORT endpoint is a different contract: it discriminates on the `machine_type`
    // SLUG to decide whether to emit `printer_metrics`. Sending the id instead silently
    // returns the generic report, and the render below dereferences `printer_metrics`, so
    // the whole Machines panel dies in its error boundary. This console only ever mounts
    // for the global built-in printer, so the literal slug is exactly right here.
    `/admin/makerspace/${makerspaceId}/machine-service-report?machine_type=${PRINTER_SLUG}`,
    canManage && printingEnabled && reportsEnabled,
  );
  const printerUsage = useMemo(
    () => (manualUsage.data ?? []).filter((entry) => entry.metering_unit === "weight"),
    [manualUsage.data],
  );
  const actionPools = usablePools(pools, "grams", draft.actionValues.machine_id, machines, makerspaceId);
  const manualPools = usablePools(pools, "grams", draft.manual.machine_id, machines, makerspaceId);

  const invalidate = () => void Promise.all([
    queryClient.invalidateQueries({ queryKey: ["machine-service-requests", makerspaceId, machineType.id] }),
    queryClient.invalidateQueries({ queryKey: ["machine-service-manual", makerspaceId, machineType.id] }),
    queryClient.invalidateQueries({ queryKey: ["printer-service-report", makerspaceId, machineType.id] }),
    queryClient.invalidateQueries({ queryKey: ["operations-report"] }),
    queryClient.invalidateQueries({ queryKey: poolQueryKey(makerspaceId) }),
    // Service transitions change the assigned machine's status, and manual usage its
    // usage hours; without this the integrated machine row and the status filter
    // stay stale until an unrelated refetch.
    queryClient.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }),
  ]);
  const submitManual = useMutation({
    mutationFn: () => staffRequest(`/admin/makerspaces/${makerspaceId}/machine-service/typed-manual-usage`, {
      method: "POST",
      body: JSON.stringify({
        machine_id: Number(draft.manual.machine_id),
        consumable_pool_id: draft.manual.consumable_pool_id ? Number(draft.manual.consumable_pool_id) : null,
        duration_minutes: Number(draft.manual.duration_minutes),
        grams: draft.manual.quantity || undefined,
        outcome: draft.manual.outcome,
        percent_complete: Number(draft.manual.percent_complete),
        reason: draft.manual.reason || undefined,
        note: draft.manual.note || undefined,
      }),
    }),
    onSuccess: () => {
      setDraft((current) => ({ ...current, manual: { ...current.manual, machine_id: "", consumable_pool_id: "", duration_minutes: "", quantity: "", outcome: "success", percent_complete: "100", reason: "", note: "" } }));
      setLogging(false);
      invalidate();
    },
  });
  const runAction = useMutation({
    mutationFn: () => {
      if (!draft.action) throw new Error("Choose an action.");
      return staffRequest(`/admin/machine-service/requests/${draft.action.id}/${draft.action.name}`, {
        method: "POST",
        body: JSON.stringify(actionBody(draft.action.name, draft.actionValues)),
      });
    },
    onSuccess: () => {
      setDraft(clearedActionDraft);
      invalidate();
    },
  });

  if (!canManage || !visible) return null;
  return (
    <div className="grid gap-4">
      <ServiceConsoleSections queue={printingEnabled ? (<Subsection title="3D-printer queue">
          <p className="mb-3 text-sm text-muted">Accept jobs, reserve filament, start work, reconcile actual grams, then complete, fail, collect, or reprint.</p>
          <ServiceQueueTabs rows={requests.data} initialStatus={queueStatus}>{visible => <div className="grid gap-3">
            {visible?.map((request) => (
              <ListRow key={request.id} title={request.title} identity={{ kind: "avatar", name: request.requester_name || "Member", seed: String(request.id) }}
                meta={<> {request.requester_name} · Planned {request.planned_grams} g · actual {request.actual_consumed_quantity ?? "0"} g<ServiceEtaLine request={request} /></>}
                right={<div className="flex flex-wrap items-center gap-2"><StatusBadge status={request.status} label={machineStatusLabel(request.status)} /><ServiceActions request={request} onAction={name => setDraft(current => ({ ...current, action: { id: request.id, name } }))} /></div>} />
            )) ?? <p className="text-sm text-muted">Loading printer queue…</p>}
          </div>}</ServiceQueueTabs>
          {draft.action ? <Modal open title={`${draft.action.name} job`} onClose={() => setDraft(current => ({ ...current, action: null }))}><ActionForm action={draft.action.name} values={draft.actionValues} setValues={(actionValues) => setDraft((current) => ({ ...current, actionValues }))} printers={machines} pools={actionPools} pending={runAction.isPending} onCancel={() => setDraft((current) => ({ ...current, action: null }))} onSubmit={() => runAction.mutate()} /><ErrorBlock error={runAction.error} /></Modal> : null}
        </Subsection>) : undefined} manualForm={<ManualUsageForm draft={draft} setDraft={setDraft} printers={machines} pools={manualPools} pending={submitManual.isPending} onSubmit={() => submitManual.mutate()} />} manualRows={<div className="mt-3 grid gap-2">{manualUsage.data && !printerUsage.length ? <EmptyState message="No manual usage logged yet. Log the first entry." /> : null}{printerUsage.map(entry => <ListRow key={entry.id} title={`${entry.duration_minutes} min`} meta={<>{entry.consumed_grams} g{entry.outcome === "failed" ? ` · ${entry.percent_complete}%` : ""}</>} right={<StatusBadge status={entry.outcome} label={machineStatusLabel(entry.outcome)} />} />)}</div>} reports={printingEnabled && reportsEnabled ? (<Subsection title="Printer reports">
          <div className="grid gap-2 md:grid-cols-2">
            {report.data?.printer_metrics.map((metric) => <p className="rounded-md border border-line p-3 text-sm" key={`${metric.makerspace_id ?? makerspaceId}:${metric.machine_id}`}><strong>{metric.machine_name}</strong><span className="mt-1 block text-xs text-muted">{metric.completed_hours}h complete - {metric.failed_partial_hours}h failed - {metric.manual_hours}h manual - {metric.consumed_grams}g used</span></p>)}
            {report.data && report.data.printer_metrics.length === 0 ? <p className="text-sm text-muted">No completed printer activity yet.</p> : null}
          </div>
        </Subsection>) : undefined} logging={logging} onLogging={setLogging} />
      <ErrorBlock error={[requests.error, manualUsage.error, report.error, submitManual.error, runAction.error].find((item) => item instanceof Error)} />
    </div>
  );
}

function actionBody(action: ServiceActionName, values: ServiceDraft["actionValues"]) {
  if (action === "accept") return { estimated_minutes: Number(values.estimated_minutes), planned_grams: values.planned_quantity || undefined };
  if (action === "start") return { machine_id: values.machine_id ? Number(values.machine_id) : null, consumable_pool_id: values.consumable_pool_id ? Number(values.consumable_pool_id) : undefined, estimated_minutes: Number(values.estimated_minutes), planned_grams: values.planned_quantity || undefined };
  if (action === "complete") return { actual_minutes: Number(values.actual_minutes), actual_grams: values.actual_quantity || undefined };
  if (action === "fail") return { actual_minutes: Number(values.actual_minutes), actual_grams: values.actual_quantity || undefined, percent_complete: Number(values.percent_complete), reason: values.reason };
  if (action === "cancel") return values.reason ? { reason: values.reason } : {};
  return action === "reject" ? { reason: values.reason } : {};
}

function ServiceActions({ request, onAction }: { request: MachineServiceRequest; onAction: (name: ServiceActionName) => void }) {
  const cancel = { label: "Cancel job", tone: "danger" as const, onClick: () => onAction("cancel") };
  if (request.status === "pending") return <><button className="desk-button-success" onClick={() => onAction("accept")}>Accept</button><OverflowMenu actions={[{ label: "Reject", tone: "danger", onClick: () => onAction("reject") }, cancel]} /></>;
  if (request.status === "accepted") return <><button className="desk-button-primary" onClick={() => onAction("start")}>Start</button><OverflowMenu actions={[cancel]} /></>;
  if (request.status === "in_progress") return <><button className="desk-button-success" onClick={() => onAction("complete")}>Complete</button><OverflowMenu actions={[{ label: "Fail", tone: "danger", onClick: () => onAction("fail") }, cancel]} /></>;
  if (request.status === "completed") return <button className="desk-button-success" onClick={() => onAction("collect")}>Collect</button>;
  return request.status === "failed" ? <button className="desk-button-warn" onClick={() => onAction("reprint")}>Reprint</button> : null;
}

function ActionForm({ action, values, setValues, printers, pools, pending, onCancel, onSubmit }: { action: ServiceActionName; values: ServiceDraft["actionValues"]; setValues: (values: ServiceDraft["actionValues"]) => void; printers: Machine[]; pools: PrinterPool[]; pending: boolean; onCancel: () => void; onSubmit: () => void }) {
  const input = (key: keyof typeof values, label: string) => <label className="eyebrow grid gap-1">{label}<input className={`desk-input ${focusRing}`} inputMode={key === "reason" ? undefined : "decimal"} value={values[key]} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></label>;
  return <div className="mt-3 rounded-md border border-accent bg-bg p-3"><h5 className="title-section capitalize">{action}</h5><div className="mt-2 grid gap-2 sm:grid-cols-2">{action === "start" ? <><select aria-label="Printer" className={`desk-input ${focusRing}`} value={values.machine_id} onChange={(event) => setValues({ ...values, machine_id: event.target.value, consumable_pool_id: "" })}><option value="">Printer</option>{printers.map((printer) => <option key={printer.id} value={printer.id}>{printer.name}</option>)}</select><select aria-label="Pool" className={`desk-input ${focusRing}`} value={values.consumable_pool_id} onChange={(event) => setValues({ ...values, consumable_pool_id: event.target.value })}><option value="">Pool</option>{pools.map((pool) => <option key={pool.id} value={pool.id}>{pool.material} {pool.color}</option>)}</select>{input("estimated_minutes", "Estimated minutes")}{input("planned_quantity", "Planned grams")}</> : null}{action === "accept" ? <>{input("estimated_minutes", "Estimated minutes")}{input("planned_quantity", "Planned grams")}</> : null}{action === "complete" || action === "fail" ? <>{input("actual_minutes", "Actual minutes")}{input("actual_quantity", "Actual grams")}{action === "fail" ? <>{input("percent_complete", "Percent complete")}{input("reason", "Reason")}</> : null}</> : null}{action === "reject" ? input("reason", "Reason") : null}{action === "cancel" ? <><CancelNotice />{input("reason", "Reason (optional)")}</> : null}</div><div className="sticky bottom-0 -mx-3 -mb-3 mt-3 flex flex-wrap justify-end gap-2 rounded-b-md border-t border-line bg-bg p-3">{action === "cancel" ? <><button className="desk-button-danger" type="button" disabled={pending} onClick={onSubmit}>{pending ? "Cancelling…" : "Cancel job"}</button><button className="desk-button-ghost" type="button" onClick={onCancel}>Keep job</button></> : <><button className="desk-button-success" disabled={pending} onClick={onSubmit}>Confirm</button><button className="desk-button-ghost" onClick={onCancel}>Cancel</button></>}</div></div>;
}

function ManualUsageForm({ draft, setDraft, printers, pools, pending, onSubmit }: { draft: ServiceDraft; setDraft: Props["setDraft"]; printers: Machine[]; pools: PrinterPool[]; pending: boolean; onSubmit: () => void }) {
  const manual = draft.manual;
  const update = (patch: Partial<typeof manual>) => setDraft((current) => ({ ...current, manual: { ...current.manual, ...patch } }));
  return <div className="grid gap-2 sm:grid-cols-2"><select aria-label="Manual usage printer" className={`desk-input ${focusRing}`} value={manual.machine_id} onChange={(event) => update({ machine_id: event.target.value, consumable_pool_id: "" })}><option value="">Printer</option>{printers.map((machine) => <option value={machine.id} key={machine.id}>{machine.name}</option>)}</select><select aria-label="Manual usage pool" className={`desk-input ${focusRing}`} value={manual.consumable_pool_id} onChange={(event) => update({ consumable_pool_id: event.target.value })}><option value="">No pool</option>{pools.map((pool) => <option value={pool.id} key={pool.id}>{pool.material} {pool.color}</option>)}</select><input aria-label="Manual usage minutes" className={`desk-input ${focusRing}`} placeholder="Minutes" type="number" value={manual.duration_minutes} onChange={(event) => update({ duration_minutes: event.target.value })} /><input aria-label="Manual usage grams" className={`desk-input ${focusRing}`} placeholder="Grams" type="number" value={manual.quantity} onChange={(event) => update({ quantity: event.target.value })} /><select aria-label="Manual usage outcome" className={`desk-input ${focusRing}`} value={manual.outcome} onChange={(event) => update({ outcome: event.target.value })}><option value="success">Success</option><option value="failed">Failed</option></select>{manual.outcome === "failed" ? <><input aria-label="Percent complete" className={`desk-input ${focusRing}`} placeholder="Percent complete" type="number" value={manual.percent_complete} onChange={(event) => update({ percent_complete: event.target.value })} /><input aria-label="Failure reason" className={`desk-input ${focusRing}`} placeholder="Failure reason" value={manual.reason} onChange={(event) => update({ reason: event.target.value })} /></> : null}<input aria-label="Manual usage note" className={`desk-input ${focusRing}`} placeholder="Note" value={manual.note} onChange={(event) => update({ note: event.target.value })} /><button className="desk-button-primary sm:col-span-2 sm:justify-self-end" disabled={!manual.machine_id || !manual.duration_minutes || pending} onClick={onSubmit}>Log usage</button></div>;
}

function Subsection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section><h4 className="title-section mb-2">{title}</h4>{children}</section>;
}
