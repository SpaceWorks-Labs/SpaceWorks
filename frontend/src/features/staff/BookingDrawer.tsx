import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ConfirmDialog, ErrorBlock, Modal, StatusBadge } from "../../components/ui";
import { DetailLayout } from "../../components/layouts";
import { opsQueryState, useOpsTabs } from "./opsPresentation";
import { BookingAgenda } from "./BookingAgenda";
import { BookingRequests } from "./BookingRequests";
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

type PendingAction = { booking: Booking; action: BookingAction };

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function actionLabel(action: BookingAction) {
  return {
    approve: "Approve",
    reject: "Reject",
    cancel: "Cancel booking",
    complete: "Complete",
    "no-show": "Mark no-show",
  }[action];
}

export function BookingDrawer({ makerspaceId, spaceId, onClose, recurringEnabled = false, initialCreateOpen = false }: {
  recurringEnabled?: boolean;
  /** Open the New booking form on arrival (the bookings list "New booking" space picker). */
  initialCreateOpen?: boolean;
  makerspaceId: number;
  spaceId: number;
  onClose: () => void;
}) {
  const spaceQuery = useBookableSpace(spaceId);
  const space = spaceQuery.data;
  const [params, setParams] = useSearchParams();
  const list = useUrlListState({ page: "1", status: "", starts_at: "", ends_at: "", ordering: "starts_at" }, `booking-${spaceId}.`);
  const { page, setPage } = list;
  const filters: BookingFilters = { ...list.values, status: list.values.status as BookingFilters["status"], booking_id: Number(params.get("space")) === spaceId ? Number(params.get("booking")) || undefined : undefined };
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const bookings = useSpaceBookings(spaceId, filters, page, list.values.ordering);
  const update = useUpdateBookableSpace(makerspaceId, spaceId);
  const deactivate = useDeactivateBookableSpace(makerspaceId, spaceId);
  const action = useBookingAction(makerspaceId, spaceId);

  const setFilter = <K extends keyof BookingFilters>(key: K, value: BookingFilters[K]) => {
    list.setFilter(key, String(value ?? ""));
  };
  const actionError = update.error || deactivate.error || action.error;
  const tabs = useOpsTabs("bookingTab", [{ key: "calendar", label: "Calendar" },
    { key: "requests", label: "Requests", count: bookings.data?.count }, { key: "settings", label: "Settings" }],
    params.get("booking") ? "requests" : "calendar");
  const [createOpen, setCreateOpen] = useState(initialCreateOpen);
  const openBooking = (bookingId: number) => setParams(current => {
    const next = new URLSearchParams(current);
    next.set("space", String(spaceId));
    next.set("booking", String(bookingId));
    next.set("booking-" + spaceId + ".page", "1");
    next.set("bookingTab", "requests");
    return next;
  });

  return (
    <>
      <div onClickCapture={tabs.onClickCapture}>
        <DetailLayout title={space?.name ?? "Space details"} back={{ label: "Bookings", onClick: onClose }}
          identity={{ kind: "icon", icon: "Calendar", tone: "info" }}
          state={opsQueryState(spaceQuery, "this space")} tabs={tabs.tabs} activeTab={tabs.active}
          status={space ? <StatusBadge status={space.is_active ? "active" : "inactive"} label={space.is_active ? "Active" : "Inactive"} /> : undefined}
          meta={space ? [space.location, space.effective_requester_notifications_enabled ? "Requester emails on" : "Requester emails off"] : undefined}
          actions={space?.is_active ? { primary: { label: "New booking", onClick: () => setCreateOpen(true) } } : undefined}
          danger={space?.is_active && tabs.active === "settings" ? [{ title: "Deactivate space",
            consequence: "The public page will hide this space and no new bookings can be submitted or approved.",
            action: { label: "Deactivate space", confirms: true, tone: "danger", onClick: () => setConfirmDeactivate(true) } }] : undefined}
          main={space ? <div className="grid gap-6">
            {tabs.active === "settings" ? <>
              <BookableSpaceForm makerspaceId={makerspaceId} mode="settings" key={space.updated_at} initialValues={valuesForSpace(space)}
                onSubmit={payload => update.mutate(payload)} pending={update.isPending}
                error={update.error ? errorText(update.error) : undefined} submitLabel="Save changes" disabled={!space.is_active} />
              {!space.is_active ? <p className="text-sm text-muted">This space is inactive and read-only.</p> : null}
            </> : tabs.active === "calendar" ? <BookingAgenda spaceId={spaceId} onOpen={openBooking} /> : <BookingRequests makerspaceId={makerspaceId} spaceId={spaceId} bookings={bookings} list={list}
              filters={filters} setFilter={setFilter} page={page} setPage={setPage}
              onAction={(booking, nextAction) => setPendingAction({ booking, action: nextAction })} />}
            {actionError ? <ErrorBlock error={actionError} /> : null}
          </div> : null} />
      </div>
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New booking">
        {space && createOpen ? <StaffBookingForm recurringEnabled={recurringEnabled} makerspaceId={makerspaceId} space={space} /> : null}
      </Modal>
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
