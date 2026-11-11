import { t } from "@lingui/core/macro";
import { DeskBadgeSwitch } from "./eventBadges/DeskBadgeSwitch";
import { CredentialLostCardActions } from "./eventCredentials/CredentialLostCardActions";
import { opsStatusLabel } from "./opsPresentation";
import { useState } from "react";

import { DataTable, EmptyState, Skeleton, StatusBadge } from "../../components/ui";
import { EventRegistrationAnswers } from "./EventRegistrationAnswers";
import { ParticipationChips, ReacceptButton } from "./eventParticipation/RosterParticipation";
import { offerCancellationUndo, useRestoreRegistration } from "./eventToolsApi";
import { EventCheckInOperator } from "./EventCheckInOperator";
import { EventBadgeActions } from "./EventBadgeActions";
import { EventDisclosure } from "./EventDisclosure";
import { EventRegisterMember } from "./EventRegisterMember";
import { PaymentReconcileActions } from "./PaymentReconcileActions";
import { DeskCollectPanel } from "./eventTicketing/DeskCollectPanel";
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
import { eventAccess } from "./eventStaffPermissions";
import { StaffEquipmentProposal } from "./StaffEquipmentProposal";
import { EventEquipmentPlanner } from "./eventEquipment/EventEquipmentPlanner";
import { useStaffIntakeOwners } from "./useStaffIntakeOwners";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import type { EventRegistration } from "./eventsApiTypes";
import type { RegistrationFilters } from "./eventsRegistrationApi";
import { RegistrationFiltersBar, TicketedFiltersBar } from "./eventRoster/RegistrationFilters";
import { PayByNotice } from "../events/PayByNotice";
import { GuestCsvButton } from "./eventRoster/GuestCsvButton";
import { BulkDecisionBar } from "./bulk/BulkDecisionBar";
import { EventPanelPager } from "./EventPanelPager";

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
  const access = eventAccess(event);
  const intakeOwner = useStaffIntakeOwners(makerspaceId);
  const [filters, setFilters] = useState<RegistrationFilters>({});
  const q = useDebouncedValue((filters.q ?? "").trim());
  const filtered = Boolean(filters.status || filters.ticket_type || q);
  const rows = useEventRegistrations(event.id, page, { status: filters.status, ticket_type: filters.ticket_type, q, group: filters.group });
  // EB4/EB5: ticket filter and column, only for events that sell ticket types.
  const ticketsOn = Boolean(event.ticketing_features?.includes("events.ticket_types"));
  const approve = useApproveEventRegistration(makerspaceId, event.id);
  const reject = useRejectEventRegistration(makerspaceId, event.id);
  const promote = usePromoteEventRegistration(makerspaceId, event.id);
  const attended = useMarkEventAttended(makerspaceId, event.id);
  const correct = useCorrectAttendance(makerspaceId, event.id);
  const cancel = useCancelEventRegistration(makerspaceId, event.id);
  const restore = useRestoreRegistration(makerspaceId, event.id);

  function pendingFor(registrationId: number) {
    return [approve, reject, promote, attended, correct, cancel, restore].some(
      (mutation) => mutation.isPending && mutation.variables === registrationId,
    );
  }

  function errorFor(registrationId: number) {
    return [approve, reject, promote, attended, correct, cancel, restore].find(
      (mutation) => mutation.error && mutation.variables === registrationId,
    )?.error;
  }

  const fallbackCount = Object.values(event.registration_counts).reduce((sum, value) => sum + value, 0);
  const checkable = event.status === "published" || event.status === "completed";

  if (!visible) return null;
  return <section aria-labelledby="registrations-title">
    <h3 id="registrations-title" className="title-section mb-2">{t`Registrations `}<span className="tabular-nums">({rows.data?.count ?? fallbackCount})</span></h3>
    {rows.isLoading ? <Skeleton className="h-32 w-full" /> : null}
    {rows.error ? <p className="text-sm text-danger">{eventErrorText(rows.error)}</p> : null}
    {ticketsOn ? <TicketedFiltersBar eventId={event.id} value={filters} onChange={next => { setFilters(next); setPage(1); }} />
      : <RegistrationFiltersBar value={filters} tickets={[]} onChange={next => { setFilters(next); setPage(1); }} />}
    <GuestCsvButton eventId={event.id} status={filters.status} q={q} />
    {access.registrations ? <BulkDecisionBar title={t`Decide several registrations`} decisions={[{ key: "approve", label: t`Approve` }, { key: "reject", label: t`Reject`, danger: true }]}
      rows={(rows.data?.results ?? []).filter(row => row.status === "pending_approval").map(row => ({ id: row.id, label: `${row.name} · ${row.email}` }))}
      path={decision => `/admin/bulk/event-registrations/${decision}`} onDone={() => { void rows.refetch(); }} /> : null}
    {rows.data && !rows.data.results.length ? <EmptyState message={filtered ? t`No registrations match these filters.` : t`No registrations yet. Add your first guest.`} /> : null}
    {event.status === "published" && event.registration_open ? <button className="desk-button mb-4" type="button" aria-expanded={adding} onClick={() => setAdding(value => !value)}>{adding ? t`Close registration form` : t`Add registration`}</button> : null}
    <EventRegisterMember visible={adding} makerspaceId={makerspaceId} eventId={event.id} customForm={event.custom_form} audience={event.registration_audience} ticketsEnabled={event.ticketing_features?.includes("events.ticket_types")} promosEnabled={event.ticketing_features?.includes("events.promo_codes")} disabled={event.status !== "published" || !event.registration_open} />
    {checkable && showCheckIn && access.checkIn ? <EventCheckInOperator makerspaceId={makerspaceId} eventId={event.id} offlineEnabled={offlineCheckInEnabled} canManageStation={access.manager} /> : null}
    {(access.edit || access.checkIn) && rows.data?.results.length ? <DeskBadgeSwitch key={`desk-${event.id}`} eventId={event.id} registrationIds={selectedIds} canEdit={access.edit} canPrint={access.checkIn} /> : null}
    {(access.edit || access.checkIn) && rows.data?.results.length ? <EventDisclosure title={t`Badges`}><EventBadgeActions event={event} makerspaceId={makerspaceId} selectedIds={selectedIds} includeAttended={includeAttended} onIncludeAttended={(value) => { setIncludeAttended(value); if (!value) setSelectedIds([]); }} canEdit={access.edit} canPrint={access.checkIn} /></EventDisclosure> : null}
    {access.registrations && rows.data?.results.length ? <div className="mb-4 empty:hidden"><EventEquipmentPlanner makerspaceId={makerspaceId} eventId={event.id}
      participants={rows.data.results} canEditWindow={access.edit && !["cancelled", "completed"].includes(event.status)} /></div> : null}
    {rows.data?.results.length ? <DataTable data={rows.data.results} columns={[
      // Check-in-only staff may reprint badges for attended guests; full managers select registered guests too.
      { key: "badge", header: t`Badge`, phone: "lead", render: row => <label className="inline-flex min-h-11 min-w-11 items-center justify-center"><input type="checkbox" aria-label={t`Select ${row.name} for a badge`} disabled={!access.checkIn || (!access.manager ? row.status !== "attended" : row.status !== "registered" && !(includeAttended && row.status === "attended"))} checked={selectedIds.includes(row.id)} onChange={e => setSelectedIds(ids => e.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))} /></label> },
      { key: "name", header: t`Name`, phone: "title", render: row => <>{row.name}{access.manager ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={row.payment} invalidateKeys={[["event", event.id, "registrations"], ["event", event.id], ["events", makerspaceId]]} /> : null}</> },
      ...(ticketsOn ? [{ key: "ticket", header: t`Ticket`, render: (row: EventRegistration) => row.ticket_type_name || "—" }] : []),
      { key: "contact", header: t`Contact`, render: row => <><a className="inline-flex min-h-11 items-center [overflow-wrap:anywhere] hover:underline" href={`mailto:${row.email}`}>{row.email}</a><a className="flex min-h-11 items-center text-muted hover:underline" href={`tel:${row.phone}`}>{row.phone}</a></> },
      { key: "status", header: t`Status`, render: row => <><StatusBadge status={row.status} label={opsStatusLabel(row.status)} /><ParticipationChips row={row} />{row.no_longer_eligible ? <span className="mt-1 block text-xs text-warn-ink">{t`No longer eligible`}</span> : null}<PayByNotice payBy={row.pay_by} audience="staff" /></> },
      { key: "actions", header: t`Action`, render: row => {
        const pending = pendingFor(row.id);
        const rowError = errorFor(row.id);
        const cancellable = ["pending_approval", "registered", "waitlisted"].includes(row.status);
        const hasAction = cancellable || row.status === "attended" || (access.registrations && row.status === "rejected");
        return <><div className="flex flex-wrap gap-2">
            {cancellable ? <button className="desk-button-danger" type="button" disabled={pending} onClick={() => cancel.mutate(row.id, { onSuccess: (cancelled) => offerCancellationUndo(cancelled, restore.mutateAsync) })}>{t`Cancel registration`}</button> : null}
            {row.status === "pending_approval" ? <><button className="desk-button-success" type="button" disabled={pending} onClick={() => approve.mutate(row.id)}>{t`Approve`}</button><button className="desk-button-danger" type="button" disabled={pending} onClick={() => reject.mutate(row.id)}>{t`Reject`}</button></> : null}
            {row.status === "waitlisted" && event.registration_requires_approval ? <><button className="desk-button-success" type="button" disabled={pending} onClick={() => promote.mutate(row.id)}>{t`Promote`}</button><button className="desk-button-danger" type="button" disabled={pending} onClick={() => reject.mutate(row.id)}>{t`Reject`}</button></> : null}
            {access.checkIn && row.status === "registered" && checkable ? <button className="desk-button-success" type="button" disabled={pending} onClick={() => attended.mutate(row.id)}>{t`Mark attended`}</button> : null}
            {access.checkIn && row.status === "attended" ? <button className="desk-button-danger" type="button" disabled={pending} onClick={() => correct.mutate(row.id)}>{t`Correct attendance`}</button> : null}
            {access.registrations ? <ReacceptButton eventId={event.id} row={row} onDone={() => void rows.refetch()} /> : null}
            {!hasAction ? "—" : null}
            {access.registrations ? <EventRegistrationAnswers row={row} schema={event.custom_form} makerspaceId={makerspaceId} eventId={event.id} /> : null}
            {access.registrations && ["registered", "attended"].includes(row.status) ? <StaffEquipmentProposal tenant={makerspaceId} domain="event" resourceId={event.id} targetId={row.id} pendingOwner={intakeOwner(`event:${event.id}:${row.id}`)} /> : null}
          </div>{access.checkIn && checkable && ["registered", "attended"].includes(row.status)
            ? <EventDisclosure title={t`Lost or shared QR`}><div className="flex flex-wrap items-center gap-2"><CredentialLostCardActions eventId={event.id} registrationId={row.id}
              version={(event as StaffEvent & { version?: number }).version} /></div></EventDisclosure> : null}{access.checkIn && row.payment?.status === "pending" && event.ticketing_features?.includes("events.desk_collect")
            ? <EventDisclosure title={t`Collect payment`}><DeskCollectPanel registrationId={row.id} onCollected={() => void rows.refetch()} /></EventDisclosure> : null}{rowError ? <p className="mt-1 text-xs text-danger" role="alert">{eventErrorText(rowError)}</p> : null}</>;
      } },
    ]} /> : null}
    <div className="mt-3"><EventPanelPager page={page} setPage={setPage} count={rows.data?.count} next={rows.data?.next} /></div>
  </section>;
}
