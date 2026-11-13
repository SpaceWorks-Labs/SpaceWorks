import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { machineStatusLabel } from "./machine/machineStatusLabel";
import { useQuery } from "@tanstack/react-query";
import { ListLayout } from "../../../components/layouts";
import { ListRow, RelativeTime, StatusBadge, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { useUrlListState } from "../../../lib/useUrlListState";

import { collectionResults, getMachineTypes, machineKeys } from "../machinesApi";
import { machineTypeSegment, staffTabPath } from "../staffTabs";


const printStatuses: Record<string, string> = { pending_prints: "pending", active_prints: "in_progress", prints_awaiting_collection: "completed" };
// The dashboard's machine-job tiles (dashboard_attention.py) queue every machine type, not only the printer.
const jobStatuses: Record<string, string> = { jobs_to_review: "pending", jobs_in_progress: "in_progress", jobs_awaiting_collection: "completed" };
const statuses: Record<string, string> = { ...printStatuses, ...jobStatuses };
const labels = (): Record<string, string> => ({ pending_prints: t`Pending prints`, active_prints: t`Active prints`, prints_awaiting_collection: t`Ready to collect`, maintenance_overdue: t`Maintenance overdue`,
  jobs_to_review: t`Jobs to review`, jobs_in_progress: t`Jobs in progress`, jobs_awaiting_collection: t`Jobs ready to collect` });
type Schedule = { id: number; machine_id: number; machine_name: string; description: string; next_due: string };
type Job = { id: number; title: string; status: string };

export function isDashboardMachineQueue(queue: string) { return Object.prototype.hasOwnProperty.call(labels(), queue); }
export function DashboardMachineQueue({ makerspaceId, slug, single, guest, enabled }: { makerspaceId: number; slug?: string | null; single: boolean; guest: boolean; enabled: boolean }) {
  const list = useUrlListState({ work_queue: "", page: "1" });
  const queue = list.values.work_queue;
  const maintenance = queue === "maintenance_overdue";
  const allJobs = Object.prototype.hasOwnProperty.call(jobStatuses, queue);
  const types = useQuery({ queryKey: machineKeys.types(makerspaceId), queryFn: () => getMachineTypes(makerspaceId), enabled: enabled && !maintenance });
  const printer = collectionResults(types.data).find(type => type.is_builtin && type.slug === "3d_printer" && type.makerspace === null);
  const jobs = useQuery({ queryKey: ["dashboard-print-queue", makerspaceId, queue, printer?.id], queryFn: () => staffRequest<Job[]>(`/admin/makerspaces/${makerspaceId}/machine-service/requests?status=${statuses[queue]}${allJobs ? "" : `&machine_type_id=${printer!.id}`}`), enabled: enabled && !maintenance && (allJobs || !!printer) });
  const schedules = useQuery({ queryKey: ["dashboard-maintenance-queue", makerspaceId, list.page], queryFn: () => staffRequest<{ count: number; results: Schedule[] }>(`/admin/makerspace/${makerspaceId}/maintenance-overdue?page=${list.page}`), enabled: enabled && maintenance });
  const baseHref = staffTabPath("machines", guest, slug, single);
  const href = consoleSessionHref(baseHref);
  const error = types.error ?? jobs.error ?? schedules.error;
  const scheduleRows = enabled && maintenance ? schedules.data?.results : undefined;
  const jobRows = enabled && !maintenance ? jobs.data : undefined;
  const loading = enabled && (types.isLoading || jobs.isLoading || schedules.isLoading);
  return <ListLayout header={{ title: labels()[queue], secondary: { label: t`All machines`, href } }}
    state={loading ? { status: "loading" } : error ? { status: "error", error: t`Couldn't load work list. Try again.`, onRetry: () => { void types.refetch(); void jobs.refetch(); void schedules.refetch(); } } : { status: "ready" }}
    isEmpty={enabled && (scheduleRows?.length === 0 || jobRows?.length === 0)}
    empty={{ message: t`No work in this queue. Open All machines to review your equipment.` }}
    body={{ kind: "rows", rows: <>
      {!enabled ? <p role="alert">{t`This queue is unavailable because its module is disabled.`}</p> : null}
      {enabled && !maintenance && !allJobs && types.isSuccess && !printer ? <p>{t`No built-in printer type is available in your scope.`}</p> : null}
      {scheduleRows?.map(row => <ListRow key={row.id} title={`${row.machine_name}: ${row.description}`}
        href={consoleSessionHref(`${baseHref}?machine=${row.machine_id}&detail_tab=Maintenance`)} meta={<>{t`Due `}<RelativeTime date={row.next_due} /></>}
        right={<StatusPill label={t`Overdue`} tone="danger" />} />)}
      {jobRows?.map(row => <ListRow key={row.id} title={row.title} right={<StatusBadge status={row.status} label={machineStatusLabel(row.status)} />}
        href={allJobs ? consoleSessionHref(`${baseHref}?job=${row.id}`) : printer ? consoleSessionHref(`${staffTabPath("machines", guest, slug, single, `${machineTypeSegment(printer)}/queue`)}?job_status=${statuses[queue]}`) : undefined}
        meta={allJobs ? t`Open job` : "Open printer queue"} />)}
    </> }} pagination={enabled && maintenance ? { page: list.page, pageSize: 24, count: schedules.data?.count ?? 0, onChange: list.setPage } : undefined} />;
}
