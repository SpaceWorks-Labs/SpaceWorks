import { formatLocale } from "../../../../lib/format";
import { t } from "@lingui/core/macro";
import { MaintenanceMeterFields } from "./MaintenanceMeterFields";
import { useState } from "react";

import { ConfirmDialog, EmptyState, ListRow, StatusPill } from "../../../../components/ui";
import {
  useCreateMaintenanceSchedule,
  useDeactivateMaintenanceSchedule,
  useUpdateMaintenanceSchedule,
  type MaintenanceSchedule,
  type ScheduleInput,
} from "./maintenanceApi";
import { BoxArt } from "../../../../components/BoxSpinner";

const emptySchedule = (): ScheduleInput => ({
  description: "",
  interval_days: 30,
  anchor: "completion",
  next_due: new Date().toISOString().slice(0, 10),
});

export function MaintenanceSchedules({
  makerspaceId, machineId, schedules, canEdit, retired, onComplete, metersEnabled = false,
}: {
  makerspaceId: number;
  metersEnabled?: boolean;
  machineId: number;
  schedules: MaintenanceSchedule[];
  canEdit: boolean;
  retired: boolean;
  onComplete: (schedule: MaintenanceSchedule) => void;
}) {
  const [draft, setDraft] = useState<ScheduleInput>(emptySchedule);
  const [editing, setEditing] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<ScheduleInput>(emptySchedule);
  const [deactivateId, setDeactivateId] = useState<number | null>(null);
  const create = useCreateMaintenanceSchedule(makerspaceId, machineId);
  const update = useUpdateMaintenanceSchedule(makerspaceId, machineId);
  const deactivate = useDeactivateMaintenanceSchedule(makerspaceId, machineId);
  const active = schedules.filter((row) => row.is_active);
  const inactive = schedules.filter((row) => !row.is_active);

  const fields = (
    value: ScheduleInput,
    change: (value: ScheduleInput) => void,
    prefix: string,
  ) => (
    <>
      <label className="eyebrow grid gap-1">
        {t`Description`}<input
          className="desk-input"
          aria-label={`${prefix} description`}
          value={value.description}
          onChange={(event) => change({ ...value, description: event.target.value })}
          required
        />
      </label>
      <label className="eyebrow grid gap-1">
        {t`Interval (days)`}<input
          className="desk-input"
          type="number"
          min={1}
          value={value.interval_days}
          onChange={(event) => change({ ...value, interval_days: Number(event.target.value) })}
          required
        />
      </label>
      {metersEnabled ? <MaintenanceMeterFields value={value} change={change} /> : null}
      <label className="eyebrow grid gap-1">
        {t`Recurrence anchor`}<select className="desk-input" value={value.anchor ?? "completion"} onChange={(event) => change({ ...value, anchor: event.target.value as ScheduleInput["anchor"] })}>
          <option value="completion">{t`From completion date`}</option>
          <option value="calendar">{t`Fixed calendar (skip missed dates)`}</option>
        </select>
      </label>
      <label className="eyebrow grid gap-1">
        {t`Next due`}<input
          className="desk-input"
          type="date"
          value={value.next_due}
          onChange={(event) => change({ ...value, next_due: event.target.value })}
          required
        />
      </label>
      <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-3">
        <input type="checkbox" checked={value.blocks_use ?? false} onChange={(event) => change({ ...value, blocks_use: event.target.checked })} />
        {t`Lock the machine out when overdue`}</label>
    </>
  );

  return (
    <section className="grid gap-3" aria-labelledby="maintenance-schedules-title">
      <h3 id="maintenance-schedules-title" className="title-section">
        {t`Maintenance schedules`}</h3>
      {!schedules.length ? (
        <EmptyState
          message={t`No maintenance schedules yet. Create the first recurring schedule.`}
        />
      ) : null}
      {[...active, ...inactive].map((schedule) => (
        <article key={schedule.id} className="grid gap-3">
          {editing === schedule.id ? (
            <form
              className="grid gap-2 sm:grid-cols-3"
              onSubmit={(event) => {
                event.preventDefault();
                update.mutate(
                  { id: schedule.id, input: editDraft },
                  { onSuccess: () => setEditing(null) },
                );
              }}
            >
              {fields(editDraft, setEditDraft, "Edit schedule")}
              <div className="flex flex-wrap gap-2 sm:col-span-3">
                <button className="desk-button-primary" type="submit" disabled={update.isPending}>
                  {update.isPending ? <><BoxArt size={16} mono />{t`Saving...`}</> : t`Save schedule`}
                </button>
                <button className="desk-button-ghost" type="button" onClick={() => setEditing(null)}>
                  {t`Cancel`}</button>
              </div>
            </form>
          ) : (
            <ListRow title={schedule.description} meta={<span>
                  {schedule.trigger !== "days" && schedule.trigger ? t`Usage: ${[schedule.usage_hours && `${schedule.usage_hours} hours`, schedule.job_count && `${schedule.job_count} jobs`].filter(Boolean).join(" or ")}. ` : ""}
                  {schedule.trigger !== "usage" ? (schedule.anchor === "calendar" ? t`Every ${schedule.interval_days} days (fixed calendar) · ${formatDate(schedule.next_due)}` : t`Every ${schedule.interval_days} days (from completion) · ${formatDate(schedule.next_due)}`) : t`Resets when maintenance is completed.`}
                  {schedule.blocks_use ? t` · Locks the machine when overdue` : ""}
                </span>}
              right={<div className="flex flex-wrap items-center gap-2"><StatusPill
                label={schedule.overdue ? t`Maintenance due` : schedule.is_active ? schedule.trigger === "usage" ? t`Within usage threshold` : t`Due as scheduled` : t`Inactive`}
                tone={schedule.overdue ? "danger" : schedule.is_active ? "accent" : "neutral"} />
              {canEdit && schedule.is_active && !retired ? (
                <div className="flex flex-wrap gap-2">
                  <button className="desk-button-success" type="button" onClick={() => onComplete(schedule)}>
                    {t`Complete`}</button>
                  <button
                    className="desk-button-ghost"
                    type="button"
                    onClick={() => {
                      setEditDraft({
                        description: schedule.description,
                        trigger: schedule.trigger, usage_hours: schedule.usage_hours, job_count: schedule.job_count,
                        interval_days: schedule.interval_days,
                        anchor: schedule.anchor ?? "completion",
                        next_due: schedule.next_due,
                        blocks_use: schedule.blocks_use ?? false,
                      });
                      setEditing(schedule.id);
                    }}
                  >
                    {t`Edit`}</button>
                  <button
                    className="desk-button-danger"
                    type="button"
                    disabled={deactivate.isPending}
                    onClick={() => setDeactivateId(schedule.id)}
                  >
                    {t`Deactivate`}</button>
                </div>
              ) : null}</div>} />
          )}
        </article>
      ))}
      {canEdit && !retired ? (
        <form
          className="grid gap-2 rounded-lg border border-line bg-surface p-3 sm:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate(draft, { onSuccess: () => setDraft(emptySchedule()) });
          }}
        >
          <h4 className="title-section sm:col-span-3">{t`New schedule`}</h4>
          {fields(draft, setDraft, "New schedule")}
          <button className="desk-button-primary sm:col-span-3 sm:w-fit" type="submit" disabled={create.isPending}>
            {create.isPending ? <><BoxArt size={16} mono />{t`Creating...`}</> : t`Create schedule`}
          </button>
        </form>
      ) : null}
      {[create.error, update.error, deactivate.error].map((error, index) =>
        error instanceof Error ? <p key={index} className="text-sm text-danger">{error.message}</p> : null,
      )}
      <ConfirmDialog
        open={deactivateId !== null}
        title={t`Deactivate maintenance schedule?`}
        message={t`Deactivate this maintenance schedule?`}
        confirmLabel={t`Deactivate schedule`}
        tone="danger"
        pending={deactivate.isPending}
        onConfirm={() => {
          if (deactivateId !== null) {
            deactivate.mutate(deactivateId, { onSuccess: () => setDeactivateId(null) });
          }
        }}
        onCancel={() => setDeactivateId(null)}
      />
    </section>
  );
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(formatLocale());
}
