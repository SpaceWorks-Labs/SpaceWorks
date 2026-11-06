import { t } from "@lingui/core/macro";
import { MaintenanceFeedControl } from "./MaintenanceFeedControl";
import { useState } from "react";

import { EmptyState, Skeleton, ErrorBlock, ListRow, RelativeTime } from "../../../../components/ui";
import { MaintenanceDocuments } from "./MaintenanceDocuments";
import { MaintenanceSchedules } from "./MaintenanceSchedules";
import { DowntimePanel, LockoutNotice } from "./DowntimePanel";
import { MachineWorkOrders } from "./workOrders/MachineWorkOrders";
import {
  useLogMaintenance,
  useMaintenanceLogs,
  useMaintenanceSchedules,
  type LogInput,
  type MaintenanceSchedule,
} from "./maintenanceApi";
import { costBody, EMPTY_COST, MaintenanceCostInput, type CostValue } from "./MaintenanceCostInput";

type MaintenanceTabProps = {
  metersEnabled?: boolean;
  feedEnabled?: boolean;
  makerspaceId: number;
  machineId: number;
  canEdit: boolean;
  canOperate: boolean;
  enabled: boolean;
  retired: boolean;
};

export function MaintenanceTab({
  makerspaceId, machineId, canEdit, canOperate, enabled, retired, metersEnabled = false, feedEnabled = false,
}: MaintenanceTabProps) {
  const [completing, setCompleting] = useState<MaintenanceSchedule | null>(null);
  const schedules = useMaintenanceSchedules(makerspaceId, machineId, enabled);
  const logs = useMaintenanceLogs(makerspaceId, machineId, enabled);

  if (schedules.isLoading || logs.isLoading) {
    return (
      <div className="grid gap-3" aria-label={t`Loading maintenance details`}>
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const queryError = schedules.error ?? logs.error;
  if (queryError instanceof Error) {
    return <ErrorBlock error={queryError} resource="maintenance" onRetry={() => { void schedules.refetch(); void logs.refetch(); }} />;
  }

  const scheduleRows = schedules.data?.results ?? [];
  const logRows = logs.data?.results ?? [];

  return (
    <div className="grid gap-5">
      <LockoutNotice machineId={machineId} />
      {feedEnabled ? <MaintenanceFeedControl makerspaceId={makerspaceId} /> : null}
      <MachineWorkOrders makerspaceId={makerspaceId} machineId={machineId} canCreate={canOperate && !retired} />
      <DowntimePanel machineId={machineId} canEdit={canEdit} />
      <MaintenanceSchedules
        metersEnabled={metersEnabled}
        makerspaceId={makerspaceId}
        machineId={machineId}
        schedules={scheduleRows}
        canEdit={canEdit}
        retired={retired}
        onComplete={setCompleting}
      />
      {completing ? (
        <ScheduleCompletionForm
          key={completing.id}
          makerspaceId={makerspaceId}
          machineId={machineId}
          schedule={completing}
          onCancel={() => setCompleting(null)}
          onCompleted={() => setCompleting(null)}
        />
      ) : null}
      {canOperate && !retired ? (
        <MaintenanceLogForm makerspaceId={makerspaceId} machineId={machineId} />
      ) : null}
      <section className="grid gap-3" aria-labelledby="maintenance-history-title">
        <h3 id="maintenance-history-title" className="title-section">
          {t`Maintenance history`}</h3>
        {!logRows.length ? (
          <EmptyState
            message={t`No maintenance logged. Record the first completed maintenance.`}
          />
        ) : null}
        {logRows.map((log) => (
          <details key={log.id} className="grid gap-3">
            <summary className="flex min-h-11 cursor-pointer list-none flex-col justify-center text-sm marker:hidden focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
              <ListRow title={log.summary} meta={log.cost ? `Cost: ${log.cost}` : undefined} right={<RelativeTime date={log.performed_at} exact />} />
            </summary>
            <div className="mt-3 border-t border-line pt-3 text-sm text-muted">
              {log.parts_note ? (
                <p className="whitespace-pre-wrap break-words">{log.parts_note}</p>
              ) : <p>{t`No parts notes.`}</p>}
              <MaintenanceDocuments
                machineId={machineId}
                logId={log.id}
                documents={log.documents}
                canDelete={canEdit}
                retired={retired}
              />
            </div>
          </details>
        ))}
      </section>
    </div>
  );
}

function ScheduleCompletionForm({ makerspaceId, machineId, schedule, onCancel, onCompleted }: {
  makerspaceId: number;
  machineId: number;
  schedule: MaintenanceSchedule;
  onCancel: () => void;
  onCompleted: () => void;
}) {
  const [summary, setSummary] = useState(schedule.description);
  const [performedAt, setPerformedAt] = useState("");
  const [cost, setCost] = useState<CostValue>(EMPTY_COST);
  const [partsNote, setPartsNote] = useState("");
  const [setIdle, setSetIdle] = useState(false);
  const complete = useLogMaintenance(makerspaceId, machineId);

  return (
    <section aria-labelledby={`complete-maintenance-${schedule.id}`}>
      <h3 id={`complete-maintenance-${schedule.id}`} className="title-section mb-3">
        {t`Complete scheduled maintenance`}</h3>
      <form
        className="grid gap-2 rounded-lg border border-line bg-surface p-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          complete.mutate({
            summary: summary.trim(),
            performed_at: performedAt ? new Date(performedAt).toISOString() : undefined,
            ...costBody(cost),
            parts_note: partsNote.trim(),
            set_idle: setIdle,
            schedule_id: schedule.id,
          }, { onSuccess: onCompleted });
        }}
      >
        <label className="eyebrow grid gap-1 sm:col-span-2">
          {t`Summary`}<input className="desk-input" value={summary}
            onChange={(event) => setSummary(event.target.value)} required />
        </label>
        <label className="eyebrow grid gap-1">
          {t`Performed at (optional)`}<input className="desk-input w-full min-w-0" type="datetime-local" value={performedAt}
            onChange={(event) => setPerformedAt(event.target.value)} />
        </label>
        <MaintenanceCostInput value={cost} onChange={setCost} />
        <label className="eyebrow grid gap-1 sm:col-span-2">
          {t`Parts and notes (optional)`}<textarea className="desk-input min-h-20" value={partsNote}
            onChange={(event) => setPartsNote(event.target.value)} />
        </label>
        <label className="eyebrow flex min-h-11 items-center gap-2 sm:col-span-2">
          <input type="checkbox" checked={setIdle}
            onChange={(event) => setSetIdle(event.target.checked)} />
          {t`Set machine status to idle`}</label>
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <button className="desk-button-primary" type="submit"
            disabled={complete.isPending || !summary.trim()}>
            {complete.isPending ? t`Completing...` : t`Complete maintenance`}
          </button>
          <button className="desk-button-ghost" type="button" onClick={onCancel} disabled={complete.isPending}>
            {t`Cancel`}</button>
        </div>
      </form>
      {complete.error instanceof Error ? (
        <p className="mt-2 text-sm text-danger" role="alert">{complete.error.message}</p>
      ) : null}
    </section>
  );
}

