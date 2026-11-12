import { plural, t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";

import type { PrinterPool } from "../../../../generated/api";
import { ConfirmDialog, EmptyState, ErrorBlock, StatusPill } from "../../../../components/ui";
import { isBuiltinPrinterType, type Machine, type MachineType, type MeteringUnit } from "../../machinesApi";
import { BatchCompleteDialog, BatchStartDialog } from "./BatchDialogs";
import { reorderPosition } from "./boardOrder";
import { useQueueDrag } from "./boardDrag";
import { JobActionDialog } from "./JobActionDialog";
import { JobConsumablesDialog } from "./JobConsumablesDialog";
import { JobFilesDialog } from "./filePreview/JobFilesDialog";
import { JobBoardCard, type CardHandlers } from "./JobBoardCard";
import type { DialogAction } from "./jobActionBody";
import { machineStatusLabel } from "./machineStatusLabel";
import { useJobAction, useJobBoard, useJobInvalidation, type StaffJob } from "./machineJobsApi";
import { poolUnits, unitLabels, usablePools } from "./servicePools";
import { LogoLoader } from "../../../../components/LogoLoader";

type Props = {
  makerspaceId: number; machineType: MachineType; machines: Machine[]; pools: PrinterPool[];
  batchEnabled: boolean; visible?: boolean;
};

/** The per-type queue board (#141): machine lanes, the ordered queue, review, waiting on member and ready to collect. */
export function JobBoard({ makerspaceId, machineType, machines, pools, batchEnabled, visible = true }: Props) {
  const board = useJobBoard(makerspaceId, machineType.id, visible);
  const direct = useJobAction(makerspaceId, machineType.id);
  const refresh = useJobInvalidation(makerspaceId, machineType.id);
  const [dialog, setDialog] = useState<{ job: StaffJob; action: DialogAction } | null>(null);
  const [uncollected, setUncollected] = useState<StaffJob | null>(null);
  const [filesOf, setFilesOf] = useState<StaffJob | null>(null);
  const [consumablesOf, setConsumablesOf] = useState<StaffJob | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [batching, setBatching] = useState(false);
  const [completing, setCompleting] = useState<{ batchId: number; jobs: StaffJob[] } | null>(null);
  const drag = useQueueDrag(board.data, (job, position) => direct.mutate({ id: job.id, action: "reorder", body: { position } }));
  if (!visible) return null;
  const printer = isBuiltinPrinterType(machineType);
  const metering = (machineType.capability_config?.metering_unit ?? "count") as MeteringUnit;
  const poolUnit = printer ? "grams" : poolUnits[metering];
  const unitLabel = printer ? "grams" : unitLabels[metering];
  const poolsFor = (machineId: string) => usablePools(pools, poolUnit, machineId, machines, makerspaceId);
  const handlers: CardHandlers = {
    onDialog: (job, action) => setDialog({ job, action }),
    onDirect: (job, action, body) => direct.mutate({ id: job.id, action, body }),
    onUncollected: setUncollected,
    onFiles: setFilesOf,
    onConsumables: setConsumablesOf,
  };
  if (board.isLoading) return <LogoLoader label={t`Loading queue board`} size={48} className="min-h-24 py-3" />;
  if (board.error) return <ErrorBlock error={board.error} resource={t`queue board`} onRetry={() => { void board.refetch(); }} />;
  const data = board.data;
  if (!data) return null;
  const overdue = new Set(data.overdue_pickup_ids);
  const noShows = new Set(data.no_show_member_ids);
  const card = (job: StaffJob, column?: StaffJob[]) => <JobBoardCard key={job.id} job={job} {...handlers} pending={direct.isPending}
    overdue={overdue.has(job.id)} noShow={!!job.requester?.id && noShows.has(job.requester.id)}
    move={column ? { up: reorderPosition(job, "up", column, data), down: reorderPosition(job, "down", column, data) } : undefined}
    drag={column && !direct.isPending ? drag.dragFor(job, column) : undefined}
    select={batchEnabled && job.status === "accepted" ? { checked: selected.includes(job.id),
      onChange: checked => setSelected(current => checked ? [...current, job.id] : current.filter(id => id !== job.id)) } : undefined} />;
  const waiting = [...data.queue, ...data.lanes.flatMap(lane => lane.assigned)];
  // The open files dialog follows the live board, so a file staff just added shows up.
  const everyJob = [...waiting, ...data.lanes.flatMap(lane => lane.running), ...data.review, ...data.waiting_on_member, ...data.ready];
  const filesJob = filesOf ? everyJob.find(job => job.id === filesOf.id) ?? filesOf : null;
  const chosen = waiting.filter(job => selected.includes(job.id));
  return <div className="grid gap-6">
    {direct.error ? <ErrorBlock error={direct.error} /> : null}
    <p aria-live="polite" className="sr-only">{drag.announcement}</p>
    {batchEnabled ? <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-3 text-sm">
      <span>{chosen.length ? plural(chosen.length, { one: "# queued job selected.", other: "# queued jobs selected." }) : t`Select two or more queued jobs to run them together.`}</span>
      <button type="button" className="desk-button-primary" disabled={chosen.length < 2} onClick={() => setBatching(true)}>{t`Start as batch`}</button>
      {chosen.length ? <button type="button" className="desk-button-ghost" onClick={() => setSelected([])}>{t`Clear selection`}</button> : null}
    </div> : null}
    <Column title={t`Machines`} count={data.lanes.length} empty={t`No active machines of this type in your scope.`}>
      {data.lanes.map(lane => <li key={lane.machine_id} className="grid gap-3 rounded-2xl border border-line bg-surface p-3">
        <div className="flex flex-wrap items-center gap-2"><h4 className="title-section">{lane.machine_name}</h4>
          <StatusPill tone={lane.status === "idle" ? "success" : lane.status === "running" ? "accent" : "neutral"} label={machineStatusLabel(lane.status)} />
          {lane.locked_out ? <StatusPill tone="danger" label={t`Locked out: maintenance overdue`} /> : null}</div>
        <BatchButtons jobs={lane.running} onComplete={setCompleting} />
        <ul className="grid gap-2" aria-label={`${lane.machine_name} jobs`}>{lane.running.map(job => card(job))}{lane.assigned.map(job => card(job))}</ul>
        {!lane.running.length && !lane.assigned.length ? <p className="text-sm text-muted">{t`Nothing running or assigned.`}</p> : null}
      </li>)}
    </Column>
    <div className="grid gap-6 lg:grid-cols-2">
      <Column title={t`Queue`} count={data.queue.length} empty={t`No accepted jobs waiting for a machine.`}
        hint={data.queue.length > 1 ? t`Drag a job to reorder the queue, or use its move buttons.` : undefined}>{data.queue.map(job => card(job, data.queue))}</Column>
      <Column title={t`To review`} count={data.review.length} empty={t`No new requests to review.`}>{data.review.map(job => card(job))}</Column>
      <Column title={t`Waiting on member`} count={data.waiting_on_member.length} empty={t`No jobs waiting for changes or a quote decision.`}>{data.waiting_on_member.map(job => card(job))}</Column>
      <Column title={t`Ready to collect`} count={data.ready.length} empty={t`Nothing waiting for pickup.`}>{data.ready.map(job => card(job))}</Column>
    </div>
    {consumablesOf ? <JobConsumablesDialog job={consumablesOf} makerspaceId={makerspaceId} onClose={() => setConsumablesOf(null)} /> : null}
    {dialog ? <JobActionDialog key={`${dialog.job.id}-${dialog.action}`} job={dialog.job} action={dialog.action} makerspaceId={makerspaceId} typeId={machineType.id}
      machines={machines} pools={poolsFor} unitLabel={unitLabel} hasPool={!!poolUnit} printer={printer} onClose={() => setDialog(null)} /> : null}
    {batching ? <BatchStartDialog jobs={chosen} makerspaceId={makerspaceId} typeId={machineType.id} machines={machines} pools={poolsFor}
      unitLabel={unitLabel} hasPool={!!poolUnit} printer={printer} onClose={done => { setBatching(false); if (done) setSelected([]); }} /> : null}
    {completing ? <BatchCompleteDialog batchId={completing.batchId} jobs={completing.jobs} makerspaceId={makerspaceId} typeId={machineType.id}
      unitLabel={unitLabel} hasPool={!!poolUnit} onClose={() => setCompleting(null)} /> : null}
    {filesJob ? <JobFilesDialog title={filesJob.title} files={filesJob.files ?? []} onClose={() => setFilesOf(null)}
      upload={{ requestId: filesJob.id, onUploaded: () => { void refresh(); } }} /> : null}
    <ConfirmDialog open={uncollected !== null} title={t`Mark not collected?`} tone="danger" confirmLabel={t`Mark not collected`} pending={direct.isPending}
      message={t`The member did not pick this job up within 14 days. It leaves the pickup shelf and the member is told.`}
      onCancel={() => setUncollected(null)} onConfirm={() => { if (uncollected) direct.mutate({ id: uncollected.id, action: "uncollected" }, { onSuccess: () => setUncollected(null) }); }} />
  </div>;
}

function Column({ title, count, empty, hint, children }: { title: string; count: number; empty: string; hint?: string; children: ReactNode }) {
  const id = `board-${title.toLowerCase().replace(/\s+/g, "-")}`;
  return <section aria-labelledby={id} className="grid content-start gap-3">
    <h3 id={id} className="title-panel">{title} <span className="text-sm font-normal text-muted">({count})</span></h3>
    {hint ? <p className="text-sm text-muted">{hint}</p> : null}
    {count ? <ul className="grid gap-3">{children}</ul> : <EmptyState message={empty} />}
  </section>;
}

function BatchButtons({ jobs, onComplete }: { jobs: StaffJob[]; onComplete: (batch: { batchId: number; jobs: StaffJob[] }) => void }) {
  const batches = [...new Set(jobs.map(job => job.batch_id).filter((id): id is number => !!id))];
  return batches.length ? <div className="flex flex-wrap gap-2">{batches.map(batchId => <button key={batchId} type="button" className="desk-button-success"
    onClick={() => onComplete({ batchId, jobs: jobs.filter(job => job.batch_id === batchId) })}>{t`Complete batch ${batchId}`}</button>)}</div> : null;
}

