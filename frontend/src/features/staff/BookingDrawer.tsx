import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ConfirmDialog, DetailDrawer, EmptyState, Skeleton, StatusBadge } from "../../components/ui";
import { CustomAnswersView } from "../forms/CustomAnswersView";
import { BookableSpaceForm, valuesForSpace } from "./BookableSpaceForm";
import { StaffBookingForm } from "./StaffBookingForm";
import {
  useBookableSpace,
  useBookingAction,
  useDeactivateBookableSpace,
  useSpaceBookings,
  useUpdateBookableSpace,
  type Booking,
  type BookingAction,
  type BookingFilters,
} from "./bookingsApi";
import { useUrlListState } from "../../lib/useUrlListState";
import { BookingDetailsEditor } from "./BookingDetailsEditor";
import { BookingPassDesigner } from "./BookingPassDesigner";
import { BookingArrivalScanner } from "./BookingArrivalScanner";
import { BookingBroadcastsPanel } from "./BookingBroadcastsPanel";
import { BookingStaffAccess } from "./BookingStaffAccess";
import { bookingAccess } from "./bookingStaffPermissions";
import { BookingResourceTabs } from "./BookingResourceTabs";
import { BookingResourceAnalytics } from "./BookingResourceAnalytics";
import { PaymentReconcileActions } from "./PaymentReconcileActions";

import { BookingCloneControl } from "./BookingCloneControl";
import { BookingReservationEditor } from "./BookingReservationEditor";
import { BookingDrawerTabs, type BookingDrawerTab } from "./BookingDrawerTabs";

type PendingAction = { booking: Booking; action: BookingAction };

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function bookingTime(booking: Booking) {
  const format = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
  return `${format.format(new Date(booking.starts_at))} – ${format.format(new Date(booking.ends_at))}`;
}

function actionLabel(action: BookingAction) {
  return {
    restore: "Undo cancellation",
    approve: "Approve",
    reject: "Reject",
    cancel: "Cancel booking",
    complete: "Complete",
    "no-show": "Mark no-show",
  }[action];
}

