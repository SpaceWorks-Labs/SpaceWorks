import { t } from "@lingui/core/macro";
import { EventReadinessPanel, EventDayPanel } from "./eventProgramme";
import { useEffect, useState } from "react";

import { ConfirmDialog, StatusBadge } from "../../components/ui";
import { DetailLayout } from "../../components/layouts";
import { EventAtAGlance, EventOverview } from "./EventOverview";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";
import { EventOrganizationAudience } from "./EventOrganizationAudience";
import { emptyEventForm, payloadFor, valuesFor } from "./EventFormFields";
import { EventRegistrationRoster } from "./EventRegistrationRoster";
import { usePriceDropCheck } from "./priceDrop/usePriceDropCheck";
import { EventCheckInTab } from "./EventCheckInTab";
import { EventDrawerMore } from "./EventDrawerMore";
import { EventEssentialsEditor } from "./EventEssentialsEditor";
import { eventDrawerSurfaces, useEventDrawerTabs } from "./eventDrawerTabs";
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
import { EventProgrammePanel } from "./eventProgramme/EventProgrammePanel";
import { EventAddonPanel } from "./eventProgramme/EventAddonPanel";
import { EventParticipationSection } from "./eventParticipation/EventParticipationSection";
import { ProgrammeSessionBoundary } from "./eventProgramme/sessionScope";
import { ScreenHelp } from "../help/HelpLink";

type Action = "publish" | "cancel" | "complete";

