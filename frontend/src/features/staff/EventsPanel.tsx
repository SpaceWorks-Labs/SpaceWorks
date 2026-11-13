import { formatDateTime, formatLocale } from "../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { EmptyState, ListRow, StatusBadge } from "../../components/ui";
import { FormPageLayout, ListLayout } from "../../components/layouts";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";
import { StructuredApiError, isSurfaceOff } from "../../lib/api";
import { useEventCollaborationReview } from "./EventCollaborationReview";
import { EventCreatePreview } from "./EventCreatePreview";
import { EventPartnersSection, emptyPartnerValues, partnerPayload } from "./EventPartnersSection";
import { EventDrawer } from "./EventDrawer";
import { EventRegistrationQueue } from "./EventRegistrationQueue";
import { EventSeriesDrawer } from "./EventSeriesDrawer";
import { EventSeriesFields, emptySeriesForm, seriesPayload } from "./EventSeriesForm";
import { eventErrorText } from "./eventUi";
import {
  EventFields,
  emptyEventForm,
  payloadFor,
  type EventFormValues,
} from "./EventFormFields";
import { useCreateEvent, useEvents, type StaffEvent } from "./eventsApi";
import { EVENT_SERIES_PAGE_SIZE, useCreateEventSeries, useEventSeriesList } from "./eventSeriesApi";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { useLocation, useSearchParams } from "react-router-dom";
import { useQuickCreate } from "./quickCreate";
import { useDomainSettingsDialog } from "./useDomainSettingsDialog";
import { useAreaPaymentsDrawer } from "./areaPayments/useAreaPaymentsDrawer";
import { EventSurfaceSettings } from "./eventPublishing/EventSurfaceSettings";
import { EventRoomStep, emptyRoomChoice, roomStepPayload } from "./EventRoomStep";
import { roomFailureText, useCreateEventWithRoom } from "./eventVenueApi";
import { toast } from "../../components/ui/toastStore";
import { EventInsightsCard, spaceInsightsPath } from "./eventProgramme/EventInsightsCard";

export { EventDrawer };

function dateRange(event: StaffEvent) {
  return `${new Date(event.starts_at).toLocaleString(formatLocale())} – ${new Date(event.ends_at).toLocaleString(formatLocale())}`;
}

