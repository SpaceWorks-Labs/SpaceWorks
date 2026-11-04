import { Tabs, type Tab } from "../../components/ui";
import { EventSettings } from "./EventSettings";
import { EventWebsiteEditor } from "./EventWebsiteEditor";
import { EventWebsitePublication } from "./EventWebsitePublication";
import { EventDuplicateAction } from "./EventDuplicateAction";
import { EventInvitesPanel } from "./EventInvitesPanel";
import { EventBroadcastsPanel } from "./EventBroadcastsPanel";
import { EventAnalyticsPanel } from "./EventAnalyticsPanel";
import { EventTicketsPanel } from "./EventTicketsPanel";
import { EventPromosPanel } from "./EventPromosPanel";
import { EventOrderTools } from "./eventTicketing/EventOrderTools";
import { EventCollaborators } from "./EventCollaborators";
import { EventOrganizers } from "./EventOrganizers";
import { EventFeedbackPanel } from "./EventFeedbackPanel";
import { EventFeedbackResponses } from "./EventFeedbackResponses";
import { EventAudienceOrganizations } from "./EventAudienceOrganizations";
import { EventCertificateDesigner } from "./EventCertificateDesigner";
import { EventBadgeActions } from "./EventBadgeActions";
import { EventStaffAccess } from "./EventStaffAccess";
import { EventSpeakersPanel } from "./EventSpeakersPanel";
import { EventDisclosure } from "./EventDisclosure";
import type { EventFormValues } from "./EventFormFields";
import type { StaffEvent } from "./eventsApi";
import type { eventAccess } from "./eventStaffPermissions";
import type { eventDrawerSurfaces, MoreSection } from "./eventDrawerTabs";

type WebsitePublication = { publish_website: boolean; website_revision?: number } | undefined;

/**
 * The drawer's "More" tab: every section past the day-of-event work, behind one sub-navigation.
 * Some panels stay mounted while another section shows — exactly as when each was its own tab —
 * so an unsaved draft or the "publish website with event" choice never goes stale.
 */
export function EventDrawerMore({ event, makerspaceId, access, surfaces, section, sectionTabs, readOnly, onWebsitePublication, settings }: {
  event: StaffEvent; makerspaceId: number; access: ReturnType<typeof eventAccess>;
  surfaces: ReturnType<typeof eventDrawerSurfaces>; section: MoreSection | undefined; sectionTabs: Tab[]; readOnly: boolean;
  onWebsitePublication: (value: WebsitePublication) => void;
  settings: { values: EventFormValues; setValues: (value: EventFormValues) => void; save: () => void; pending: boolean;
    invalidate: () => void; resetField: (field: string) => void; complete: () => void };
}) {
  const eventId = event.id;
  const { ticketing, sections } = surfaces;
  const websiteTarget = { kind: "events" as const, id: eventId, makerspaceId };
  return <>
    {section ? <Tabs tabs={sectionTabs} activeKey={section} label="More sections" /> : null}
    {surfaces.invites ? <EventInvitesPanel key={eventId} visible={section === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
    {surfaces.ticketTypes ? <EventTicketsPanel key={eventId} visible={section === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
    {surfaces.promos ? <EventPromosPanel key={eventId} visible={section === "tickets"} eventId={eventId} disabled={readOnly} /> : null}
    {section === "tickets" && access.manager ? <EventOrderTools eventId={eventId} features={ticketing} manager={access.manager} disabled={readOnly} /> : null}
    {sections.speakers && section === "speakers" ? <EventSpeakersPanel eventId={eventId} makerspaceId={makerspaceId} websiteEnabled={sections.website} disabled={readOnly} /> : null}
    {section === "feedback" ? access.edit ? <>
      <EventFeedbackPanel eventId={eventId} makerspaceId={makerspaceId} canViewResponses={access.registrations} canManageCertificates={access.manager} />
      {ticketing.includes("events.certificate_designer") ? <EventDisclosure title="Certificate designer"><EventCertificateDesigner key={`certificate:${eventId}`} makerspaceId={makerspaceId} eventId={eventId} /></EventDisclosure> : null}
    </> : access.registrations ? <EventFeedbackResponses eventId={eventId} makerspaceId={makerspaceId} responseCount={0} canManageCertificates={false} /> : null : null}
    {sections.broadcasts && section === "broadcasts" ? <EventBroadcastsPanel makerspaceId={makerspaceId} eventId={eventId} /> : null}
    {sections.analytics && section === "analytics" ? <EventAnalyticsPanel makerspaceId={makerspaceId} eventId={eventId} endsAt={event.ends_at} features={event.report_features ?? []} /> : null}
    {/* Kept mounted (hidden) so the "publish website with event" choice the Publish action reads never goes stale. */}
    {sections.website && access.publish && event.status === "draft" ? <div hidden={section !== "website"}><EventWebsitePublication key={eventId} target={websiteTarget} onChange={onWebsitePublication} /></div> : null}
    {sections.website && section === "website" ? <EventWebsiteEditor key={`event:${eventId}`} target={websiteTarget} canEdit={access.edit} canPublish={access.publish} status={event.status} inheritedImage={{ url: event.image_url, alt: event.title }} /> : null}
    {access.manager ? <>
      <EventOrganizers visible={section === "team"} event={event} makerspaceId={makerspaceId} disabled={readOnly} />
      <EventCollaborators visible={section === "team"} makerspaceId={makerspaceId} eventId={eventId} />
      {section === "team" ? <EventStaffAccess target={{ kind: "event", id: eventId }} /> : null}
    </> : null}
    {sections.settings && section === "settings" ? <>
      {event.can_duplicate === true ? <div className="flex flex-wrap gap-2"><EventDuplicateAction event={event} makerspaceId={makerspaceId} /></div> : null}
      <EventSettings event={event} makerspaceId={makerspaceId} {...settings} />
      {access.edit ? <EventAudienceOrganizations event={event} makerspaceId={makerspaceId} disabled={readOnly} /> : null}
      {/* Without the roster, an editor still owns the badge template; printing stays with check-in staff. */}
      {!access.registrations && access.edit ? <EventDisclosure title="Badges"><EventBadgeActions event={event} makerspaceId={makerspaceId} selectedIds={[]} includeAttended={false} onIncludeAttended={() => {}} canPrint={false} /></EventDisclosure> : null}
    </> : null}
  </>;
}
