import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { opsStatusLabel } from "./opsPresentation";
import { AUDIENCE_LABELS } from "./EventAudienceOptions";
import { Card, EmptyState, ListRow, RelativeTime, StatCard, StatusBadge } from "../../components/ui";
import { useEventRegistrations, type StaffEvent } from "./eventsApi";
import { eventAccess } from "./eventStaffPermissions";
import { useStaffChargesOn } from "./useStaffChargesOn";

/** The latest registrations. Mounted only for staff who may read the roster, so nobody else requests it. */
function RegistrationsPreview({ eventId, onRegistrations }: { eventId: number; onRegistrations?: () => void }) {
  // The roster already mounts this exact page query; TanStack Query shares its request/cache.
  const registrations = useEventRegistrations(eventId, 1);
  const previewRows = [...(registrations.data?.results ?? [])].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).slice(0, 5);
  return <Card><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="title-panel">{t`Registrations`}</h2>{onRegistrations ? <button className="desk-button" type="button" onClick={onRegistrations}>{t`All registrations`}</button> : null}</div>
    {registrations.error ? <EmptyState message={t`Couldn't load registrations. Try again.`} action={{ label: t`Retry`, onClick: () => { void registrations.refetch(); } }} /> : previewRows.length ? <div className="grid gap-3">{previewRows.map(row => <ListRow key={row.id} title={row.name} identity={{ kind: "avatar", name: row.name, seed: String(row.id) }} meta={<RelativeTime date={row.created_at} />} right={<StatusBadge status={row.status} label={opsStatusLabel(row.status)} />} />)}</div> : <p className="text-sm text-muted">{registrations.isLoading ? t`Loading registrations…` : t`No registrations yet. Add your first guest in Registrations.`}</p>}
  </Card>;
}

/** Each jump action is passed only when the viewer holds the matching EventDrawer tab. */
export function EventOverview({ event, onRegistrations }: { event: StaffEvent; onRegistrations?: () => void }) {
  const counts = event.registration_counts;
  const going = counts.registered + counts.attended;
  return <div className="grid gap-6">
    <div className="sw-stats">
      <StatCard label={t`Going`} value={going} of={event.capacity || undefined} progress={event.capacity ? going / event.capacity : undefined} />
      <StatCard label={t`Waitlist`} value={counts.waitlisted} />
      <StatCard label={t`Awaiting approval`} value={counts.pending_approval} />
      <StatCard label={t`Checked in`} value={counts.attended} of={going || undefined} />
    </div>
    {eventAccess(event).registrations ? <RegistrationsPreview eventId={event.id} onRegistrations={onRegistrations} /> : null}
    {event.description ? <Card><h2 className="title-panel mb-3">{t`About this event`}</h2><p className="whitespace-pre-wrap text-sm">{event.description}</p></Card> : null}
  </div>;
}

const AUDIENCE_LABEL = { members: AUDIENCE_LABELS.members, accounts: AUDIENCE_LABELS.accounts, invite: AUDIENCE_LABELS.invite } as const;
/** Participating-organization events name their organizations; the server's audience label already does. */
const audienceLabel = (event: StaffEvent) => event.registration_audience === "participating_organizations"
  ? event.audience_label || AUDIENCE_LABELS.participating_organizations : AUDIENCE_LABEL[event.registration_audience ?? "members"];

export function EventAtAGlance({ event, onCheckIn }: { event: StaffEvent; onCheckIn?: () => void }) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const chargesOn = useStaffChargesOn("events");
  const eventDay = new Date(event.starts_at); eventDay.setHours(0, 0, 0, 0);
  const days = Math.round((eventDay.getTime() - today.getTime()) / 86_400_000);
  return <div className="grid gap-6">
    <Card><h2 className="title-panel mb-4">{t`At a glance`}</h2>
      <dl className="grid gap-4 text-sm">
        <div><dt className="text-muted">{t`When`}</dt><dd>{new Date(event.starts_at).toLocaleString(formatLocale())} → {new Date(event.ends_at).toLocaleString(formatLocale())} · {event.timezone_name}</dd></div>
        <div><dt className="text-muted">{t`Where`}</dt><dd>{event.location || t`Location to be confirmed`}</dd></div>
        <div><dt className="text-muted">{t`Who can join`}</dt><dd>{audienceLabel(event)} · {event.is_public ? t`Public listing` : t`Private event`}</dd></div>
        {chargesOn ? <div><dt className="text-muted">{t`Price`}</dt><dd>{Number(event.payment_amount) === 0 ? t`Free` : event.payment_amount}</dd></div> : null}
        <div><dt className="text-muted">{t`Registration`}</dt><dd>{event.registration_open ? t`Open` : t`Closed`}{event.effective_registration_cutoff_at ? t` · Closes ${new Date(event.effective_registration_cutoff_at).toLocaleString(formatLocale())}` : ""}</dd></div>
      </dl>
    </Card>
    {onCheckIn && event.status === "published" && event.offline_checkin_enabled && days >= 0 && days <= 1 ? <Card><h2 className="title-panel">{t`Get ready for the door`}</h2><p className="my-3 text-sm text-muted">{t`Download the guest list before the event so check-in works without a connection.`}</p><button className="desk-button" type="button" onClick={onCheckIn}>{t`Prepare check-in`}</button></Card> : null}
  </div>;
}
