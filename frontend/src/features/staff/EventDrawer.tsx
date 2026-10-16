import { useEffect, useState } from "react";

import { ConfirmDialog, StatCard, StatusBadge } from "../../components/ui";
import { DetailLayout } from "../../components/layouts";
import { EventAtAGlance, EventOverview } from "./EventOverview";
import { EventSettings } from "./EventSettings";
import { opsQueryState, useOpsTabs, opsStatusLabel } from "./opsPresentation";
import { EventWebsiteEditor } from "./EventWebsiteEditor";
import { EventWebsitePublication } from "./EventWebsitePublication";
import { EventOrganizationAudience } from "./EventOrganizationAudience";
import { EventDuplicateAction } from "./EventDuplicateAction";
import { EventInvitesPanel } from "./EventInvitesPanel";
import { EventBroadcastsPanel } from "./EventBroadcastsPanel";
import { EventAnalyticsPanel } from "./EventAnalyticsPanel";
import { EventTicketsPanel } from "./EventTicketsPanel";
import { EventPromosPanel } from "./EventPromosPanel";
import { EventCollaborators } from "./EventCollaborators";
import { EventOrganizers } from "./EventOrganizers";
import { emptyEventForm, payloadFor, valuesFor } from "./EventFormFields";
import { EventFeedbackPanel } from "./EventFeedbackPanel";
import { EventFeedbackResponses } from "./EventFeedbackResponses";
import { EventRegistrationRoster } from "./EventRegistrationRoster";
import { EventCheckInOperator } from "./EventCheckInOperator";
import { EventCertificateDesigner } from "./EventCertificateDesigner";
import { EventBadgeActions } from "./EventBadgeActions";
import { EventStaffAccess } from "./EventStaffAccess";
import { eventAccess } from "./eventStaffPermissions";
import {
  useCancelEvent,
  useCompleteEvent,
  useEvent,
  useEventInvalidation,
  usePublishEvent,
  useUpdateEvent,
} from "./eventsApi";
import type { EventPatch } from "./eventsApi";
import { eventErrorText } from "./eventUi";

type Action = "publish" | "cancel" | "complete";