export function EventsPanel({ makerspaceId, enabledFeatures = [], enabledModules = [], publicSiteEnabled = false }: {
  makerspaceId: number; enabledFeatures?: string[]; enabledModules?: string[]; publicSiteEnabled?: boolean;
}) {
  const list = useUrlListState({ q: "", status: "", ordering: "starts_at", page: "1" });
  const { page, setPage } = list;
  const [params, setParams] = useSearchParams();
  // Notices link to /admin/events/<id> (desk links) as well as ?event=<id>; either opens that event.
  const pathEventId = /\/events\/(\d+)(?:\/|$)/.exec(useLocation().pathname)?.[1] ?? null;
  const isSeries = params.get("eventsView") === "series";
  // Open item A22: the cross-event queue of registrations waiting on staff.
  const isQueue = params.get("eventsView") === "queue";
  // Parity E-F3 (A21): top events and the returning share, while events.space_insights is on.
  const insightsOn = enabledFeatures.includes("events.space_insights");
  const isInsights = insightsOn && params.get("eventsView") === "insights";
  const events = useEvents(makerspaceId, isSeries ? 1 : page, isSeries ? "" : list.query);
  const create = useCreateEvent(makerspaceId);
  const createWithRoom = useCreateEventWithRoom(makerspaceId);
  const [room, setRoom] = useState(emptyRoomChoice);
  const roomStep = enabledModules.includes("bookings") ? roomStepPayload(room) : null;
  const roomIncomplete = enabledModules.includes("bookings") && room.mode !== "none" && !roomStep;
  const series = useEventSeriesList(makerspaceId, isSeries ? page : 1);
  const createSeries = useCreateEventSeries(makerspaceId);
  const [values, setValues] = useState<EventFormValues>(emptyEventForm);
  const [seriesValues, setSeriesValues] = useState(emptySeriesForm);
  const [partners, setPartners] = useState(emptyPartnerValues);
  const [audienceEdited, setAudienceEdited] = useState(false);
  const [seriesAudienceEdited, setSeriesAudienceEdited] = useState(false);
  useEffect(() => {
    setValues(emptyEventForm); setSeriesValues(emptySeriesForm); setPartners(emptyPartnerValues);
    setAudienceEdited(false); setSeriesAudienceEdited(false); setRoom(emptyRoomChoice);
  }, [makerspaceId]);
  const defaultAudience = events.data?.default_registration_audience;
  const newValues = defaultAudience && !audienceEdited ? { ...values, registration_audience: defaultAudience } : values;
  const newSeriesValues = defaultAudience && !seriesAudienceEdited ? { ...seriesValues, registration_audience: defaultAudience } : seriesValues;
  const [creationMode, setCreationMode] = useState<"single" | "series">("single");
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get("event") ?? pathEventId) || null);
  const linkedId = params.get("event") ?? pathEventId;
  useEffect(() => { setSelectedId(Number(linkedId) || null); }, [linkedId]);
  const closeSelection = () => { setSelectedId(null); setParams((current) => { const next = new URLSearchParams(current); next.delete("event"); return next; }); };
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  useQuickCreate("event", () => { setCreationMode("single"); setCreating(true); });
  // The Event Manager owns the events.* switches and event defaults (domain-settings API).
  // L1: the event report switches (DY-61) and the embed allow-list sit below the switches.
  const eventSettings = useDomainSettingsDialog(makerspaceId, "events", true, <EventSurfaceSettings makerspaceId={makerspaceId} />, publicSiteEnabled);
  // Decision 242(a): every event charge type the Event Manager owns, settled from inside Events.
  const eventPayments = useAreaPaymentsDrawer(makerspaceId, "events");

  function submit() {
    // Unknown default and untouched field: let the server apply the space's default audience.
    const { registration_audience: audience, ...rest } = payloadFor(newValues);
    const extras = partnerPayload(partners, newValues.registration_audience === "participating_organizations");
    const body = defaultAudience || audienceEdited ? { ...rest, ...extras, registration_audience: audience } : { ...rest, ...extras };
    const done = (id: number) => {
      setCreating(false);
      setValues(emptyEventForm); setAudienceEdited(false); setPartners(emptyPartnerValues); setRoom(emptyRoomChoice);
      openEvent(id);
    };
    // Decision 223 G6: with a room step the draft and its room go in one call; a failed room keeps the draft.
    if (roomStep) createWithRoom.mutate({ event: body, room: roomStep }, { onSuccess: ({ event, room: result }) => {
      if (result.status === "failed") toast(t`The event was created as a draft, but the room step failed: ${roomFailureText(result)} Retry from the venue panel.`, { tone: "error" });
      else toast(result.booking_status === "pending" ? t`Event created. The room request awaits approval.` : t`Event created with its room.`, { tone: "success" });
      done(event.id);
    } });
    else create.mutate(body, { onSuccess: (created) => done(created.id) });
  }
  function submitSeries() {
    const { registration_audience: seriesAudience, ...seriesRest } = seriesPayload(newSeriesValues);
    createSeries.mutate(defaultAudience || seriesAudienceEdited ? { ...seriesRest, registration_audience: seriesAudience } : seriesRest, {
      onSuccess: (created) => {
        setCreating(false);
        setSeriesValues(emptySeriesForm); setSeriesAudienceEdited(false);
        setSelectedSeriesId(created.series.id);
      },
    });
  }

  // Tabs are server-side status filters (the API filters by status, not date), so every page of
  // events is reachable — filtering one fetched page in the browser used to hide events.
  const statusTabs = [{ key: "all", label: t`All` }, { key: "published", label: t`Published` }, { key: "draft", label: t`Drafts` }, { key: "completed", label: t`Completed` }, { key: "cancelled", label: t`Cancelled` }];
  const view = { active: isSeries ? "series" : isQueue ? "queue" : isInsights ? "insights" : list.values.status || "all",
    tabs: [...statusTabs.map(tab => ({ ...tab, href: "#" })), { key: "queue", label: t`Waiting on you`, href: "#" },
      { key: "series", label: t`Series`, href: "#", count: series.data?.count }, ...(insightsOn ? [{ key: "insights", label: t`Insights`, href: "#" }] : [])] };
  const selectTab = (key: string) => {
    setParams(current => {
      const next = new URLSearchParams(current);
      if (key === "series" || key === "queue" || key === "insights") next.set("eventsView", key); else next.delete("eventsView");
      if (key === "all" || key === "series" || key === "queue" || key === "insights") next.delete("status"); else next.set("status", key);
      next.delete("page");
      return next;
    });
  };
  const collaborations = useEventCollaborationReview(makerspaceId);
  const activeError = isSeries ? series.error : events.error;
  const apiError = activeError instanceof StructuredApiError ? activeError : null;
  const denied = apiError?.status === 403 || isSurfaceOff(apiError);
  const rows = events.data?.results ?? [];
  const shown = rows;
  const organizationAudience = enabledFeatures.includes("events.organization_audience");
  const openEvent = (id: number) => { setSelectedId(id); setParams(current => { const next = new URLSearchParams(current); next.set("event", String(id)); return next; }); };
  if (selectedId !== null) return <EventDrawer key={selectedId} eventId={selectedId} makerspaceId={makerspaceId} enabledFeatures={enabledFeatures} enabledModules={enabledModules} onClose={closeSelection}
    onOpenSeries={seriesId => { closeSelection(); setSelectedSeriesId(seriesId); }} />;
  if (selectedSeriesId !== null) return <EventSeriesDrawer key={selectedSeriesId} seriesId={selectedSeriesId} makerspaceId={makerspaceId} enabledFeatures={enabledFeatures} onClose={() => setSelectedSeriesId(null)} onSelectOccurrence={id => { setSelectedSeriesId(null); openEvent(id); }} />;
  if (creating) return <FormPageLayout state={{ status: "ready" }} header={{ title: creationMode === "single" ? t`New event` : t`New series`, subtitle: t`Start with a draft. Publish when every detail is ready.` }}
    back={{ label: t`All events`, onClick: () => setCreating(false) }} cancel={{ label: t`Cancel`, onClick: () => setCreating(false) }}
    form={<div data-create-event>{creationMode === "single" ? <><EventFields layout="split" organizationAudienceEnabled={organizationAudience} onlineEnabled={enabledFeatures.includes("events.online_delivery")} values={newValues} setValues={(next) => { if (next.registration_audience !== newValues.registration_audience) setAudienceEdited(true); setValues(next); }}
        moreExtras={<EventPartnersSection values={partners} setValues={setPartners} hostId={makerspaceId} audienceSelected={newValues.registration_audience === "participating_organizations"} />} />
        {creationMode === "single" && enabledModules.includes("bookings") ? <div className="mt-4"><EventRoomStep makerspaceId={makerspaceId} start={newValues.starts_at} end={newValues.ends_at} capacity={Number(newValues.capacity) || 0} value={room} onChange={setRoom} /></div> : null}</>
      : <EventSeriesFields organizationAudienceEnabled={organizationAudience} values={newSeriesValues} setValues={(next) => { if (next.registration_audience !== newSeriesValues.registration_audience) setSeriesAudienceEdited(true); setSeriesValues(next); }} />}
      {create.error || createSeries.error || createWithRoom.error ? <p className="mt-3 text-sm text-danger" role="alert">{eventErrorText(create.error || createSeries.error || createWithRoom.error)}</p> : null}</div>}
    preview={{ label: t`Event preview`, content: <EventCreatePreview values={creationMode === "single" ? newValues : newSeriesValues} currency={events.data?.results[0]?.currency} /> }}
    submit={{ label: creationMode === "single" ? t`Create event` : t`Create series`, pending: create.isPending || createSeries.isPending || createWithRoom.isPending, pendingLabel: t`Creating…`,
      disabled: events.isPending || (creationMode === "single" && roomIncomplete), disabledReason: events.isPending ? t`Loading this space's default registration audience.` : creationMode === "single" && roomIncomplete ? t`Finish the venue step or choose “No room for now”.` : undefined, onClick: creationMode === "single" ? submit : submitSeries }} />;
  return <div><ListLayout
    header={{ title: t`Events`, subtitle: t`Bring people together. Make something happen.`, primary: denied ? undefined : { label: t`New event`, onClick: () => { setCreationMode("single"); setCreating(true); } }, secondary: denied ? undefined : { label: t`New series`, onClick: () => { setCreationMode("series"); setCreating(true); } }, overflow: denied ? undefined : [...eventSettings.actions, ...eventPayments.actions] }}
    callout={denied ? undefined : collaborations.callout}
    state={denied || isQueue || isInsights ? { status: "ready" } : opsQueryState(view.active === "series" ? series : events, "events")}
    isEmpty={Boolean(denied) || (!isQueue && !isInsights && (view.active === "series" ? !series.data?.results.length : !events.data?.count))}
    empty={{ message: denied ? apiError?.status === 403 ? t`Event management access is required.` : t`The events module is unavailable.` : view.active === "series" ? t`No series yet. Create your first recurring event.` : t`Your events will appear here. Create your first event.`, action: denied ? undefined : { label: t`New event`, onClick: () => { setCreationMode("single"); setCreating(true); } } }}
    tabs={view.tabs} activeTab={view.active} onTabChange={selectTab}
    filtered={!isQueue && !isInsights && view.active !== "series" && Boolean(list.values.q || list.values.status)}
    filteredEmpty={{ message: list.values.q ? t`No events match this search. Try another title.` : t`No ${opsStatusLabel(list.values.status).toLowerCase()} events.`, action: { label: t`Clear filters`, onClick: () => list.update({ q: "", status: "" }) } }}
    filters={isSeries || isQueue || isInsights ? undefined : { toolbar: <ListViewControls state={list} makerspaceId={makerspaceId} entity="events" searchLabel="Search events" sorts={[["starts_at", "Starts first"], ["-starts_at", "Starts last"], ["title", "Title"]]} /> }}
    body={{ kind: "rows", rows: isInsights ? <EventInsightsCard path={spaceInsightsPath(makerspaceId)} onOpenEvent={openEvent} /> : isQueue ? <EventRegistrationQueue makerspaceId={makerspaceId} onOpenEvent={openEvent} /> : view.active === "series" ? series.data?.results.map(row => <ListRow key={row.id} title={row.title} onClick={() => setSelectedSeriesId(row.id)} draft={row.status === "draft"} identity={row.next_occurrence_at ? { kind: "date", date: row.next_occurrence_at } : { kind: "icon", icon: "Calendar", tone: "accent" }} meta={`${plural(row.future_occurrence_count, { one: "# upcoming date scheduled", other: "# upcoming dates scheduled" })} · ${row.next_occurrence_at ? formatDateTime(row.next_occurrence_at) : t`No future dates`}`} right={<StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} />} />) : !shown.length ? <EmptyState message={view.active === "all" ? t`No events match this search.` : t`No ${opsStatusLabel(view.active).toLowerCase()} events.`} /> : shown.map(item => <ListRow key={item.id} title={item.title} identity={{ kind: "date", date: item.starts_at }} draft={item.status === "draft"} onClick={() => openEvent(item.id)} meta={<>{dateRange(item)}{item.location ? ` · ${item.location}` : ""}<span className="block">{t`${item.registration_counts.pending_approval} pending approval`}</span></>} right={<div className="grid justify-items-end gap-2"><StatusBadge domain="event" status={item.status} label={opsStatusLabel(item.status)} /><span className="text-sm tabular-nums">{item.capacity ? t`${item.registration_counts.registered + item.registration_counts.attended} of ${item.capacity} going` : t`${item.registration_counts.registered + item.registration_counts.attended} going`}</span>{item.capacity ? <progress className="h-1 w-28 accent-accent" value={item.registration_counts.registered + item.registration_counts.attended} max={item.capacity} aria-label={t`${item.title} places filled`} /> : null}</div>} />) }}
    pagination={isQueue || isInsights ? undefined : isSeries ? series.data ? { page, pageSize: EVENT_SERIES_PAGE_SIZE, count: series.data.count, onChange: setPage } : undefined : events.data ? { page, pageSize: 24, count: events.data.count, onChange: setPage } : undefined}
    detail={denied ? undefined : collaborations.detail} />
    {eventSettings.dialog}
    {eventPayments.dialog}
  </div>;
}