export function EventDrawer({ eventId, makerspaceId, onClose, onOpenSeries, enabledFeatures = [], enabledModules = [] }: {
  eventId: number;
  makerspaceId: number;
  onClose: () => void;
  /** Opens the occurrence's recurring series (the "Recurring · <series>" badge links there when set). */
  onOpenSeries?: (seriesId: number) => void;
  enabledFeatures?: string[];
  enabledModules?: string[];
}) {
  const eventQuery = useEvent(eventId);
  const event = eventQuery.data;
  const access = eventAccess(event ?? { staff_permissions: [], can_manage_staff: false });
  const [values, setValues] = useState(emptyEventForm);
  const [websitePublication, setWebsitePublication] = useState<{ publish_website: boolean; website_revision?: number } | undefined>();
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
  // Lane L24: a cheaper event price may owe paid seats without a ticket type a refund.
  const drop = usePriceDropCheck(makerspaceId);
  // Sends only the fields that changed, so a grant-limited editor never sends what they may not touch.
  const saveOccurrence = async (onSaved?: () => void) => {
    if (!event) return;
    const next = payloadFor(values);
    const current = payloadFor(valuesFor(event));
    const changed = Object.fromEntries(
      Object.entries(next).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(current[key as keyof typeof current])),
    ) as EventPatch;
    if (!Object.keys(changed).length) { onSaved?.(); return; }
    const cheaper = changed.payment_amount !== undefined && Number(changed.payment_amount) < Number(event.payment_amount);
    if (cheaper && !(await drop.check(`/admin/events/${event.id}/`, "PATCH", changed))) return;
    if (onSaved) update.mutate(changed, { onSuccess: onSaved }); else update.mutate(changed);
  };

  const series = event?.series_summary;
  const seriesId = series?.id;
  const recurring = series ? onOpenSeries && seriesId ? <button type="button" className="relative rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink before:absolute before:-inset-x-1 before:-inset-y-3 hover:bg-info-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" onClick={() => onOpenSeries(seriesId)}>{t`Recurring · ${series.title}`}</button>
    : <span className="rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink">{t`Recurring · ${series.title}`}</span> : null;
  // Every tab and section is gated on the same event staff grant the API enforces (eventDrawerSurfaces).
  const surfaces = eventDrawerSurfaces(event, access, enabledFeatures, enabledModules);
  const { checkable, sections } = surfaces;
  const tabs = useEventDrawerTabs([
    { key: "overview", label: t`Overview` },
    ...(access.registrations ? [{ key: "registrations", label: t`Registrations`, count: event ? Object.values(event.registration_counts).reduce((sum, count) => sum + count, 0) : undefined }] : []),
    ...(surfaces.checkInTab ? [{ key: "checkin", label: t`Check-in` }] : []),
  ], sections, surfaces.credentials.label);
  const canSaveEssentials = (access.edit || access.publish) && !readOnly;
  return <ProgrammeSessionBoundary error={eventQuery.error}>
    <div onClickCapture={tabs.onClickCapture}>
      <DetailLayout title={event?.title ?? t`Event details`} back={{ label: t`All events`, onClick: onClose }}
        identity={event ? { kind: "date", date: event.starts_at } : undefined}
        status={event ? <StatusBadge domain="event" status={event.status} label={opsStatusLabel(event.status)} /> : undefined}
        meta={event ? [...(recurring ? [recurring] : []), event.is_public ? "Public" : "Private", event.location, `${event.registration_counts.registered + event.registration_counts.attended} / ${event.capacity || "unlimited"} going`] : undefined}
        state={opsQueryState(eventQuery, "event")} tabs={tabs.tabs} activeTab={tabs.active}
        actions={{ primary: event?.status === "draft" && access.publish ? { label: t`Publish`, confirms: true, onClick: () => setConfirm("publish") }
          : event?.status === "published" && access.checkIn ? { label: t`Open check-in`, targetsTab: "checkin", onClick: () => tabs.select("checkin") }
          : event?.status === "completed" && sections.feedback && tabs.section !== "feedback" ? { label: t`View feedback`, onClick: () => tabs.select("feedback") } : undefined,
          // Ending an event is routine on event day, so it sits one click away in the header, not only in Settings.
          overflow: event?.status === "published" && access.publish ? [{ label: t`Complete event`, confirms: true, onClick: () => setConfirm("complete") },
            { label: t`Cancel event`, confirms: true, tone: "danger", onClick: () => setConfirm("cancel") }] : undefined }}
        banner={readOnly ? { size: "banner", tone: "warn", lead: `This event is ${event?.status}. It can’t be edited.` } : undefined}
        danger={tabs.section === "settings" && event?.status === "published" && access.publish ? [{ title: t`Cancel event`, consequence: "Registrants are notified and registration closes.", action: { label: t`Cancel event`, onClick: () => setConfirm("cancel") } }] : []}
        aside={event && tabs.active === "overview" ? <EventAtAGlance event={event} onCheckIn={checkable && access.checkIn ? () => tabs.select("checkin") : undefined} /> : undefined}
        main={event ? <div className="grid gap-6">
          {tabs.section && sections[tabs.section] ? <ScreenHelp screen={`events.${tabs.section}`} /> : null}
          {tabs.active === "overview" ? <>
            {canSaveEssentials ? <EventEssentialsEditor event={event} access={access} values={values} setValues={setValues} save={saveOccurrence} pending={update.isPending} /> : null}
            <EventOrganizationAudience event={event} pending={update.isPending} onReconfigure={access.edit ? () => update.mutate({ registration_audience: "participating_organizations" }) : undefined} />
            <EventReadinessPanel eventId={eventId} />
            {access.checkIn ? <EventDayPanel eventId={eventId} /> : null}
            <EventOverview event={event} onRegistrations={access.registrations ? () => tabs.select("registrations") : undefined} />
          </> : null}
          {access.registrations ? <EventRegistrationRoster key={eventId} visible={tabs.active === "registrations"} event={event} makerspaceId={makerspaceId} offlineCheckInEnabled={event.offline_checkin_enabled} showCheckIn={false} /> : null}
          {surfaces.checkInTab ? <EventCheckInTab event={event} makerspaceId={makerspaceId} active={tabs.active === "checkin"} checkable={checkable} canManageStation={access.manager} /> : null}
          <EventDrawerMore event={event} makerspaceId={makerspaceId} access={access} surfaces={surfaces} section={tabs.section} sectionTabs={tabs.sectionTabs}
            readOnly={readOnly} onWebsitePublication={setWebsitePublication}
            settings={{ values, setValues, save: () => { void saveOccurrence(); }, pending: update.isPending, invalidate: invalidateEvent, resetField: field => update.mutate({ inherit_fields: [field] }), complete: () => setConfirm("complete") }} />
          {tabs.section && sections[tabs.section] ? <EventProgrammePanel event={event} makerspaceId={makerspaceId} section={tabs.section} access={access} features={enabledFeatures} /> : null}
          {(tabs.section === "stage-forms" || tabs.section === "reimbursements") && sections[tabs.section]
            ? <EventAddonPanel key={`${event.id}:${tabs.section}`} event={event} makerspaceId={makerspaceId} section={tabs.section} access={access} /> : null}
          {tabs.section && sections[tabs.section] ? <EventParticipationSection key={`${event.id}:l21a:${tabs.section}`} event={event} section={tabs.section} access={access} features={enabledFeatures} /> : null}
          {actionError ? <p role="alert" className="text-sm text-danger">{eventErrorText(actionError)}</p> : null}
        </div> : null} />
    </div>
    {drop.dialog}
    <ConfirmDialog open={confirm !== null} title={`${confirm ? confirm[0].toUpperCase() + confirm.slice(1) : "Change"} event`} message={t`Are you sure you want to ${confirm ?? "change"} this event?`} confirmLabel={confirm ? confirm[0].toUpperCase() + confirm.slice(1) : t`Confirm`} tone={confirm === "cancel" ? "danger" : "default"} pending={lifecycle.isPending} onCancel={() => setConfirm(null)} onConfirm={() => { const options = { onSettled: () => setConfirm(null) }; if (confirm === "publish") publish.mutate(websitePublication, options); else lifecycle.mutate(undefined, options); }} />
  </ProgrammeSessionBoundary>;
}
