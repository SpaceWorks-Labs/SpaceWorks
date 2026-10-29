import { useEffect, useState } from "react";

import { EmptyState, ListRow, StatusBadge } from "../../components/ui";
import { FormPageLayout, ListLayout } from "../../components/layouts";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";
import { StructuredApiError } from "../../lib/api";
import { useEventCollaborationReview } from "./EventCollaborationReview";
import { EventCreatePreview } from "./EventCreatePreview";
import { EventPartnersSection, emptyPartnerValues, partnerPayload } from "./EventPartnersSection";
import { EventDrawer } from "./EventDrawer";
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
import { useSearchParams } from "react-router-dom";
import { useQuickCreate } from "./quickCreate";
import { useDomainSettingsDialog } from "./useDomainSettingsDialog";
import { EventSurfaceSettings } from "./eventPublishing/EventSurfaceSettings";

export { EventDrawer };

function dateRange(event: StaffEvent) {
  return `${new Date(event.starts_at).toLocaleString()} – ${new Date(event.ends_at).toLocaleString()}`;
}

export function EventsPanel({ makerspaceId, enabledFeatures = [], enabledModules = [] }: {
  makerspaceId: number; enabledFeatures?: string[]; enabledModules?: string[];
}) {
  const list = useUrlListState({ q: "", status: "", ordering: "starts_at", page: "1" });
  const { page, setPage } = list;
  const [params, setParams] = useSearchParams();
  const isSeries = params.get("eventsView") === "series";
  const events = useEvents(makerspaceId, isSeries ? 1 : page, isSeries ? "" : list.query);
  const create = useCreateEvent(makerspaceId);
  const series = useEventSeriesList(makerspaceId, isSeries ? page : 1);
  const createSeries = useCreateEventSeries(makerspaceId);
  const [values, setValues] = useState<EventFormValues>(emptyEventForm);
  const [seriesValues, setSeriesValues] = useState(emptySeriesForm);
  const [partners, setPartners] = useState(emptyPartnerValues);
  const [audienceEdited, setAudienceEdited] = useState(false);
  const [seriesAudienceEdited, setSeriesAudienceEdited] = useState(false);
  useEffect(() => {
    setValues(emptyEventForm); setSeriesValues(emptySeriesForm); setPartners(emptyPartnerValues);
    setAudienceEdited(false); setSeriesAudienceEdited(false);
  }, [makerspaceId]);
  const defaultAudience = events.data?.default_registration_audience;
  const newValues = defaultAudience && !audienceEdited ? { ...values, registration_audience: defaultAudience } : values;
  const newSeriesValues = defaultAudience && !seriesAudienceEdited ? { ...seriesValues, registration_audience: defaultAudience } : seriesValues;
  const [creationMode, setCreationMode] = useState<"single" | "series">("single");
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get("event")) || null);
  const linkedId = params.get("event");
  useEffect(() => { setSelectedId(Number(linkedId) || null); }, [linkedId]);
  const closeSelection = () => { setSelectedId(null); setParams((current) => { const next = new URLSearchParams(current); next.delete("event"); return next; }); };
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  useQuickCreate("event", () => { setCreationMode("single"); setCreating(true); });
  // The Event Manager owns the events.* switches and event defaults (domain-settings API).
  // L1: the event report switches (DY-61) and the embed allow-list sit below the switches.
  const eventSettings = useDomainSettingsDialog(makerspaceId, "events", true, <EventSurfaceSettings makerspaceId={makerspaceId} />);

  function submit() {
    // Unknown default and untouched field: let the server apply the space's default audience.
    const { registration_audience: audience, ...rest } = payloadFor(newValues);
    const extras = partnerPayload(partners, newValues.registration_audience === "participating_organizations");
    create.mutate(defaultAudience || audienceEdited ? { ...rest, ...extras, registration_audience: audience } : { ...rest, ...extras }, {
      onSuccess: (created) => {
        setCreating(false);
        setValues(emptyEventForm); setAudienceEdited(false); setPartners(emptyPartnerValues);
        openEvent(created.id);
      },
    });
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
  const statusTabs = [{ key: "all", label: "All" }, { key: "published", label: "Published" }, { key: "draft", label: "Drafts" }, { key: "completed", label: "Completed" }, { key: "cancelled", label: "Cancelled" }];
  const view = { active: params.get("eventsView") === "series" ? "series" : list.values.status || "all",
    tabs: [...statusTabs.map(tab => ({ ...tab, href: "#" })), { key: "series", label: "Series", href: "#", count: series.data?.count }] };
  const selectTab = (key: string) => {
    setParams(current => {
      const next = new URLSearchParams(current);
      if (key === "series") next.set("eventsView", "series"); else next.delete("eventsView");
      if (key === "all" || key === "series") next.delete("status"); else next.set("status", key);
      next.delete("page");
      return next;
    });
  };
  const collaborations = useEventCollaborationReview(makerspaceId);
  const activeError = isSeries ? series.error : events.error;
  const apiError = activeError instanceof StructuredApiError ? activeError : null;
  const denied = apiError?.status === 403 || (apiError?.status === 400 && apiError.body.module);
  const rows = events.data?.results ?? [];
  const shown = rows;
  const organizationAudience = enabledFeatures.includes("events.organization_audience");
  const openEvent = (id: number) => { setSelectedId(id); setParams(current => { const next = new URLSearchParams(current); next.set("event", String(id)); return next; }); };
  if (selectedId !== null) return <EventDrawer key={selectedId} eventId={selectedId} makerspaceId={makerspaceId} enabledFeatures={enabledFeatures} enabledModules={enabledModules} onClose={closeSelection}
    onOpenSeries={seriesId => { closeSelection(); setSelectedSeriesId(seriesId); }} />;
  if (selectedSeriesId !== null) return <EventSeriesDrawer key={selectedSeriesId} seriesId={selectedSeriesId} makerspaceId={makerspaceId} onClose={() => setSelectedSeriesId(null)} onSelectOccurrence={id => { setSelectedSeriesId(null); openEvent(id); }} />;
  if (creating) return <FormPageLayout state={{ status: "ready" }} header={{ title: creationMode === "single" ? "New event" : "New series", subtitle: "Start with a draft. Publish when every detail is ready." }}
    back={{ label: "All events", onClick: () => setCreating(false) }} cancel={{ label: "Cancel", onClick: () => setCreating(false) }}
    form={<div data-create-event>{creationMode === "single" ? <EventFields layout="split" organizationAudienceEnabled={organizationAudience} onlineEnabled={enabledFeatures.includes("events.online_delivery")} values={newValues} setValues={(next) => { if (next.registration_audience !== newValues.registration_audience) setAudienceEdited(true); setValues(next); }}
        moreExtras={<EventPartnersSection values={partners} setValues={setPartners} hostId={makerspaceId} audienceSelected={newValues.registration_audience === "participating_organizations"} />} />
      : <EventSeriesFields organizationAudienceEnabled={organizationAudience} values={newSeriesValues} setValues={(next) => { if (next.registration_audience !== newSeriesValues.registration_audience) setSeriesAudienceEdited(true); setSeriesValues(next); }} />}
      {create.error || createSeries.error ? <p className="mt-3 text-sm text-danger" role="alert">{eventErrorText(create.error || createSeries.error)}</p> : null}</div>}
    preview={{ label: "Event preview", content: <EventCreatePreview values={creationMode === "single" ? newValues : newSeriesValues} /> }}
    submit={{ label: creationMode === "single" ? "Create event" : "Create series", pending: create.isPending || createSeries.isPending, pendingLabel: "Creating…",
      disabled: events.isPending, disabledReason: events.isPending ? "Loading this space's default registration audience." : undefined, onClick: creationMode === "single" ? submit : submitSeries }} />;
  return <div><ListLayout
    header={{ title: "Events", subtitle: "Bring people together. Make something happen.", primary: denied ? undefined : { label: "New event", onClick: () => { setCreationMode("single"); setCreating(true); } }, secondary: denied ? undefined : { label: "New series", onClick: () => { setCreationMode("series"); setCreating(true); } }, overflow: denied ? undefined : eventSettings.actions }}
    callout={denied ? undefined : collaborations.callout}
    state={denied ? { status: "ready" } : opsQueryState(view.active === "series" ? series : events, "events")}
    isEmpty={Boolean(denied) || (view.active === "series" ? !series.data?.results.length : !events.data?.count)}
    empty={{ message: denied ? apiError?.status === 403 ? "Event management access is required." : "The events module is unavailable." : view.active === "series" ? "No series yet. Create your first recurring event." : "Your events will appear here. Create your first event.", action: denied ? undefined : { label: "New event", onClick: () => { setCreationMode("single"); setCreating(true); } } }}
    tabs={view.tabs} activeTab={view.active} onTabChange={selectTab}
    filtered={view.active !== "series" && Boolean(list.values.q || list.values.status)}
    filteredEmpty={{ message: list.values.q ? "No events match this search. Try another title." : `No ${opsStatusLabel(list.values.status).toLowerCase()} events.`, action: { label: "Clear filters", onClick: () => list.update({ q: "", status: "" }) } }}
    filters={isSeries ? undefined : { toolbar: <ListViewControls state={list} makerspaceId={makerspaceId} entity="events" searchLabel="Search events" sorts={[["starts_at", "Starts first"], ["-starts_at", "Starts last"], ["title", "Title"]]} /> }}
    body={{ kind: "rows", rows: view.active === "series" ? series.data?.results.map(row => <ListRow key={row.id} title={row.title} onClick={() => setSelectedSeriesId(row.id)} draft={row.status === "draft"} identity={row.next_occurrence_at ? { kind: "date", date: row.next_occurrence_at } : { kind: "icon", icon: "Calendar", tone: "accent" }} meta={`${row.future_occurrence_count} buffered · ${row.next_occurrence_at ? new Date(row.next_occurrence_at).toLocaleString() : "No future occurrence"}`} right={<StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} />} />) : !shown.length ? <EmptyState message={view.active === "all" ? "No events match this search." : `No ${opsStatusLabel(view.active).toLowerCase()} events.`} /> : shown.map(item => <ListRow key={item.id} title={item.title} identity={{ kind: "date", date: item.starts_at }} draft={item.status === "draft"} onClick={() => openEvent(item.id)} meta={<>{dateRange(item)}{item.location ? ` · ${item.location}` : ""}<span className="block">{item.registration_counts.pending_approval} pending</span></>} right={<div className="grid justify-items-end gap-2"><StatusBadge domain="event" status={item.status} label={opsStatusLabel(item.status)} /><span className="text-sm tabular-nums">{item.registration_counts.registered + item.registration_counts.attended} / {item.capacity || "unlimited"} going</span>{item.capacity ? <progress className="h-1 w-28 accent-accent" value={item.registration_counts.registered + item.registration_counts.attended} max={item.capacity} aria-label={`${item.title} places filled`} /> : null}</div>} />) }}
    pagination={isSeries ? series.data ? { page, pageSize: EVENT_SERIES_PAGE_SIZE, count: series.data.count, onChange: setPage } : undefined : events.data ? { page, pageSize: 24, count: events.data.count, onChange: setPage } : undefined}
    detail={denied ? undefined : collaborations.detail} />
    {eventSettings.dialog}
  </div>;
}