export function EventDrawer({ eventId, makerspaceId, onClose, onOpenSeries }: {
  eventId: number;
  makerspaceId: number;
  onClose: () => void;
  /** Opens the occurrence's recurring series (the "Recurring · <series>" badge links there when set). */
  onOpenSeries?: (seriesId: number) => void;
}) {
  const eventQuery = useEvent(eventId);
  const event = eventQuery.data;
  const access = eventAccess(event ?? { staff_permissions: [], can_manage_staff: false });
  const [values, setValues] = useState(emptyEventForm);
  const [websitePublication, setWebsitePublication] = useState<{ publish_website: boolean; website_revision?: number } | undefined>();
  const websiteTarget = { kind: "events" as const, id: eventId, makerspaceId };
  const [confirm, setConfirm] = useState<Action | null>(null);
  const update = useUpdateEvent(makerspaceId, eventId);
  const publish = usePublishEvent(makerspaceId, eventId);
  const cancel = useCancelEvent(makerspaceId, eventId);
  const complete = useCompleteEvent(makerspaceId, eventId);
  const invalidateEvent = useEventInvalidation(makerspaceId, eventId);

  useEffect(() => { if (event) setValues(valuesFor(event)); }, [event?.updated_at]);
  useEffect(() => setWebsitePublication(undefined), [eventId]);
  const lifecycle = confirm === "publish" ? publish : confirm === "cancel" ? cancel : complete;
  const readOnly = event?.status === "cancelled" || event?.status === "completed";
  const actionError = update.error || publish.error || cancel.error || complete.error;
  const saveOccurrence = () => {
    if (!event) return;
    const next = payloadFor(values);
    const current = payloadFor(valuesFor(event));
    const changed = Object.fromEntries(
      Object.entries(next).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(current[key as keyof typeof current])),
    ) as EventPatch;
    update.mutate(changed);
  };

  const ticketing = event?.ticketing_features ?? [];
  const series = event?.series_summary;
  const seriesId = series?.id;
  const recurring = series ? onOpenSeries && seriesId ? <button type="button" className="relative rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink before:absolute before:-inset-x-1 before:-inset-y-3 hover:bg-info-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" onClick={() => onOpenSeries(seriesId)}>Recurring · {series.title}</button>
    : <span className="rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink">Recurring · {series.title}</span> : null;
  // Every tab is gated on the same event staff grant the API enforces (eventStaffPermissions):
  // a grant-only staffer sees only the tabs whose actions they actually hold.
  const checkable = event?.status === "published" || event?.status === "completed";
  const showInvites = access.invitations && ticketing.includes("events.invites");
  const showTicketTypes = access.manager && ticketing.includes("events.ticket_types");
  const showPromos = access.manager && ticketing.includes("events.promo_codes");
  const showWebsite = ticketing.includes("events.website") && (access.edit || access.publish);
  const showBroadcasts = access.registrations && Boolean(event?.broadcasts_enabled);
  const showAnalytics = Boolean(event?.report_features?.includes("analytics"));
  const showFeedback = access.edit || access.registrations;
  const showSettings = access.edit || access.publish;
  const tabs = useOpsTabs("eventTab", [
    { key: "overview", label: "Overview" },
    ...(access.registrations ? [{ key: "registrations", label: "Registrations", count: event ? Object.values(event.registration_counts).reduce((sum, count) => sum + count, 0) : undefined }] : []),
    ...(checkable && access.checkIn ? [{ key: "checkin", label: "Check-in" }] : []),
    ...(showInvites || showTicketTypes || showPromos ? [{ key: "tickets", label: "Tickets & invites" }] : []),
    ...(showFeedback ? [{ key: "feedback", label: "Feedback" }] : []),
    ...(showBroadcasts ? [{ key: "broadcasts", label: "Broadcasts" }] : []),
    ...(showAnalytics ? [{ key: "analytics", label: "Analytics" }] : []),
    ...(showWebsite ? [{ key: "website", label: "Website" }] : []),
    ...(access.manager ? [{ key: "team", label: "Team" }] : []),
    ...(showSettings ? [{ key: "settings", label: "Settings" }] : []),
  ], "overview");
  return <>
    <div onClickCapture={tabs.onClickCapture}>
      <DetailLayout title={event?.title ?? "Event details"} back={{ label: "All events", onClick: onClose }}
        identity={event ? { kind: "date", date: event.starts_at } : undefined}
        status={event ? <StatusBadge domain="event" status={event.status} label={opsStatusLabel(event.status)} /> : undefined}
        meta={event ? [...(recurring ? [recurring] : []), event.is_public ? "Public" : "Private", event.location, `${event.registration_counts.registered + event.registration_counts.attended} / ${event.capacity || "unlimited"} going`] : undefined}
        state={opsQueryState(eventQuery, "event")} tabs={tabs.tabs} activeTab={tabs.active}
        actions={{ primary: event?.status === "draft" && access.publish ? { label: "Publish", confirms: true, onClick: () => setConfirm("publish") }
          : event?.status === "published" && access.checkIn ? { label: "Open check-in", targetsTab: "checkin", onClick: () => tabs.select("checkin") }
          : event?.status === "completed" && showFeedback ? { label: "View feedback", targetsTab: "feedback", onClick: () => tabs.select("feedback") } : undefined,
          // Ending an event is routine on event day, so it sits one click away in the header, not only in Settings.
          overflow: event?.status === "published" && access.publish ? [{ label: "Complete event", confirms: true, onClick: () => setConfirm("complete") },
            { label: "Cancel event", confirms: true, tone: "danger", onClick: () => setConfirm("cancel") }] : undefined }}
        banner={readOnly ? { size: "banner", tone: "warn", lead: `This event is ${event?.status}. It can’t be edited.` } : undefined}
        danger={tabs.active === "settings" && event?.status === "published" && access.publish ? [{ title: "Cancel event", consequence: "Registrants are notified and registration closes.", action: { label: "Cancel event", onClick: () => setConfirm("cancel") } }] : []}
        aside={event && tabs.active === "overview" ? <EventAtAGlance event={event} onCheckIn={() => tabs.select("checkin")} /> : undefined}
        main={event ? <div className="grid gap-6">
          {tabs.active === "overview" ? <>
            <EventOrganizationAudience event={event} pending={update.isPending} onReconfigure={access.edit ? () => update.mutate({ registration_audience: "participating_organizations" }) : undefined} />
            <EventOverview event={event} onRegistrations={() => tabs.select("registrations")} />
          </> : null}
          {access.registrations ? <EventRegistrationRoster key={eventId} visible={tabs.active === "registrations"} event={event} makerspaceId={makerspaceId} offlineCheckInEnabled={event.offline_checkin_enabled} showCheckIn={false} /> : null}
          {checkable && access.checkIn ? <>
            {tabs.active === "checkin" ? <StatCard label="Checked in" value={event.registration_counts.attended} of={event.registration_counts.registered + event.registration_counts.attended || undefined} /> : null}
            <EventCheckInOperator visible={tabs.active === "checkin"} makerspaceId={makerspaceId} eventId={eventId} offlineEnabled={event.offline_checkin_enabled} canManageStation={access.manager} />
          </> : null}
          {showInvites ? <EventInvitesPanel key={eventId} visible={tabs.active === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
          {showTicketTypes ? <EventTicketsPanel key={eventId} visible={tabs.active === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
          {showPromos ? <EventPromosPanel key={eventId} visible={tabs.active === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
          {tabs.active === "feedback" ? access.edit ? <>
            <EventFeedbackPanel eventId={eventId} makerspaceId={makerspaceId} canViewResponses={access.registrations} canManageCertificates={access.manager} />
            {ticketing.includes("events.certificate_designer") ? <EventCertificateDesigner key={`certificate:${eventId}`} makerspaceId={makerspaceId} eventId={eventId} /> : null}
          </> : access.registrations ? <EventFeedbackResponses eventId={eventId} makerspaceId={makerspaceId} responseCount={0} canManageCertificates={false} /> : null : null}
          {showBroadcasts && tabs.active === "broadcasts" ? <EventBroadcastsPanel makerspaceId={makerspaceId} eventId={eventId} /> : null}
          {showAnalytics && tabs.active === "analytics" ? <EventAnalyticsPanel makerspaceId={makerspaceId} eventId={eventId} endsAt={event.ends_at} features={event.report_features ?? []} /> : null}
          {/* Kept mounted (hidden) so the "publish website with event" choice the Publish action reads never goes stale. */}
          {showWebsite && access.publish && event.status === "draft" ? <div hidden={tabs.active !== "website"}><EventWebsitePublication key={eventId} target={websiteTarget} onChange={setWebsitePublication} /></div> : null}
          {showWebsite && tabs.active === "website" ? <EventWebsiteEditor key={`event:${eventId}`} target={websiteTarget} canEdit={access.edit} canPublish={access.publish} status={event.status} /> : null}
          {access.manager ? <>
            <EventOrganizers visible={tabs.active === "team"} event={event} makerspaceId={makerspaceId} disabled={readOnly} />
            <EventCollaborators visible={tabs.active === "team"} makerspaceId={makerspaceId} eventId={eventId} />
            {tabs.active === "team" ? <EventStaffAccess target={{ kind: "event", id: eventId }} /> : null}
          </> : null}
          {showSettings && tabs.active === "settings" ? <>
            {access.edit ? <div className="flex flex-wrap gap-2"><EventDuplicateAction event={event} makerspaceId={makerspaceId} /></div> : null}
            <EventSettings event={event} makerspaceId={makerspaceId} values={values} setValues={setValues}
              save={saveOccurrence} pending={update.isPending} invalidate={invalidateEvent} resetField={field => update.mutate({ inherit_fields: [field] })} complete={() => setConfirm("complete")} />
            {/* Without the roster, an editor still owns the badge template; printing stays with check-in staff. */}
            {!access.registrations && access.edit ? <EventBadgeActions event={event} makerspaceId={makerspaceId} selectedIds={[]} includeAttended={false} onIncludeAttended={() => {}} canPrint={false} /> : null}
          </> : null}
          {actionError ? <p role="alert" className="text-sm text-danger">{eventErrorText(actionError)}</p> : null}
        </div> : null} />
    </div>
    <ConfirmDialog open={confirm !== null} title={`${confirm ? confirm[0].toUpperCase() + confirm.slice(1) : "Change"} event`} message={`Are you sure you want to ${confirm ?? "change"} this event?`} confirmLabel={confirm ? confirm[0].toUpperCase() + confirm.slice(1) : "Confirm"} tone={confirm === "cancel" ? "danger" : "default"} pending={lifecycle.isPending} onCancel={() => setConfirm(null)} onConfirm={() => { const options = { onSettled: () => setConfirm(null) }; if (confirm === "publish") publish.mutate(websitePublication, options); else lifecycle.mutate(undefined, options); }} />
  </>;
}
