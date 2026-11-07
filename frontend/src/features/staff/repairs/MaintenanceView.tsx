import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import type { Makerspace } from "../panels/shared";
import { opsQueryState } from "../opsPresentation";
import { StepDialog } from "./StepDialog";
import { useSubjectOptions } from "./subjectsApi";
import { COST_METHODS } from "../panels/machine/MaintenanceCostInput";

type Schedule = { id: number; subject_type: string; subject_id: number; subject_label: string; description: string;
  interval_days: number; next_due: string; is_active: boolean };
type MachineDue = { id: number; machine_id: number; machine_name: string; description: string; next_due: string };
type Due = { kind: "machine" | "item"; id: number; label: string; description: string; next_due: string };

const today = () => new Date().toISOString().slice(0, 10);

/**
 * Maintenance under each parent (#128 C-9): item and room schedules for their managers, and
 * for a Technician every schedule due in their coverage -- machines included -- to run and log.
 */
export function MaintenanceView({ makerspace, manager }: { makerspace: Makerspace; manager: boolean }) {
  const client = useQueryClient();
  const key = ["repairs", "maintenance", makerspace.id];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<{ machine_schedules: MachineDue[]; schedules: Schedule[] }>(
    `/admin/makerspaces/${makerspace.id}/my-maintenance`) });
  const [running, setRunning] = useState<Due | null>(null);
  const [adding, setAdding] = useState<"inventory_product" | "bookable_space" | null>(null);
  const run = useMutation({
    mutationFn: ({ due, body }: { due: Due; body: Record<string, unknown> }) => staffRequest(due.kind === "machine"
      ? `/admin/maintenance/schedules/${due.id}/run` : `/admin/subject-maintenance/${due.id}/run`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { setRunning(null); void client.invalidateQueries({ queryKey: key }); },
  });
  const rows: Due[] = [
    ...(query.data?.machine_schedules ?? []).map(row => ({ kind: "machine" as const, id: row.id, label: row.machine_name, description: row.description, next_due: row.next_due })),
    ...(query.data?.schedules ?? []).filter(row => row.is_active).map(row => ({ kind: "item" as const, id: row.id, label: row.subject_label, description: row.description, next_due: row.next_due })),
  ].sort((a, b) => a.next_due.localeCompare(b.next_due));
  return <>
    <ListLayout header={{ title: t`Maintenance`, subtitle: t`Scheduled maintenance on items, units and rooms, and what is due in your coverage.`,
      primary: manager ? { label: t`Item schedule`, icon: "Plus", onClick: () => setAdding("inventory_product") } : undefined,
      secondary: manager ? { label: t`Room schedule`, onClick: () => setAdding("bookable_space") } : undefined }}
      state={opsQueryState(query, "maintenance")} isEmpty={!rows.length} empty={{ message: t`Nothing is scheduled here yet.` }}
      body={{ kind: "rows", rows: rows.map(row => <ListRow key={`${row.kind}-${row.id}`} title={row.description} onClick={() => setRunning(row)}
        identity={{ kind: "icon", icon: "Wrench", tone: "accent" }} meta={`${row.label} · due ${new Date(`${row.next_due}T00:00:00`).toLocaleDateString(formatLocale())}`}
        right={row.next_due < today() ? <StatusPill tone="danger" label={t`Overdue`} /> : row.next_due === today() ? <StatusPill tone="warn" label={t`Due today`} /> : null} />) }} />
    {running ? <StepDialog title={t`Log: ${running.description}`} submitLabel={t`Log maintenance`} makerspaceId={makerspace.id}
      fields={[{ name: "summary", label: t`What was done`, kind: "textarea", required: true }, { name: "parts_note", label: t`Parts and notes (optional)`, kind: "textarea" },
        { name: "cost", label: t`Cost (optional)`, kind: "number" }, { name: "cost_method", label: t`Paid by`, kind: "select", options: COST_METHODS }]}
      note="A cost is recorded as maintenance spending in the finance ledger."
      pending={run.isPending} error={run.error?.message} onClose={() => setRunning(null)} onSubmit={body => run.mutate({ due: running, body })} /> : null}
    {adding ? <NewSchedule kind={adding} makerspaceId={makerspace.id} onClose={() => setAdding(null)}
      onSaved={() => { setAdding(null); void client.invalidateQueries({ queryKey: key }); }} /> : null}
  </>;
}

function NewSchedule({ kind, makerspaceId, onClose, onSaved }: {
  kind: "inventory_product" | "bookable_space"; makerspaceId: number; onClose: () => void; onSaved: () => void;
}) {
  const options = useSubjectOptions(makerspaceId, kind).options;
  const save = useMutation({ mutationFn: (body: Record<string, unknown>) => staffRequest(`/admin/makerspaces/${makerspaceId}/subject-maintenance`,
    { method: "POST", body: JSON.stringify(body) }), onSuccess: onSaved });
  return <StepDialog key={options.length} title={kind === "bookable_space" ? t`New room schedule` : t`New item schedule`}
    submitLabel={t`Add schedule`} makerspaceId={makerspaceId} pending={save.isPending} error={save.error?.message} onClose={onClose}
    fields={[
      { name: "subject_id", label: kind === "bookable_space" ? t`Room` : t`Item`, kind: "select", required: true,
        options: [{ value: "", label: t`Choose` }, ...options.map(row => ({ value: String(row.id), label: row.label }))] },
      { name: "description", label: t`What to do`, kind: "text", required: true },
      { name: "interval_days", label: t`Every (days)`, kind: "number", required: true, initial: "30" },
      { name: "next_due", label: t`First due`, kind: "date", required: true, initial: today() }]}
    onSubmit={body => save.mutate({ ...body, subject_type: kind, subject_id: Number(body.subject_id),
      interval_days: Math.round(Number(body.interval_days)) })} />;
}
