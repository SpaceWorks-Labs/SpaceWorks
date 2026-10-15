import { useEffect, useState } from "react";

import { ConfirmDialog, StatCard, StatusBadge } from "../../components/ui";
import { DetailLayout } from "../../components/layouts";
import { EventAtAGlance, EventOverview } from "./EventOverview";
import { EventSettings } from "./EventSettings";
import { EventCheckInOperator } from "./EventCheckInOperator";
import { opsQueryState, useOpsTabs, opsStatusLabel } from "./opsPresentation";
import { EventInvitesPanel } from "./EventInvitesPanel";
import { EventTicketsPanel } from "./EventTicketsPanel";
import { EventPromosPanel } from "./EventPromosPanel";
import { EventCollaborators } from "./EventCollaborators";
import { EventOrganizers } from "./EventOrganizers";
import { emptyEventForm, payloadFor, valuesFor } from "./EventFormFields";
import { EventFeedbackPanel } from "./EventFeedbackPanel";
import { EventRegistrationRoster } from "./EventRegistrationRoster";
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
  const [values, setValues] = useState(emptyEventForm);
  const [confirm, setConfirm] = useState<Action | null>(null);
  const update = useUpdateEvent(makerspaceId, eventId);
  const publish = usePublishEvent(makerspaceId, eventId);
  const cancel = useCancelEvent(makerspaceId, eventId);
  const complete = useCompleteEvent(makerspaceId, eventId);
  const invalidateEvent = useEventInvalidation(makerspaceId, eventId);

  useEffect(() => { if (event) setValues(valuesFor(event)); }, [event?.updated_at]);
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
  const recurring = series ? onOpenSeries && seriesId ? <button type="button" className="rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink hover:bg-info-soft" onClick={() => onOpenSeries(seriesId)}>Recurring · {series.title}</button>
    : <span className="rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink">Recurring · {series.title}</span> : null;
  const tabs = useOpsTabs("eventTab", [
    { key: "overview", label: "Overview" },
    { key: "registrations", label: "Registrations", count: event ? Object.values(event.registration_counts).reduce((sum, count) => sum + count, 0) : undefined },
    ...(event?.status === "published" || event?.status === "completed" ? [{ key: "checkin", label: "Check-in" }] : []),
    ...(ticketing.some(value => ["events.invites", "events.ticket_types", "events.promo_codes"].includes(value)) ? [{ key: "tickets", label: "Tickets & invites" }] : []),
    { key: "feedback", label: "Feedback" }, { key: "team", label: "Team" }, { key: "settings", label: "Settings" },
  ], "overview");
  return <>
    <div onClickCapture={tabs.onClickCapture}>
      <DetailLayout title={event?.title ?? "Event details"} back={{ label: "All events", onClick: onClose }}
        identity={event ? { kind: "date", date: event.starts_at } : undefined}
        status={event ? <StatusBadge domain="event" status={event.status} label={opsStatusLabel(event.status)} /> : undefined}
        meta={event ? [...(recurring ? [recurring] : []), event.is_public ? "Public" : "Private", event.location, `${event.registration_counts.registered + event.registration_counts.attended} / ${event.capacity || "unlimited"} going`] : undefined}
        state={opsQueryState(eventQuery, "event")} tabs={tabs.tabs} activeTab={tabs.active}
        actions={{ primary: event?.status === "draft" ? { label: "Publish", confirms: true, onClick: () => setConfirm("publish") }
          : event?.status === "published" ? { label: "Open check-in", targetsTab: "checkin", onClick: () => tabs.select("checkin") }
          : event?.status === "completed" ? { label: "View feedback", targetsTab: "feedback", onClick: () => tabs.select("feedback") } : undefined,
          // Ending an event is routine on event day, so it sits one click away in the header, not only in Settings.
          overflow: event?.status === "published" ? [{ label: "Complete event", confirms: true, onClick: () => setConfirm("complete") },
            { label: "Cancel event", confirms: true, tone: "danger", onClick: () => setConfirm("cancel") }] : undefined }}
        banner={readOnly ? { size: "banner", tone: "warn", lead: `This event is ${event?.status}. It can’t be edited.` } : undefined}
        danger={tabs.active === "settings" && event?.status === "published" ? [{ title: "Cancel event", consequence: "Registrants are notified and registration closes.", action: { label: "Cancel event", onClick: () => setConfirm("cancel") } }] : []}
        aside={event && tabs.active === "overview" ? <EventAtAGlance event={event} onCheckIn={() => tabs.select("checkin")} /> : undefined}
        main={event ? <div className="grid gap-6">
          {tabs.active === "overview" ? <EventOverview event={event} onRegistrations={() => tabs.select("registrations")} /> : null}
          <EventRegistrationRoster key={eventId} visible={tabs.active === "registrations"} event={event} makerspaceId={makerspaceId} offlineCheckInEnabled={event.offline_checkin_enabled} showCheckIn={false} />
          {event.status === "published" || event.status === "completed" ? <>
            {tabs.active === "checkin" ? <StatCard label="Checked in" value={event.registration_counts.attended} of={event.registration_counts.registered + event.registration_counts.attended || undefined} /> : null}
            <EventCheckInOperator visible={tabs.active === "checkin"} makerspaceId={makerspaceId} eventId={eventId} offlineEnabled={event.offline_checkin_enabled} />
          </> : null}
          {ticketing.includes("events.invites") ? <EventInvitesPanel key={eventId} visible={tabs.active === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
          {ticketing.includes("events.ticket_types") ? <EventTicketsPanel key={eventId} visible={tabs.active === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
          {ticketing.includes("events.promo_codes") ? <EventPromosPanel key={eventId} visible={tabs.active === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
          <EventFeedbackPanel visible={tabs.active === "feedback"} eventId={eventId} makerspaceId={makerspaceId} />
          <EventOrganizers visible={tabs.active === "team"} event={event} makerspaceId={makerspaceId} disabled={readOnly} />
          <EventCollaborators visible={tabs.active === "team"} makerspaceId={makerspaceId} eventId={eventId} />
          {tabs.active === "settings" ? <EventSettings event={event} makerspaceId={makerspaceId} values={values} setValues={setValues}
            save={saveOccurrence} pending={update.isPending} invalidate={invalidateEvent} resetField={field => update.mutate({ inherit_fields: [field] })} complete={() => setConfirm("complete")} /> : null}
          {actionError ? <p role="alert" className="text-sm text-danger">{eventErrorText(actionError)}</p> : null}
        </div> : null} />
    </div>
    <ConfirmDialog open={confirm !== null} title={`${confirm ? confirm[0].toUpperCase() + confirm.slice(1) : "Change"} event`} message={`Are you sure you want to ${confirm ?? "change"} this event?`} confirmLabel={confirm ? confirm[0].toUpperCase() + confirm.slice(1) : "Confirm"} tone={confirm === "cancel" ? "danger" : "default"} pending={lifecycle.isPending} onCancel={() => setConfirm(null)} onConfirm={() => lifecycle.mutate(undefined, { onSuccess: () => setConfirm(null), onError: () => setConfirm(null) })} />
  </>;
}
