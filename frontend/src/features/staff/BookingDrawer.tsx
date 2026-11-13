import { t } from "@lingui/core/macro";
import { useContext, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { ConfirmDialog, ErrorBlock, Modal, SegmentedControl, StatusBadge } from "../../components/ui";
import { capabilityOn } from "../../lib/features";
import { StaffListContext } from "./StaffListContext";
import { StaffOrganizationBookingForm } from "./StaffOrganizationBookingForm";
import { DetailLayout } from "../../components/layouts";
import { opsQueryState, useOpsTabs } from "./opsPresentation";
import { BookingAgenda } from "./BookingAgenda";
import { BookingRequests } from "./BookingRequests";
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
import { BookingWebsiteEditor } from "./BookingWebsiteEditor";
import { BookingPassDesigner } from "./BookingPassDesigner";
import { BookingArrivalScanner } from "./BookingArrivalScanner";
import { BookingBroadcastsPanel } from "./BookingBroadcastsPanel";
import { bookingAccess } from "./bookingStaffPermissions";
import { BookingResourceAnalytics } from "./BookingResourceAnalytics";
import { BookingSpaceSettings } from "./BookingSpaceSettings";
import { BookingDecisionDialog } from "./BookingDecisionDialog";
import { BookingIssuesList } from "./BookingIssuesList";
import { SpacePhotosSection } from "./SpacePhotosSection";

/** Later lanes supply their separately authorized tab components through the `additionalTabs` slot. */
export type BookingDrawerTab = { id: string; label: string; content: ReactNode };
type PendingAction = { booking: Booking; action: BookingAction };

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

export function BookingDrawer({ makerspaceId, spaceId, onClose, recurringEnabled = false, initialCreateOpen = false, additionalTabs = [] }: {
  /** Later lanes supply their separately authorized tab components through this slot. */
  additionalTabs?: BookingDrawerTab[];
  recurringEnabled?: boolean;
  /** Open the New booking form on arrival (the bookings list "New booking" space picker). */
  initialCreateOpen?: boolean;
  makerspaceId: number;
  spaceId: number;
  onClose: () => void;
}) {
  const spaceQuery = useBookableSpace(spaceId);
  const space = spaceQuery.data;
  // A resource grant narrows the console: managers see everything, grantees only their granted surfaces.
  const access = bookingAccess(space);
  const [params, setParams] = useSearchParams();
  const list = useUrlListState({ page: "1", status: "", starts_at: "", ends_at: "", ordering: "starts_at" }, `booking-${spaceId}.`);
  const { page, setPage } = list;
  const filters: BookingFilters = { ...list.values, status: list.values.status as BookingFilters["status"], booking_id: Number(params.get("space")) === spaceId ? Number(params.get("booking")) || undefined : undefined };
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
  // Each optional surface is a tab only when the space enables it AND this actor may use it.
  const optionalTabs: BookingDrawerTab[] = space ? [
    ...(space.checkin_enabled && (access.manager || space.staff_permissions?.includes("check_in")) ? [{
      id: "check-in", label: t`Arrivals`, content: <BookingArrivalScanner key={spaceId} makerspaceId={makerspaceId} spaceId={spaceId} /> }] : []),
    ...(access.reservations && space.broadcasts_enabled ? [{
      id: "broadcasts", label: t`Broadcasts`, content: <BookingBroadcastsPanel makerspaceId={makerspaceId} spaceId={spaceId} /> }] : []),
    ...(space.report_features?.length ? [{
      id: "analytics", label: t`Analytics`, content: <BookingResourceAnalytics makerspaceId={makerspaceId} spaceId={spaceId} features={space.report_features} /> }] : []),
    ...(space.website_enabled && (access.edit || space.staff_permissions?.includes("publish_page")) ? [{
      id: "website", label: t`Website`, content: <BookingWebsiteEditor key={spaceId} space={space} /> }] : []),
    ...(space.passes_enabled && access.edit ? [{
      id: "passes", label: t`Pass designer`, content: <BookingPassDesigner key={spaceId} makerspaceId={makerspaceId} spaceId={spaceId} /> }] : []),
    ...additionalTabs,
  ] : additionalTabs;
  const tabs = useOpsTabs("bookingTab", [
    ...(access.reservations ? [{ key: "requests", label: t`Requests`, count: bookings.data?.count }, { key: "calendar", label: t`Calendar` }] : []),
    ...optionalTabs.map(tab => ({ key: tab.id, label: tab.label })),
    ...(access.reservations ? [{ key: "issues", label: t`Issues` }] : []),
    ...(access.manager || access.edit ? [{ key: "photos", label: t`Photos` }] : []),
    { key: "settings", label: access.manager || access.edit ? t`Settings` : t`Details` }],
    // Requests first: the basic path is apply -> review -> notify.
    !access.reservations ? optionalTabs[0]?.id ?? "settings" : "requests");
  const [createOpen, setCreateOpen] = useState(initialCreateOpen);
  // Decision 223 P2: a booking for a partner organization, behind `bookings.organization_bookings`.
  const organizations = capabilityOn(useContext(StaffListContext).makerspace, "bookings.organization_bookings");
  const [createFor, setCreateFor] = useState<"member" | "organization">("member");
  const openBooking = (bookingId: number) => setParams(current => {
    const next = new URLSearchParams(current);
    next.set("space", String(spaceId));
    next.set("booking", String(bookingId));
    next.set("booking-" + spaceId + ".page", "1");
    next.set("bookingTab", "requests");
    return next;
  });
  const optional = optionalTabs.find(tab => tab.id === tabs.active);

  return (
    <>
      <div onClickCapture={tabs.onClickCapture}>
        <DetailLayout title={space?.name ?? t`Space details`} back={{ label: t`Bookings`, onClick: onClose }}
          identity={{ kind: "icon", icon: "Calendar", tone: "info" }}
          state={opsQueryState(spaceQuery, "this space")} tabs={tabs.tabs} activeTab={tabs.active}
          status={space ? <StatusBadge status={space.is_active ? "active" : "inactive"} label={space.is_active ? t`Active` : t`Inactive`} /> : undefined}
          meta={space ? [space.location, space.effective_requester_notifications_enabled ? t`Requester emails on` : t`Requester emails off`] : undefined}
          actions={space?.is_active && access.reservations ? { primary: { label: t`New booking`, onClick: () => setCreateOpen(true) } } : undefined}
          danger={space?.is_active && access.manager && tabs.active === "settings" ? [{ title: t`Deactivate space`,
            consequence: "The public page will hide this space and no new bookings can be submitted or approved.",
            action: { label: t`Deactivate space`, confirms: true, tone: "danger", onClick: () => setConfirmDeactivate(true) } }] : undefined}
          main={space ? <div className="grid gap-6">
            {tabs.active === "settings" ? <BookingSpaceSettings makerspaceId={makerspaceId} space={space} access={access} update={update} />
              : optional ? optional.content
              : tabs.active === "calendar" ? <BookingAgenda spaceId={spaceId} onOpen={openBooking} />
              : tabs.active === "issues" ? <BookingIssuesList makerspaceId={makerspaceId} spaceId={spaceId} />
              : tabs.active === "photos" ? <SpacePhotosSection spaceId={spaceId} active={space.is_active} />
              : <BookingRequests makerspaceId={makerspaceId} spaceId={spaceId} space={space} canReconcile={access.manager} bookings={bookings} list={list}
                filters={filters} setFilter={setFilter} page={page} setPage={setPage}
                onAction={(booking, nextAction) => setPendingAction({ booking, action: nextAction })} />}
            {actionError ? <ErrorBlock error={actionError} /> : null}
          </div> : null} />
      </div>
      <Modal open={createOpen && access.reservations} onClose={() => setCreateOpen(false)} title={t`New booking`}>
        {space && createOpen && access.reservations && organizations ? <div className="mb-3"><SegmentedControl label={t`Who is this booking for?`} value={createFor}
          options={[{ value: "member", label: t`Member or house` }, { value: "organization", label: t`Organization` }]} onChange={value => setCreateFor(value as "member" | "organization")} /></div> : null}
        {space && createOpen && access.reservations && organizations && createFor === "organization" ? <StaffOrganizationBookingForm makerspaceId={makerspaceId} space={space} />
          : space && createOpen && access.reservations ? <StaffBookingForm recurringEnabled={recurringEnabled || Boolean(space.recurring_enabled)} makerspaceId={makerspaceId} space={space} /> : null}
      </Modal>
      <BookingDecisionDialog key={pendingAction ? `${pendingAction.booking.id}-${pendingAction.action}` : "none"}
        open={pendingAction?.action === "reject" || pendingAction?.action === "cancel"}
        action={pendingAction?.action === "reject" ? "reject" : "cancel"} bookerName={pendingAction?.booking.name ?? ""}
        pending={action.isPending} onCancel={() => setPendingAction(null)}
        onConfirm={reason => pendingAction && action.mutate({ bookingId: pendingAction.booking.id, action: pendingAction.action, reason },
          { onSuccess: () => setPendingAction(null), onError: () => setPendingAction(null) })} />
      <ConfirmDialog
        open={pendingAction !== null && pendingAction.action !== "reject" && pendingAction.action !== "cancel"}
        title={pendingAction ? actionLabel(pendingAction.action) : t`Update booking`}
        message={pendingAction ? actionLabel(pendingAction.action) + " for " + pendingAction.booking.name + "?" : ""}
        confirmLabel={pendingAction ? actionLabel(pendingAction.action) : t`Confirm`}
        tone={pendingAction?.action === "approve" || pendingAction?.action === "complete" || pendingAction?.action === "restore" ? "default" : "danger"}
        pending={action.isPending}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => pendingAction && action.mutate({ bookingId: pendingAction.booking.id, action: pendingAction.action }, { onSuccess: () => setPendingAction(null), onError: () => setPendingAction(null) })}
      />
      <ConfirmDialog open={confirmDeactivate} title={t`Deactivate space`} message={t`The public page will hide this space and no new bookings can be submitted or approved.`} confirmLabel={t`Deactivate`} tone="danger" pending={deactivate.isPending} onCancel={() => setConfirmDeactivate(false)} onConfirm={() => deactivate.mutate(undefined, { onSuccess: () => setConfirmDeactivate(false), onError: () => setConfirmDeactivate(false) })} />
    </>
  );
}