function MaintenanceLogForm({ makerspaceId, machineId }: {
  makerspaceId: number;
  machineId: number;
}) {
  const [summary, setSummary] = useState("");
  const [performedAt, setPerformedAt] = useState("");
  const [cost, setCost] = useState<CostValue>(EMPTY_COST);
  const [partsNote, setPartsNote] = useState("");
  const [setIdle, setSetIdle] = useState(false);
  const log = useLogMaintenance(makerspaceId, machineId);

  const reset = () => {
    setSummary("");
    setPerformedAt("");
    setCost(EMPTY_COST);
    setPartsNote("");
    setSetIdle(false);
  };

  return (
    <section aria-labelledby="log-maintenance-title">
      <h3 id="log-maintenance-title" className="title-section mb-3">
        {t`Log maintenance`}</h3>
      <form
        className="grid gap-2 rounded-lg border border-line bg-surface p-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          const input: LogInput = {
            summary: summary.trim(),
            performed_at: performedAt ? new Date(performedAt).toISOString() : undefined,
            ...costBody(cost),
            parts_note: partsNote.trim(),
            set_idle: setIdle,
          };
          log.mutate(input, { onSuccess: reset });
        }}
      >
        <label className="eyebrow grid gap-1 sm:col-span-2">
          {t`Summary`}<input className="desk-input" value={summary}
            onChange={(event) => setSummary(event.target.value)} required />
        </label>
        <label className="eyebrow grid gap-1">
          {t`Performed at (optional)`}<input className="desk-input w-full min-w-0" type="datetime-local" value={performedAt}
            onChange={(event) => setPerformedAt(event.target.value)} />
        </label>
        <MaintenanceCostInput value={cost} onChange={setCost} />
        <label className="eyebrow grid gap-1 sm:col-span-2">
          {t`Parts and notes (optional)`}<textarea className="desk-input min-h-20" value={partsNote}
            onChange={(event) => setPartsNote(event.target.value)} />
        </label>
        <label className="eyebrow flex min-h-11 items-center gap-2 sm:col-span-2">
          <input type="checkbox" checked={setIdle}
            onChange={(event) => setSetIdle(event.target.checked)} />
          {t`Set machine status to idle`}</label>
        <button className="desk-button-primary justify-self-start" type="submit"
          disabled={log.isPending || !summary.trim()}>
          {log.isPending ? t`Logging...` : t`Log maintenance`}
        </button>
      </form>
      {log.error instanceof Error ? (
        <p className="mt-2 text-sm text-danger" role="alert">{log.error.message}</p>
      ) : null}
    </section>
  );
}
