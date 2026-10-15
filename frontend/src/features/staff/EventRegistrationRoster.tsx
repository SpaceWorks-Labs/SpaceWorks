import { opsStatusLabel } from "./opsPresentation";
import { useState } from "react";

import { DataTable, EmptyState, Skeleton, StatusBadge } from "../../components/ui";
import { EventCheckInOperator } from "./EventCheckInOperator";
import { EventBadgeActions } from "./EventBadgeActions";
import { EventRegisterMember } from "./EventRegisterMember";
import { PaymentReconcileActions } from "./PaymentReconcileActions";
import { useCorrectAttendance } from "./eventFeedbackApi";
import {
  useApproveEventRegistration,
  useCancelEventRegistration,
  useEventRegistrations,
  useMarkEventAttended,
  usePromoteEventRegistration,
  useRejectEventRegistration,
  type StaffEvent,
} from "./eventsApi";
import { eventErrorText } from "./eventUi";

export function EventRegistrationRoster({ visible = true, event, makerspaceId, offlineCheckInEnabled, showCheckIn = true }: { visible?: boolean;
  event: StaffEvent;
  makerspaceId: number;
  offlineCheckInEnabled: boolean;
  showCheckIn?: boolean;
}) {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [includeAttended, setIncludeAttended] = useState(false);
  const rows = useEventRegistrations(event.id, page);
  const approve = useApproveEventRegistration(makerspaceId, event.id);
  const reject = useRejectEventRegistration(makerspaceId, event.id);
  const promote = usePromoteEventRegistration(makerspaceId, event.id);
  const attended = useMarkEventAttended(makerspaceId, event.id);
  const correct = useCorrectAttendance(makerspaceId, event.id);
  const cancel = useCancelEventRegistration(makerspaceId, event.id);

  function pendingFor(registrationId: number) {
    return [approve, reject, promote, attended, correct, cancel].some(
      (mutation) => mutation.isPending && mutation.variables === registrationId,
    );
  }

  function errorFor(registrationId: number) {
    return [approve, reject, promote, attended, correct, cancel].find(
      (mutation) => mutation.error && mutation.variables === registrationId,
    )?.error;
  }

  const fallbackCount = Object.values(event.registration_counts).reduce((sum, value) => sum + value, 0);
  const checkable = event.status === "published" || event.status === "completed";

  if (!visible) return null;
  return <section aria-labelledby="registrations-title">
    <h3 id="registrations-title" className="title-section mb-2">Registrations <span className="tabular-nums">({rows.data?.count ?? fallbackCount})</span></h3>
    {rows.isLoading ? <Skeleton className="h-32 w-full" /> : null}
    {rows.error ? <p className="text-sm text-danger">{eventErrorText(rows.error)}</p> : null}
    {rows.data && !rows.data.results.length ? <EmptyState message="No registrations yet. Add your first guest." /> : null}
    {event.status === "published" && event.registration_open ? <button className="desk-button mb-4" type="button" onClick={() => setAdding(value => !value)}>{adding ? "Close registration form" : "Add registration"}</button> : null}
    <EventRegisterMember visible={adding} makerspaceId={makerspaceId} eventId={event.id} customForm={event.custom_form} audience={event.registration_audience} ticketsEnabled={event.ticketing_features?.includes("events.ticket_types")} promosEnabled={event.ticketing_features?.includes("events.promo_codes")} disabled={event.status !== "published" || !event.registration_open} />
    {checkable && showCheckIn ? <EventCheckInOperator makerspaceId={makerspaceId} eventId={event.id} offlineEnabled={offlineCheckInEnabled} /> : null}
    {rows.data?.results.length ? <EventBadgeActions event={event} makerspaceId={makerspaceId} selectedIds={selectedIds} includeAttended={includeAttended} onIncludeAttended={(value) => { setIncludeAttended(value); if (!value) setSelectedIds([]); }} /> : null}
    {rows.data?.results.length ? <DataTable data={rows.data.results} columns={[
      { key: "badge", header: "Badge", render: row => <label className="inline-flex min-h-11 min-w-11 items-center justify-center"><input type="checkbox" aria-label={`Select ${row.name} for a badge`} disabled={row.status !== "registered" && !(includeAttended && row.status === "attended")} checked={selectedIds.includes(row.id)} onChange={e => setSelectedIds(ids => e.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))} /></label> },
      { key: "name", header: "Name", render: row => <>{row.name}<PaymentReconcileActions makerspaceId={makerspaceId} payment={row.payment} invalidateKeys={[["event", event.id, "registrations"], ["event", event.id], ["events", makerspaceId]]} /></> },
      { key: "contact", header: "Contact", render: row => <><a className="inline-flex min-h-11 items-center hover:underline" href={`mailto:${row.email}`}>{row.email}</a><a className="flex min-h-11 items-center text-muted hover:underline" href={`tel:${row.phone}`}>{row.phone}</a></> },
      { key: "status", header: "Status", render: row => <StatusBadge status={row.status} label={opsStatusLabel(row.status)} /> },
      { key: "actions", header: "Action", render: row => {
        const pending = pendingFor(row.id);
        const rowError = errorFor(row.id);
        const cancellable = ["pending_approval", "registered", "waitlisted"].includes(row.status);
        const hasAction = cancellable || row.status === "attended";
        return <><div className="flex flex-wrap gap-2">
            {cancellable ? <button className="desk-button-danger" type="button" disabled={pending} onClick={() => cancel.mutate(row.id)}>Cancel registration</button> : null}
            {row.status === "pending_approval" ? <><button className="desk-button-success" type="button" disabled={pending} onClick={() => approve.mutate(row.id)}>Approve</button><button className="desk-button-danger" type="button" disabled={pending} onClick={() => reject.mutate(row.id)}>Reject</button></> : null}
            {row.status === "waitlisted" && event.registration_requires_approval ? <><button className="desk-button-success" type="button" disabled={pending} onClick={() => promote.mutate(row.id)}>Promote</button><button className="desk-button-danger" type="button" disabled={pending} onClick={() => reject.mutate(row.id)}>Reject</button></> : null}
            {row.status === "registered" && checkable ? <button className="desk-button-success" type="button" disabled={pending} onClick={() => attended.mutate(row.id)}>Mark attended</button> : null}
            {row.status === "attended" ? <button className="desk-button-danger" type="button" disabled={pending} onClick={() => correct.mutate(row.id)}>Correct attendance</button> : null}
            {!hasAction ? "—" : null}
          </div>{rowError ? <p className="mt-1 text-xs text-danger" role="alert">{eventErrorText(rowError)}</p> : null}</>;
      } },
    ]} /> : null}
    <div className="mt-3 flex items-center justify-between gap-2"><span className="tabular-nums text-xs text-muted">Page {page}</span><div className="flex gap-2"><button className="desk-button" type="button" disabled={!rows.data?.previous} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button><button className="desk-button" type="button" disabled={!rows.data?.next} onClick={() => setPage((value) => value + 1)}>Next</button></div></div>
  </section>;
}
