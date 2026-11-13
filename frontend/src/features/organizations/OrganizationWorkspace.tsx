import { t } from "@lingui/core/macro";
import { RouteLink } from "../../components/ui/RouteLink";
import { spaceKindLabel } from "../bookings/bookingStatusLabel";
import { PublicEventCards } from "../publicPages/PublicCollectionCards";

// Decision 295 (O-B6): typed locally until `generated/api.ts` is regenerated.
export type WorkspaceEvent = { title: string; starts_at: string; ends_at: string; timezone: string; location: string; public_token: string };
export type WorkspaceRoom = { name: string; kind: string; description: string; public_token: string };
export type OrganizationWorkspacePayload = {
  kind: "organization"; space_noun: "organization"; name: string;
  /** `null` while the workspace's Events (or its public surface) is off; then the section is absent. */
  events: WorkspaceEvent[] | null;
  /** `null` while Bookings is off; an empty list means nothing is bookable publicly yet. */
  rooms: WorkspaceRoom[] | null;
};

/**
 * An organization workspace has no /m/ page of its own (its /m/ address redirects here), so the
 * organization page carries what that page would: upcoming events and rooms to book. Links go
 * to the workspace's own event and booking pages, which keep their /m/<slug>/ addresses.
 */
export function OrganizationWorkspaceSections({ workspace, spaceSlug }: { workspace: OrganizationWorkspacePayload; spaceSlug: string }) {
  const base = `/m/${encodeURIComponent(spaceSlug)}`;
  const rooms = workspace.rooms;
  return <>
    {workspace.events ? <section aria-labelledby="workspace-events-title" className="grid gap-4">
      <h2 id="workspace-events-title" className="title-panel">{t`Upcoming events`}</h2>
      <PublicEventCards showPrice={false} rows={workspace.events.map(event => ({ ...event,
        event_url: `${base}/events/${encodeURIComponent(event.public_token)}` }))} />
    </section> : null}
    {rooms?.length ? <section aria-labelledby="workspace-rooms-title" className="grid gap-4">
      <h2 id="workspace-rooms-title" className="title-panel">{t`Rooms to book`}</h2>
      <ul className="grid gap-3 sm:grid-cols-2">{rooms.map(room => <RoomCard key={room.public_token} room={room} base={base} />)}</ul>
    </section> : null}
  </>;
}

function RoomCard({ room, base }: { room: WorkspaceRoom; base: string }) {
  const name = room.name;
  return <li className="grid content-start gap-2 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{name}</h3>
    <p className="text-sm text-muted">{spaceKindLabel(room.kind)}</p>
    {room.description ? <p className="whitespace-pre-wrap text-sm text-ink">{room.description.slice(0, 300)}</p> : null}
    <RouteLink className="desk-button justify-self-start" href={`${base}/bookings/${encodeURIComponent(room.public_token)}`}>
      {t`Book ${name}`}</RouteLink>
  </li>;
}
