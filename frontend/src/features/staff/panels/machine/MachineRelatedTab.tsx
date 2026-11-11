import { t } from "@lingui/core/macro";
import { useContext } from "react";
import { useQuery } from "@tanstack/react-query";

import { ListRow, StatusPill } from "../../../../components/ui";
import { staffRequest } from "../../../../lib/api";
import { formatDate, formatDateTime } from "../../../../lib/format";
import { opsStatusLabel } from "../../opsPresentation";
import { serviceStatusLabel, TERMINAL_SERVICE_STATUSES } from "../../../machine-service/types";
import { openLinks, RelatedLinks, type RelatedCandidate } from "../../crossLinks/RelatedLinks";
import { useCrossLink } from "../../crossLinks/staffHref";
import { useSubjectIncidents } from "../../crossLinks/subjectIncidents";
import type { Machine } from "../../machinesApi";
import { StaffListContext } from "../../StaffListContext";
import { machineTypeSegment } from "../../staffTabs";
import type { StaffJob } from "./machineJobsApi";

/** `GET machine-bookings` row (decision 242, MC11), hand-typed until the client is regenerated. */
type MachineBookingRow = { id: number; machine_id: number; machine_name: string; member_name: string; starts_at: string; ends_at: string; status: string };

/** The drawer's own tabs this tab can jump to (they are siblings, not links). */
export type DrawerJump = { key: string; label: string };

const isOpen = (status: string) => !TERMINAL_SERVICE_STATUSES.has(status);

/**
 * MC11: everything tied to one machine in one place. Jobs and incidents load here; every other
 * area is a link into that area's own console, offered only when the viewer can open it
 * (decision 224). The drawer's sibling tabs (maintenance, consumables, sessions, warranty) are jumps.
 */
export function MachineRelatedTab({ machine, makerspaceId, canManageMachines, jumps, onJump }: {
  machine: Machine; makerspaceId: number; canManageMachines: boolean; jumps: DrawerJump[]; onJump: (key: string) => void;
}) {
  const link = useCrossLink();
  const { makerspace } = useContext(StaffListContext);
  const serviceOn = canManageMachines && (makerspace?.enabled_modules ?? []).includes("machine_service");
  const jobs = useQuery({
    queryKey: ["machine-related-jobs", makerspaceId, machine.id],
    enabled: serviceOn,
    retry: false,
    queryFn: ({ signal }) => staffRequest<StaffJob[]>(`/admin/makerspaces/${makerspaceId}/machine-service/requests?machine=${machine.id}`, { signal }),
  });
  // Re-checked against the machine so an unfiltered answer can never pass as this machine's jobs.
  const jobRows = (jobs.data ?? []).filter(job => job.machine?.id === machine.id || job.assigned_machine?.id === machine.id);
  const incidents = useSubjectIncidents(makerspaceId, "machine", machine.id);
  // MC11: machine-time bookings, read-only here (a Machine Manager may not manage bookings).
  const timeBooking = canManageMachines && (makerspace?.enabled_features ?? []).includes("machines.time_booking");
  const bookings = useQuery({
    queryKey: ["machine-related-bookings", makerspaceId, machine.id],
    enabled: timeBooking,
    retry: false,
    queryFn: ({ signal }) => staffRequest<{ count: number; results: MachineBookingRow[] }>(
      `/admin/makerspaces/${makerspaceId}/machine-bookings?machine=${machine.id}`, { signal }),
  });
  const bookingRows = (bookings.data?.results ?? []).filter(row => row.machine_id === machine.id);
  const typePath = machineTypeSegment(machine.machine_type);
  const candidates: RelatedCandidate[] = [
    ...(serviceOn ? [{ key: "jobs", label: t`Service queue`, helper: t`All ${machine.machine_type.name} jobs`,
      count: jobs.isLoading ? null : jobRows.filter(job => isOpen(job.status)).length, href: link("machines", {}, `${typePath}/queue`) }] : []),
    ...(!incidents.hidden ? [{ key: "incidents", label: t`Incidents`, helper: t`Reported on this machine`, count: incidents.count, href: link("incidents", { machine: machine.id }) }] : []),
    ...(canManageMachines ? [{ key: "certifications", label: t`Certifications`, helper: t`Who may use ${machine.machine_type.name} machines`, href: link("machines", {}, `${typePath}/certifications`) }] : []),
    { key: "repairs", label: t`Repairs`, helper: t`Repair jobs and work orders`, href: link("repairs") },
    { key: "tobuy", label: t`To-Buy`, helper: t`Parts and supplies to order`, href: link("tobuy") },
    { key: "bookings", label: t`Bookings`, helper: t`Machine time bookings`, href: link("bookings") },
  ];
  const links = openLinks(candidates);
  return <div className="grid min-w-0 gap-6">
    {jumps.length ? <section className="grid gap-2" aria-label={t`On this machine`}>
      <h3 className="title-section">{t`On this machine`}</h3>
      <div className="flex flex-wrap gap-2">{jumps.map(jump =>
        <button key={jump.key} type="button" className="desk-button" onClick={() => onJump(jump.key)}>{jump.label}</button>)}</div>
    </section> : null}
    <RelatedLinks links={links} empty={t`Nothing else is linked to this machine that you can open.`} />
    {serviceOn ? <section className="grid gap-2" aria-label={t`Recent jobs`}>
      <h3 className="title-section">{t`Recent jobs`}</h3>
      {jobs.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading jobs…`}</p>
        : jobs.isError ? <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger"><p>{t`Couldn't load jobs.`}</p>
          <button type="button" className="desk-button" onClick={() => { void jobs.refetch(); }}>{t`Retry`}</button></div>
        : !jobRows.length ? <p className="text-sm text-muted">{t`No jobs on this machine yet.`}</p>
        : <div className="grid gap-2">{jobRows.slice(0, 5).map(job => <ListRow key={job.id} title={job.title || t`Job #${job.id}`}
          meta={[job.requester_name, formatDate(job.created_at)].filter(Boolean).join(" · ")}
          right={<StatusPill tone={isOpen(job.status) ? "accent" : "neutral"} label={serviceStatusLabel(job.status)} />} />)}</div>}
    </section> : null}
    {timeBooking && !bookings.isError ? <section className="grid gap-2" aria-label={t`Machine bookings`}>
      <h3 className="title-section">{t`Machine bookings`}</h3>
      {bookings.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading bookings…`}</p>
        : !bookingRows.length ? <p className="text-sm text-muted">{t`No bookings for this machine.`}</p>
        : <div className="grid gap-2">{bookingRows.slice(0, 10).map(row => <ListRow key={row.id} title={row.member_name || t`Booking #${row.id}`}
          identity={{ kind: "date", date: row.starts_at }} meta={`${formatDateTime(row.starts_at)} – ${formatDateTime(row.ends_at)}`}
          right={<StatusPill tone={row.status === "confirmed" ? "success" : "neutral"} label={opsStatusLabel(row.status)} />} />)}</div>}
    </section> : null}
    {!incidents.hidden && incidents.rows.length ? <section className="grid gap-2" aria-label={t`Recent incidents`}>
      <h3 className="title-section">{t`Recent incidents`}</h3>
      <div className="grid gap-2">{incidents.rows.slice(0, 3).map(row => <ListRow key={row.id} title={row.title}
        href={link("incidents", { incident: row.id })} meta={formatDate(row.occurred_at)} />)}</div>
    </section> : null}
  </div>;
}
