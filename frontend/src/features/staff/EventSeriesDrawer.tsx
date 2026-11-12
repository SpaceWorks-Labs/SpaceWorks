import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { SeriesGuestList } from "./eventProgramme/SeriesGuestList";
import { SeriesInvitesPanel } from "./eventProgramme/SeriesInvitesPanel";
import { useEffect, useState, type FormEvent } from "react";

import { ConfirmDialog, EmptyState, ErrorText, ListRow, Pagination, StatusBadge } from "../../components/ui";
import { DetailLayout } from "../../components/layouts";
import { opsQueryState, useOpsTabs, opsStatusLabel } from "./opsPresentation";
import { EventSeriesCollaborators } from "./EventSeriesCollaborators";
import { SeriesMoneyCard } from "./SeriesMoneyCard";
import { SeriesPassTypes, useStaffCapability } from "./eventTicketing/SeriesPassTypes";
import { EventWebsiteEditor } from "./EventWebsiteEditor";
import { EventOrganizationAudience } from "./EventOrganizationAudience";
import { EventStaffAccess } from "./EventStaffAccess";
import { eventAccess } from "./eventStaffPermissions";
import { EventCoverUploader } from "./eventProgramme/EventCoverUploader";
import { EventSeriesFields, emptySeriesForm, seriesPayload, valuesForSeries } from "./EventSeriesForm";
import {
  EVENT_SERIES_PAGE_SIZE,
  useEventSeries,
  useEventSeriesAction,
  useEventSeriesOccurrences,
  useUpdateEventSeries,
} from "./eventSeriesApi";
import { eventErrorText } from "./eventUi";
import { pageStickyActions } from "./stickyActions";
import { LogoLoader } from "../../components/LogoLoader";

type Action = "publish" | "cancel" | "complete" | "extend";

function confirmCopy(action: Action | null) {
  if (action === "publish") return { title: t`Publish recurring series`, message: t`This will publish the series and its applicable occurrences.` };
  if (action === "complete") return { title: t`Complete recurring series`, message: t`This will complete the series and its applicable occurrences.` };
  if (action === "cancel") return { title: t`Cancel recurring series`, message: t`This will cancel the series and its applicable occurrences.` };
  if (action === "extend") return { title: t`Extend recurring series`, message: t`This will extend the series and its applicable occurrences.` };
  return { title: t`Change recurring series`, message: t`This will change the series and its applicable occurrences.` };
}

