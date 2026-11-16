import { t } from "@lingui/core/macro";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../../components/layouts";
import { ListRow, StatusBadge } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";
import { formatDate } from "../../../../lib/format";
import { useUrlListState } from "../../../../lib/useUrlListState";
import type { Machine } from "../../machinesApi";
import { opsQueryState } from "../../opsPresentation";
import { SavedViewsMenu } from "../../SavedViewsMenu";
import { useStaffGet } from "../shared";
import { jobStatusLabel, matchesServiceStatus, serviceStatusFilters } from "./ServiceConsoleSections";

const NO_FILTERS = { status: "active", machine: "", member: "", q: "" };
const NOT_ASSIGNED = "none";

const machineOf = (job: MachineServiceRequest) => job.assigned_machine ?? job.machine ?? null;

type Group = { key: string; label: string; machines: { key: string; label: string; jobs: MachineServiceRequest[] }[]; count: number };

/** Jobs grouped by machine type, then by machine (decision 241); unassigned jobs sit last in their type. */
export function groupJobs(jobs: MachineServiceRequest[], machines: Machine[]): Group[] {
  const typeNames = new Map(machines.map(row => [row.machine_type.slug, row.machine_type.name]));
  const groups = new Map<string, Map<string, { label: string; jobs: MachineServiceRequest[] }>>();
  for (const job of jobs) {
    const typeKey = job.machine_type || NOT_ASSIGNED;
    const machine = machineOf(job);
    const machineKey = machine ? String(machine.id) : NOT_ASSIGNED;
    const byMachine = groups.get(typeKey) ?? new Map();
    groups.set(typeKey, byMachine);
    const bucket = byMachine.get(machineKey) ?? { label: machine?.name ?? t`No machine yet`, jobs: [] };
    bucket.jobs.push(job);
    byMachine.set(machineKey, bucket);
  }
  return [...groups.entries()].map(([key, byMachine]) => {
    const rows = [...byMachine.entries()].map(([machineKey, bucket]) => ({ key: machineKey, ...bucket }))
      .sort((a, b) => (a.key === NOT_ASSIGNED ? 1 : b.key === NOT_ASSIGNED ? -1 : a.label.localeCompare(b.label)));
    return { key, label: typeNames.get(key) ?? (key === NOT_ASSIGNED ? t`No machine type` : key), machines: rows,
      count: rows.reduce((total, row) => total + row.jobs.length, 0) };
  }).sort((a, b) => a.label.localeCompare(b.label));
}

/** Every job across the machine types this person manages (A15), filtered by status, machine and member. */
export function AllJobsScreen({ makerspaceId, machines, onBack }: { makerspaceId: number; machines: Machine[]; onBack: () => void }) {
  const [, setParams] = useSearchParams();
  const list = useUrlListState(NO_FILTERS, "jobs_");
  const filters = list.values;
  const jobs = useStaffGet<MachineServiceRequest[]>(["machine-service-requests", makerspaceId, "all"],
    `/admin/makerspaces/${makerspaceId}/machine-service/requests`);
  const rows = jobs.data ?? [];
  const members = new Map(rows.map(job => [String(job.requester?.id ?? ""), job.requester_name || job.requester?.display || ""]));
  members.delete("");
  const term = filters.q.trim().toLowerCase();
  const visible = rows.filter(job => matchesServiceStatus(filters.status, job.status)
    && (!filters.machine || (filters.machine === NOT_ASSIGNED ? !machineOf(job) : String(machineOf(job)?.id ?? "") === filters.machine))
    && (!filters.member || String(job.requester?.id ?? "") === filters.member)
    && (!term || job.title.toLowerCase().includes(term)));
  const groups = groupJobs(visible, machines);
  const active = [filters.machine, filters.member, filters.q].filter(Boolean).length + (filters.status !== "active" ? 1 : 0);
  const open = (id: number) => setParams(current => { const next = new URLSearchParams(current); next.set("job", String(id)); return next; });
  return <ListLayout header={{ title: t`All jobs`, subtitle: t`Jobs on every machine type you look after, grouped by type and machine.`,
    secondary: { label: t`All machines`, onClick: onBack } }}
    filters={{ search: { label: t`Search jobs`, value: filters.q, onChange: value => list.setFilter("q", value) },
      activeCount: active, onClear: () => list.update({ ...NO_FILTERS }),
      views: <SavedViewsMenu makerspaceId={makerspaceId} entity="machine_jobs" state={list.values} onRestore={list.restore} />,
      controls: <div className="grid gap-3">
        <label className="eyebrow grid gap-1">{t`Status`}<select className="desk-input" value={filters.status} onChange={event => list.setFilter("status", event.target.value)}>
          {serviceStatusFilters().map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <label className="eyebrow grid gap-1">{t`Machine`}<select className="desk-input" value={filters.machine} onChange={event => list.setFilter("machine", event.target.value)}>
          <option value="">{t`All machines`}</option><option value={NOT_ASSIGNED}>{t`No machine yet`}</option>
          {machines.map(row => <option key={row.id} value={row.id}>{`${row.name} (${row.machine_type.name})`}</option>)}</select></label>
        <label className="eyebrow grid gap-1">{t`Member`}<select className="desk-input" value={filters.member} onChange={event => list.setFilter("member", event.target.value)}>
          <option value="">{t`All members`}</option>
          {[...members.entries()].sort((a, b) => a[1].localeCompare(b[1])).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      </div> }}
    filtered={active > 0} state={opsQueryState(jobs, "jobs")} isEmpty={!visible.length}
    empty={{ message: t`No jobs yet. New requests land here.` }}
    filteredEmpty={{ message: t`No jobs match these filters.`, action: { label: t`Clear filters`, onClick: () => list.update({ ...NO_FILTERS }) } }}
    body={{ kind: "rows", rows: groups.map(group => <details key={group.key} open className="rounded-xl border border-line bg-panel p-3">
      <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-3">
        <span className="title-section">{group.label}</span><span className="text-sm text-muted tabular-nums">{t`Jobs: ${group.count}`}</span></summary>
      <div className="mt-3 grid gap-4">{group.machines.map(machine => <section key={machine.key} aria-label={machine.label} className="grid gap-2">
        <h3 className="text-sm font-semibold text-ink">{machine.label} <span className="font-normal text-muted">· {machine.jobs.length}</span></h3>
        {machine.jobs.map(job => <ListRow key={job.id} title={job.title} onClick={() => open(job.id)}
          meta={[job.requester_name || job.requester?.display, job.created_at ? formatDate(job.created_at) : ""].filter(Boolean).join(" · ")}
          right={<StatusBadge status={job.status} label={jobStatusLabel(job.status)} />} />)}
      </section>)}</div>
    </details>) }} />;
}