export function BookingDrawer({ makerspaceId, spaceId, onClose, recurringEnabled = false, additionalTabs = [] }: {
  additionalTabs?: BookingDrawerTab[];
  recurringEnabled?: boolean;
  makerspaceId: number;
  spaceId: number;
  onClose: () => void;
}) {
  const [selectedTab, setSelectedTab] = useState("overview");
  const spaceQuery = useBookableSpace(spaceId);
  const space = spaceQuery.data;
  const access = bookingAccess(space);
  const [params] = useSearchParams();
  const list = useUrlListState({ page: "1", status: "", starts_at: "", ends_at: "", ordering: "starts_at" }, `booking-${spaceId}.`);
  const { page, setPage } = list;
  const filters: BookingFilters = { ...list.values, status: list.values.status as BookingFilters["status"], booking_id: Number(params.get("space")) === spaceId ? Number(params.get("booking")) || undefined : undefined };
  const [tab, setTab] = useState<"details" | "analytics">("details");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const bookings = useSpaceBookings(spaceId, filters, page, list.values.ordering, access.reservations);
  const update = useUpdateBookableSpace(makerspaceId, spaceId);
  const deactivate = useDeactivateBookableSpace(makerspaceId, spaceId);
  const action = useBookingAction(makerspaceId, spaceId);

  const setFilter = <K extends keyof BookingFilters>(key: K, value: BookingFilters[K]) => {
    list.setFilter(key, String(value ?? ""));
  };
  const actionError = update.error || deactivate.error || action.error;
  const hasReports = Boolean(space?.report_features?.length);
  const activeTab = hasReports ? tab : "details";
  const resourceTabs = [...additionalTabs, ...(space?.passes_enabled && access.edit ? [{
    id: "passes", label: "Pass designer", content: selectedTab === "passes"
      ? <BookingPassDesigner key={spaceId} makerspaceId={makerspaceId} spaceId={spaceId} /> : null,
  }] : [])];
  const visibleTab = selectedTab === "overview" || resourceTabs.some((item) => item.id === selectedTab) ? selectedTab : "overview";

  return (
    <>
      <DetailDrawer open title={space?.name ?? "Space details"} onClose={onClose}>
        {spaceQuery.isLoading ? <Skeleton className="h-64 w-full" /> : null}
        {spaceQuery.error ? <EmptyState title="Unable to load space" description={errorText(spaceQuery.error)} /> : null}
        {space ? (
          <div className="grid gap-6">
            <BookingDrawerTabs tabs={[{ id: "overview", label: "Resource and reservations", content: null }, ...resourceTabs]} selected={visibleTab} onSelect={setSelectedTab} />
            {resourceTabs.find((item) => item.id === visibleTab)?.content}
            {visibleTab === "overview" ? <>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={space.is_active ? "active" : "inactive"} />
              <span className="text-sm text-muted">{space.effective_requester_notifications_enabled ? "Requester emails on" : "Requester emails off"}</span>
            </div>
            {hasReports ? <BookingResourceTabs active={activeTab} onChange={setTab} /> : null}
            <div id="resource-analytics" role="tabpanel" aria-labelledby="resource-analytics-tab" hidden={activeTab !== "analytics"}>
              {activeTab === "analytics" && hasReports ? <BookingResourceAnalytics makerspaceId={makerspaceId} spaceId={spaceId} features={space.report_features ?? []} /> : null}
            </div>
            <div id="resource-details" role={hasReports ? "tabpanel" : undefined} aria-labelledby={hasReports ? "resource-details-tab" : undefined} hidden={activeTab !== "details"} className="grid gap-6">
            {access.manager ? <BookableSpaceForm
              makerspaceId={makerspaceId}
              key={space.updated_at}
              initialValues={valuesForSpace(space)}
              onSubmit={(payload) => update.mutate(payload)}
              pending={update.isPending}
              error={update.error ? errorText(update.error) : undefined}
              submitLabel="Save changes"
              disabled={!space.is_active}
            /> : access.edit ? <BookingDetailsEditor key={space.updated_at} space={space} pending={update.isPending} onSubmit={(payload) => update.mutate(payload)} /> : <p className="text-sm text-muted">{space.description || "Use your assigned resource permissions."}</p>}
            {access.manager && space.clone_enabled ? <BookingCloneControl space={space} /> : null}
            {access.manager && space.staff_grants_enabled ? <BookingStaffAccess target={{ id: spaceId }} /> : null}
            {access.manager && space.is_active ? <button className="desk-button-danger w-fit" type="button" onClick={() => setConfirmDeactivate(true)}>Deactivate space</button> : !space.is_active ? <p className="text-sm text-muted">This space is inactive and read-only.</p> : null}
            {space.checkin_enabled && (access.manager || space.staff_permissions?.includes("check_in")) ? <BookingArrivalScanner key={spaceId} makerspaceId={makerspaceId} spaceId={spaceId} /> : null}
            {access.reservations && space.broadcasts_enabled ? <BookingBroadcastsPanel makerspaceId={makerspaceId} spaceId={spaceId} /> : null}
            {access.reservations ? <section aria-labelledby="space-bookings-title">
              {space.is_active ? <StaffBookingForm recurringEnabled={recurringEnabled || space.recurring_enabled} makerspaceId={makerspaceId} space={space} /> : null}
              <div className="mb-3">
                <h3 id="space-bookings-title" className="title-section">Bookings <span className="font-mono">({bookings.data?.count ?? 0})</span></h3>
                <p className="mt-1 text-xs text-muted">Contact details and custom answers are staff-only.</p>
              </div>
              <label className="text-xs text-muted">Sort<select className="desk-input" value={list.values.ordering} onChange={(event) => list.setFilter("ordering", event.target.value)}><option value="starts_at">Starts first</option><option value="-starts_at">Starts last</option><option value="created_at">Created first</option></select></label>
              <div className="mb-3 grid gap-2 sm:grid-cols-3">
                <label className="grid gap-1 text-xs font-semibold text-muted">Status
                  <select className="desk-input" value={filters.status ?? ""} onChange={(event) => setFilter("status", event.target.value as BookingFilters["status"])}>
                    <option value="">All statuses</option>
                    <option value="pending">Pending</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="rejected">Rejected</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="completed">Completed</option>
                    <option value="no_show">No-show</option>
                  </select>
                </label>
                <label className="grid gap-1 text-xs font-semibold text-muted">Starts after
                  <input className="desk-input" type="datetime-local" value={filters.starts_at ?? ""} onChange={(event) => setFilter("starts_at", event.target.value)} />
                </label>
                <label className="grid gap-1 text-xs font-semibold text-muted">Ends before
                  <input className="desk-input" type="datetime-local" value={filters.ends_at ?? ""} onChange={(event) => setFilter("ends_at", event.target.value)} />
                </label>
              </div>
              {bookings.isLoading ? <Skeleton className="h-40 w-full" /> : null}
              {bookings.error ? <p className="text-sm text-danger" role="alert">{errorText(bookings.error)}</p> : null}
              {bookings.data && !bookings.data.results.length ? <EmptyState title="No matching bookings" description="Bookings for this space will appear here." /> : null}
              {bookings.data?.results.length ? (
                <div className="grid gap-3">
                  {bookings.data.results.map((booking) => (
                    <article className="rounded-xl border border-line bg-bg p-3" key={booking.id}>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div><h4 className="title-section">{booking.name}</h4><p className="mt-1 font-mono text-xs text-muted">{bookingTime(booking)}</p></div>
                        <StatusBadge status={booking.status} />
                      </div>
                      <div className="mt-2 text-sm"><a className="block break-all hover:underline" href={"mailto:" + booking.email}>{booking.email}</a><a className="block text-muted hover:underline" href={"tel:" + booking.phone}>{booking.phone}</a></div>
                      <details className="mt-3 rounded-lg border border-line bg-panel p-3">
                        <summary className="cursor-pointer text-sm font-semibold text-ink">View custom answers</summary>
                        <div className="mt-3"><CustomAnswersView snapshot={booking.custom_answers} /></div>
                      </details>
                      {access.manager ? <PaymentReconcileActions
                        makerspaceId={makerspaceId}
                        payment={booking.payment}
                        invalidateKeys={[
                          ["booking-space", spaceId, "bookings"],
                          ["booking-space", spaceId],
                        ]}
                      /> : null}
                      {space.staff_tools_enabled ? <BookingReservationEditor key={`${booking.id}-${booking.starts_at}-${JSON.stringify(booking.custom_answers)}-${booking.note}`} space={space} booking={booking} /> : null}
                      <BookingActions undoEnabled={space.staff_tools_enabled} booking={booking} onAction={(nextAction) => setPendingAction({ booking, action: nextAction })} />
                    </article>
                  ))}
                </div>
              ) : null}
              {bookings.data ? <div className="mt-3 flex items-center justify-between gap-2"><span className="font-mono text-xs text-muted">Page {page}</span><div className="flex gap-2"><button className="desk-button" type="button" disabled={!bookings.data.previous} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button><button className="desk-button" type="button" disabled={!bookings.data.next} onClick={() => setPage((value) => value + 1)}>Next</button></div></div> : null}
            </section> : null}
            </div>
            </> : null}
            {actionError ? <p className="text-sm text-danger" role="alert">{errorText(actionError)}</p> : null}
          </div>
        ) : null}
      </DetailDrawer>
      <ConfirmDialog
        open={pendingAction !== null}
        title={pendingAction ? actionLabel(pendingAction.action) : "Update booking"}
        message={pendingAction ? actionLabel(pendingAction.action) + " for " + pendingAction.booking.name + "?" : ""}
        confirmLabel={pendingAction ? actionLabel(pendingAction.action) : "Confirm"}
        tone={pendingAction?.action === "approve" || pendingAction?.action === "complete" ? "default" : "danger"}
        pending={action.isPending}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => pendingAction && action.mutate({ bookingId: pendingAction.booking.id, action: pendingAction.action }, { onSuccess: () => setPendingAction(null), onError: () => setPendingAction(null) })}
      />
      <ConfirmDialog open={confirmDeactivate} title="Deactivate space" message="The public page will hide this space and no new bookings can be submitted or approved." confirmLabel="Deactivate" tone="danger" pending={deactivate.isPending} onCancel={() => setConfirmDeactivate(false)} onConfirm={() => deactivate.mutate(undefined, { onSuccess: () => setConfirmDeactivate(false), onError: () => setConfirmDeactivate(false) })} />
    </>
  );
}

function BookingActions({ booking, onAction, undoEnabled }: { undoEnabled?: boolean; booking: Booking; onAction: (action: BookingAction) => void }) {
  const ended = new Date(booking.ends_at) <= new Date();
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {undoEnabled && booking.restore_until && new Date(booking.restore_until) > new Date() ? <button className="desk-button" type="button" onClick={() => onAction("restore")}>Undo cancellation</button> : null}
      {booking.status === "pending" ? <><button className="desk-button-success" type="button" onClick={() => onAction("approve")}>Approve</button><button className="desk-button-danger" type="button" onClick={() => onAction("reject")}>Reject</button></> : null}
      {["pending", "confirmed"].includes(booking.status) && !booking.arrived_at ? <button className="desk-button-danger" type="button" onClick={() => onAction("cancel")}>Cancel</button> : null}
      {booking.status === "confirmed" && ended ? <><button className="desk-button-success" type="button" onClick={() => onAction("complete")}>Complete</button>{!booking.arrived_at ? <button className="desk-button-warn" type="button" onClick={() => onAction("no-show")}>No-show</button> : null}</> : null}
    </div>
  );
}