export function EventSeriesDrawer({ seriesId, makerspaceId, onClose, onSelectOccurrence, enabledFeatures = [] }: {
  seriesId: number; makerspaceId: number; onClose: () => void;
  onSelectOccurrence: (eventId: number) => void;
  enabledFeatures?: readonly string[];
}) {
  const query = useEventSeries(seriesId);
  const access = eventAccess(query.data ?? { staff_permissions: [], can_manage_staff: false });
  const [occurrencePage, setOccurrencePage] = useState(1);
  const occurrences = useEventSeriesOccurrences(seriesId, occurrencePage);
  useEffect(() => { setOccurrencePage(1); }, [seriesId]);
  const update = useUpdateEventSeries(makerspaceId, seriesId);
  const [values, setValues] = useState(emptySeriesForm);
  const [confirm, setConfirm] = useState<Action | null>(null);
  const publish = useEventSeriesAction(makerspaceId, seriesId, "publish");
  const cancel = useEventSeriesAction(makerspaceId, seriesId, "cancel");
  const complete = useEventSeriesAction(makerspaceId, seriesId, "complete");
  const extend = useEventSeriesAction(makerspaceId, seriesId, "extend");
  const action = confirm === "publish" ? publish : confirm === "cancel" ? cancel : confirm === "complete" ? complete : extend;
  // eslint-disable-next-line react-hooks/exhaustive-deps -- the form is reseeded only when the server revision (query.data.updated_at) changes; depending on the data object would wipe in-progress edits on every refetch
  useEffect(() => { if (query.data) setValues(valuesForSeries(query.data)); }, [query.data?.updated_at]);
  const terminal = query.data?.status === "cancelled" || query.data?.status === "completed";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const payload = seriesPayload(values);
    if (!query.data) return;
    const original = seriesPayload(valuesForSeries(query.data));
    const changed = Object.fromEntries(Object.entries(payload).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(original[key as keyof typeof original])));
    update.mutate({ ...changed, ...(query.data.status === "published" ? { effective_from: new Date().toISOString() } : {}) });
  };
  // Tabs and lifecycle actions follow the series staff grant the API enforces (eventStaffPermissions).
  const showWebsite = Boolean(query.data?.website_enabled) && (access.edit || access.publish);
  const showSettings = access.edit || access.publish;
  const showPasses = useStaffCapability(makerspaceId, "events.series_passes") && access.manager;
  // Parity E-F3 (B12): the series allowlist, for invite-only series while events.series_invites is on.
  const showInvites = enabledFeatures.includes("events.series_invites") && access.invitations && query.data?.registration_audience === "invite";
  const tabs = useOpsTabs("seriesTab", [{ key: "occurrences", label: t`Occurrences`, count: occurrences.data?.count },
    ...(access.registrations ? [{ key: "guests", label: t`Guests` }] : []),
    ...(showWebsite ? [{ key: "website", label: t`Website` }] : []),
    ...(showPasses ? [{ key: "passes", label: t`Passes` }] : []),
    ...(showInvites ? [{ key: "invites", label: t`Invitations` }] : []),
    ...(access.manager ? [{ key: "team", label: t`Team` }] : []),
    ...(showSettings ? [{ key: "settings", label: t`Settings` }] : [])], "occurrences");
  return <>
    <div onClickCapture={tabs.onClickCapture}><DetailLayout title={query.data?.title ?? t`Recurring series`} back={{ label: t`All events`, onClick: onClose }}
      identity={{ kind: "icon", icon: "Calendar", tone: "accent" }}
      status={query.data ? <StatusBadge domain="event" status={query.data.status} label={opsStatusLabel(query.data.status)} /> : undefined}
      meta={query.data ? [`${query.data.future_occurrence_count} active occurrences`, `Revision ${query.data.revision}`] : undefined}
      state={opsQueryState(query, "series")} tabs={tabs.tabs} activeTab={tabs.active}
      actions={{ primary: !access.publish ? undefined : query.data?.status === "draft" ? { label: t`Publish series`, confirms: true, onClick: () => setConfirm("publish") } : query.data?.status === "published" ? { label: t`Extend now`, onClick: () => setConfirm("extend") } : undefined,
        overflow: query.data?.status === "published" && access.publish ? [{ label: t`Complete series`, confirms: true, onClick: () => setConfirm("complete") },
          { label: t`Cancel series`, confirms: true, tone: "danger", onClick: () => setConfirm("cancel") }] : undefined }}
      banner={query.data?.last_generation_error_code ? { size: "banner", tone: "danger", lead: `Automatic extension needs attention (${query.data.last_generation_error_code}).`,
        body: t`Correct the schedule in Settings, then use Extend now.`, action: query.data.status === "published" && access.publish ? { label: t`Extend now`, onClick: () => setConfirm("extend") } : undefined } : undefined}
      danger={tabs.active === "settings" && query.data?.status === "published" && access.publish ? [{ title: t`Cancel series`, consequence: "Future occurrences close and registrants are notified.", action: { label: t`Cancel series`, onClick: () => setConfirm("cancel") } }] : []}
      main={query.data ? <div className="grid gap-5">
        {access.registrations && tabs.active === "guests" ? <SeriesGuestList seriesId={seriesId} /> : null}
        {showPasses && tabs.active === "passes" ? <SeriesPassTypes seriesId={seriesId} disabled={terminal} /> : null}
        {showInvites && tabs.active === "invites" ? <SeriesInvitesPanel seriesId={seriesId} disabled={terminal} /> : null}
        {tabs.active === "occurrences" ? <SeriesMoneyCard money={query.data.money} /> : null}
        {tabs.active === "occurrences" ? <EventOrganizationAudience event={query.data} pending={update.isPending} onReconfigure={access.edit ? () => update.mutate({ registration_audience: "participating_organizations" }) : undefined} /> : null}
        {showSettings && tabs.active === "settings" ? <div className="grid gap-5">
        {access.edit ? <EventCoverUploader endpoint={`/admin/event-series/${seriesId}/image`} currentUrl={query.data.image_url} label={t`Series photo (inherited by occurrences)`} disabled={terminal} onChanged={() => { void query.refetch(); }} /> : null}
        <form onSubmit={submit}><h3 className="title-section mb-3">{t`Edit future occurrences`}</h3><EventSeriesFields organizationAudienceEnabled={query.data.organization_audience_enabled} values={values} setValues={setValues} disabled={terminal} canEditDetails={access.edit} canEditSchedule={access.publish} canEditPrice={access.manager} />{!terminal ? <div className={pageStickyActions}><button className="desk-button" type="button" disabled={update.isPending} onClick={() => setValues(valuesForSeries(query.data!))}>{t`Discard`}</button><button className="desk-button-primary" type="submit" disabled={update.isPending}>{t`Save future occurrences`}</button></div> : null}</form>
        {query.data.status === "published" && access.publish ? <button className="desk-button justify-self-start" type="button" onClick={() => setConfirm("complete")}>{t`Complete series`}</button> : null}
        </div> : null}
        {showWebsite && tabs.active === "website" ? <EventWebsiteEditor key={`series:${seriesId}`} target={{ kind: "event-series", id: seriesId, makerspaceId }} canEdit={access.edit} canPublish={access.publish} status={query.data.status} inheritedImage={{ url: query.data.image_url ?? null, alt: query.data.title }} /> : null}
        {update.error || action.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(update.error || action.error)}</p> : null}
        {tabs.active === "occurrences" ? <section><h2 className="title-panel">{t`Occurrences`}</h2><p className="mt-1 text-sm text-muted">{t`Choose a date to edit or cancel only that occurrence.`}</p>
          {occurrences.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" /> : null}
          {occurrences.error ? <ErrorText resource={t`occurrences`} onRetry={() => { void occurrences.refetch(); }} /> : null}
          {occurrences.data && !occurrences.data.results.length ? <EmptyState message={t`No occurrences on this page.`} /> : null}
          <div className="mt-3 grid gap-3">{occurrences.data?.results.map(row => <ListRow key={row.id} title={new Date(row.starts_at).toLocaleString(formatLocale())} identity={{ kind: "date", date: row.starts_at }} draft={row.status === "draft"} onClick={() => onSelectOccurrence(row.id)} right={<StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} />} />)}</div>
          {occurrences.data ? <Pagination page={occurrencePage} count={occurrences.data.count} pageSize={EVENT_SERIES_PAGE_SIZE} totalPages={Math.ceil(occurrences.data.count / EVENT_SERIES_PAGE_SIZE)} onChange={setOccurrencePage} disabled={occurrences.isFetching} /> : null}
        </section> : null}
        {access.manager ? <>
          <EventSeriesCollaborators visible={tabs.active === "team"} seriesId={seriesId} makerspaceId={makerspaceId} />
          {tabs.active === "team" ? <EventStaffAccess target={{ kind: "series", id: seriesId }} /> : null}
        </> : null}
      </div> : null} /></div>
    <ConfirmDialog open={confirm !== null} title={confirmCopy(confirm).title} message={confirmCopy(confirm).message} confirmLabel={t`Confirm`} tone={confirm === "cancel" ? "danger" : "default"} pending={action.isPending} onCancel={() => setConfirm(null)} onConfirm={() => action.mutate(undefined, { onSettled: () => setConfirm(null) })} />
  </>;
}
