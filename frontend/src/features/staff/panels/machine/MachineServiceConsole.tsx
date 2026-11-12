import { t } from "@lingui/core/macro";
import { UsageAttributionFields } from "./UsageAttributionFields";
import { machineStatusLabel } from "./machineStatusLabel";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { MachineServiceRequest, PrinterPool, TypedManualUsageResponse } from "../../../../generated/api";
import { ErrorBlock, ListRow, StatusBadge, OverflowMenu, Modal, EmptyState } from "../../../../components/ui";
import { ServiceConsoleSections, ServiceQueueTabs } from "./ServiceConsoleSections";
import { staffRequest } from "../../../../lib/api";
import { machineKeys } from "../../machinesApi";
import { CancelNotice, ServiceEtaLine } from "./ServiceEtaLine";
import type { Machine, MachineType, MeteringUnit } from "../../machinesApi";
import { useStaffGet } from "../shared";
import { clearedActionDraft } from "./serviceDrafts";
import { cancelBody, openAction } from "./cancelEstimate";
import type { ServiceActionName, ServiceDraft } from "./serviceDrafts";
import { poolQueryKey, poolUnits, unitLabels, usablePools } from "./servicePools";
import { LogoLoader } from "../../../../components/LogoLoader";

type Props = {
  visible?: boolean;
  makerspaceId: number;
  canManage: boolean;
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

export function MachineServiceConsole({ makerspaceId, canManage, machineType, machines, pools, draft, setDraft, visible = true, queueStatus, logging: liftedLogging, onLogging: setLiftedLogging }: Props) {
  const [ownLogging, setOwnLogging] = useState(false);
  const logging = liftedLogging ?? ownLogging;
  const setLogging = setLiftedLogging ?? setOwnLogging;
  const queryClient = useQueryClient();
  const meteringUnit = (machineType.capability_config?.metering_unit ?? "count") as MeteringUnit;
  const unitLabel = unitLabels[meteringUnit];
  const poolUnit = poolUnits[meteringUnit];
  // Filter by the stable machine-type ID, not the slug: slugs are not unique across the
  // global/tenant split, so a makerspace-local type sharing a built-in's slug would pull in
  // the other type's jobs and let a manager mutate them from the wrong section.
  const machineTypeFilter = `machine_type_id=${machineType.id}`;
  const requests = useStaffGet<MachineServiceRequest[]>(
    ["machine-service-requests", makerspaceId, machineType.id],
    `/admin/makerspaces/${makerspaceId}/machine-service/requests?${machineTypeFilter}`,
    canManage,
  );
  const manualUsage = useStaffGet<TypedManualUsageResponse[]>(
    ["machine-service-manual", makerspaceId, machineType.id],
    `/admin/makerspaces/${makerspaceId}/machine-service/typed-manual-usage?${machineTypeFilter}`,
    canManage,
  );
  const actionPools = usablePools(pools, poolUnit, draft.actionValues.machine_id, machines, makerspaceId);
  const manualPools = usablePools(pools, poolUnit, draft.manual.machine_id, machines, makerspaceId);

  const invalidate = () => void Promise.all([
    queryClient.invalidateQueries({ queryKey: ["machine-service-requests", makerspaceId, machineType.id] }),
    queryClient.invalidateQueries({ queryKey: ["machine-service-manual", makerspaceId, machineType.id] }),
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
        member: draft.manual.member ? Number(draft.manual.member) : undefined,
        started_at: draft.manual.started_at ? new Date(draft.manual.started_at).toISOString() : undefined,
        consumable_pool_id: poolUnit && draft.manual.consumable_pool_id ? Number(draft.manual.consumable_pool_id) : null,
        duration_minutes: Number(draft.manual.duration_minutes),
        quantity: poolUnit && draft.manual.quantity ? draft.manual.quantity : undefined,
        metering_unit: meteringUnit,
        outcome: draft.manual.outcome,
        percent_complete: Number(draft.manual.percent_complete),
        reason: draft.manual.reason || undefined,
        note: draft.manual.note || undefined,
      }),
    }),
    onSuccess: () => {
      setDraft((current) => ({ ...current, manual: { ...current.manual, member: "", started_at: "", machine_id: "", consumable_pool_id: "", duration_minutes: "", quantity: "", outcome: "success", percent_complete: "100", reason: "", note: "" } }));
      setLogging(false);
      invalidate();
    },
  });
  const runAction = useMutation({
    mutationFn: () => {
      if (!draft.action) throw new Error(t`Choose an action.`);
      return staffRequest(`/admin/machine-service/requests/${draft.action.id}/${draft.action.name}`, {
        method: "POST",
        body: JSON.stringify(actionBody(draft.action.name, draft.actionValues, !!poolUnit)),
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
      <ServiceConsoleSections queue={<Subsection title={t`Service queue`}>
        <p className="mb-3 text-sm text-muted">
          {t`This type is metered in ${unitLabel}. `}{poolUnit ? t`Choose a machine before selecting its consumable pool.` : t`Minutes-based services do not use consumable pools.`}
        </p>
        <ServiceQueueTabs rows={requests.data} initialStatus={queueStatus}>{visible => <div className="grid gap-3">
          {visible?.map((request) => (
            <ListRow key={request.id} title={request.title} identity={{ kind: "avatar", name: request.requester_name || "Member", seed: String(request.id) }}
                meta={<> {t`${request.requester_name} · Planned ${request.planned_quantity ?? "0"} ${unitLabel} · actual ${request.actual_consumed_quantity ?? "0"} ${unitLabel}`}<ServiceEtaLine request={request} /></>}
                right={<div className="flex flex-wrap items-center gap-2"><StatusBadge status={request.status} label={machineStatusLabel(request.status)} /><ServiceActions request={request} onAction={name => setDraft(current => openAction(current, request, name))} /></div>} />
          )) ?? <LogoLoader label={t`Loading service queue...`} size={48} className="min-h-16 py-3" />}
        </div>}</ServiceQueueTabs>
        {draft.action ? (
          <Modal open title={`${draft.action.name} job`} onClose={() => setDraft(current => ({ ...current, action: null }))}><ServiceActionForm
            action={draft.action.name}
            values={draft.actionValues}
            setValues={(actionValues) => setDraft((current) => ({ ...current, actionValues }))}
            machines={machines}
            pools={actionPools}
            unitLabel={unitLabel}
            hasPool={!!poolUnit}
            pending={runAction.isPending}
            onSubmit={() => runAction.mutate()}
            onCancel={() => setDraft((current) => ({ ...current, action: null }))}
          /><ErrorBlock error={runAction.error} /></Modal>
        ) : null}
      </Subsection>} manualForm={<ManualUsageForm draft={draft} setDraft={setDraft} machines={machines} pools={manualPools} unitLabel={unitLabel} hasPool={!!poolUnit} pending={submitManual.isPending} onSubmit={() => submitManual.mutate()} />} manualRows={<div className="mt-3 grid gap-2">
          {manualUsage.data?.length === 0 ? <EmptyState message={t`No manual usage logged yet. Log the first entry.`} /> : null}{manualUsage.data?.map(entry => <ListRow key={entry.id} title={`${entry.duration_minutes} min`} meta={<>{entry.consumed_quantity} {unitLabel}{entry.outcome === "failed" ? ` · ${entry.percent_complete}%` : ""}</>} right={<StatusBadge status={entry.outcome} label={machineStatusLabel(entry.outcome)} />} />)}</div>} reports={undefined} logging={logging} onLogging={setLogging} />
      <ErrorBlock error={[requests.error, manualUsage.error, submitManual.error, runAction.error].find((item) => item instanceof Error)} />
    </div>
  );
}

function actionBody(action: ServiceActionName, values: ServiceDraft["actionValues"], hasPool: boolean) {
  if (action === "accept") return { estimated_minutes: Number(values.estimated_minutes) };
  if (action === "start") return { machine_id: values.machine_id ? Number(values.machine_id) : null, consumable_pool_id: hasPool && values.consumable_pool_id ? Number(values.consumable_pool_id) : undefined, estimated_minutes: Number(values.estimated_minutes), planned_quantity: hasPool && values.planned_quantity ? values.planned_quantity : undefined };
  if (action === "complete") return { actual_minutes: Number(values.actual_minutes), actual_quantity: hasPool && values.actual_quantity ? values.actual_quantity : undefined };
  if (action === "fail") return { actual_minutes: Number(values.actual_minutes), actual_quantity: hasPool && values.actual_quantity ? values.actual_quantity : undefined, percent_complete: Number(values.percent_complete), reason: values.reason };
  if (action === "cancel") return cancelBody(values);
  return action === "reject" ? { reason: values.reason } : {};
}

function ServiceActions({ request, onAction }: { request: MachineServiceRequest; onAction: (name: ServiceActionName) => void }) {
  const cancel = { label: t`Cancel job`, tone: "danger" as const, onClick: () => onAction("cancel") };
  if (request.status === "pending") return <><button className="desk-button-success" onClick={() => onAction("accept")}>{t`Accept`}</button><OverflowMenu actions={[{ label: t`Reject`, tone: "danger", onClick: () => onAction("reject") }, cancel]} /></>;
  if (request.status === "accepted") return <><button className="desk-button-primary" onClick={() => onAction("start")}>{t`Start`}</button><OverflowMenu actions={[cancel]} /></>;
  if (request.status === "in_progress") return <><button className="desk-button-success" onClick={() => onAction("complete")}>{t`Complete`}</button><OverflowMenu actions={[{ label: t`Fail`, tone: "danger", onClick: () => onAction("fail") }, cancel]} /></>;
  return request.status === "completed" ? <button className="desk-button-success" onClick={() => onAction("collect")}>{t`Collect`}</button> : null;
}

function ServiceActionForm({ action, values, setValues, machines, pools, unitLabel, hasPool, pending, onSubmit, onCancel }: { action: ServiceActionName; values: ServiceDraft["actionValues"]; setValues: (values: ServiceDraft["actionValues"]) => void; machines: Machine[]; pools: PrinterPool[]; unitLabel: string; hasPool: boolean; pending: boolean; onSubmit: () => void; onCancel: () => void }) {
  const input = (key: keyof typeof values, label: string) => <label className="eyebrow grid gap-1">{label}<input className={`desk-input ${focusRing}`} inputMode={key === "reason" ? undefined : "decimal"} value={values[key]} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></label>;
  const chooseMachine = (machine_id: string) => setValues({ ...values, machine_id, consumable_pool_id: "" });
  return <div className="mt-3 rounded-md border border-accent bg-bg p-3"><h5 className="title-section capitalize">{action}</h5><div className="mt-2 grid gap-2 sm:grid-cols-2">{action === "accept" ? input("estimated_minutes", "Estimated minutes") : null}{action === "start" ? <><select aria-label={t`Machine`} className={`desk-input ${focusRing}`} value={values.machine_id} onChange={(event) => chooseMachine(event.target.value)}><option value="">{t`Machine`}</option>{machines.map((machine) => <option key={machine.id} value={machine.id}>{machine.name}</option>)}</select>{hasPool ? <select aria-label={t`Pool`} className={`desk-input ${focusRing}`} value={values.consumable_pool_id} onChange={(event) => setValues({ ...values, consumable_pool_id: event.target.value })}><option value="">{t`Pool`}</option>{pools.map((pool) => <option key={pool.id} value={pool.id}>{pool.material} {pool.color}</option>)}</select> : null}{input("estimated_minutes", "Estimated minutes")}{hasPool ? input("planned_quantity", `Planned ${unitLabel}`) : null}</> : null}{action === "complete" || action === "fail" ? <>{input("actual_minutes", "Actual minutes")}{hasPool ? input("actual_quantity", `Actual ${unitLabel}`) : null}{action === "fail" ? <>{input("percent_complete", "Percent complete")}{input("reason", "Reason")}</> : null}</> : null}{action === "reject" ? input("reason", "Reason") : null}{action === "cancel" ? <><CancelNotice />{values.cancel_hold ? input("consumed_quantity", `Material used so far (${unitLabel}, 0 to ${values.cancel_hold})`) : null}{input("reason", "Reason (optional)")}</> : null}</div><div className="sticky bottom-0 -mx-3 -mb-3 mt-3 flex flex-wrap justify-end gap-2 rounded-b-md border-t border-line bg-bg p-3">{action === "cancel" ? <><button className="desk-button-danger" type="button" disabled={pending} onClick={onSubmit}>{pending ? t`Cancelling…` : t`Cancel job`}</button><button className="desk-button-ghost" type="button" onClick={onCancel}>{t`Keep job`}</button></> : <><button className="desk-button-success" disabled={pending} onClick={onSubmit}>{t`Confirm`}</button><button className="desk-button-ghost" onClick={onCancel}>{t`Cancel`}</button></>}</div></div>;
}

function ManualUsageForm({ draft, setDraft, machines, pools, unitLabel, hasPool, pending, onSubmit }: { draft: ServiceDraft; setDraft: Props["setDraft"]; machines: Machine[]; pools: PrinterPool[]; unitLabel: string; hasPool: boolean; pending: boolean; onSubmit: () => void }) {
  const manual = draft.manual;
  const update = (patch: Partial<typeof manual>) => setDraft((current) => ({ ...current, manual: { ...current.manual, ...patch } }));
  return <div className="grid gap-2 sm:grid-cols-2"><select aria-label={t`Manual usage machine`} className={`desk-input ${focusRing}`} value={manual.machine_id} onChange={(event) => update({ machine_id: event.target.value, consumable_pool_id: "" })}><option value="">{t`Machine`}</option>{machines.map((machine) => <option key={machine.id} value={machine.id}>{machine.name}</option>)}</select>{hasPool ? <select aria-label={t`Manual usage pool`} className={`desk-input ${focusRing}`} value={manual.consumable_pool_id} onChange={(event) => update({ consumable_pool_id: event.target.value })}><option value="">{t`No pool`}</option>{pools.map((pool) => <option key={pool.id} value={pool.id}>{pool.material} {pool.color}</option>)}</select> : null}<input aria-label={t`Manual usage minutes`} className={`desk-input ${focusRing}`} type="number" min="0" placeholder={t`Minutes`} value={manual.duration_minutes} onChange={(event) => update({ duration_minutes: event.target.value })} />{hasPool ? <input aria-label={t`Manual usage ${unitLabel}`} className={`desk-input ${focusRing}`} type="number" min="0" placeholder={unitLabel} value={manual.quantity} onChange={(event) => update({ quantity: event.target.value })} /> : null}<select aria-label={t`Manual usage outcome`} className={`desk-input ${focusRing}`} value={manual.outcome} onChange={(event) => update({ outcome: event.target.value })}><option value="success">{t`Success`}</option><option value="failed">{t`Failed`}</option></select>{manual.outcome === "failed" ? <input aria-label={t`Failure reason`} className={`desk-input ${focusRing}`} placeholder={t`Failure reason`} value={manual.reason} onChange={(event) => update({ reason: event.target.value })} /> : null}<UsageAttributionFields machineId={Number(manual.machine_id)} member={manual.member ?? ""} startedAt={manual.started_at ?? ""} onChange={update} /><input aria-label={t`Manual usage note`} className={`desk-input ${focusRing}`} placeholder={t`Note`} value={manual.note} onChange={(event) => update({ note: event.target.value })} /><button className="desk-button-primary sm:col-span-2 sm:justify-self-end" disabled={!manual.machine_id || !manual.duration_minutes || pending} onClick={onSubmit}>{t`Log usage`}</button></div>;
}

function Subsection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section><h4 className="title-section mb-2">{title}</h4>{children}</section>;
}
