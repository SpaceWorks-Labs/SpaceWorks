import { Mail, MapPin } from "lucide-react";
import { ActionControl, ListRow } from "../../components/ui";
import type { TenantBootstrap } from "../../lib/api";
import { usePublicSpaces } from "../bookings/publicBookingsApi";
import { MakerspaceSection } from "./MakerspaceSection";

type Path = (part?: string) => string;
export const SPACES_PREVIEW = 3;

/** A short list of bookable spaces; hidden while loading and when none are published. */
export function SpacesSection({ slug, path }: { slug: string; path: Path }) {
  const spaces = usePublicSpaces(slug);
  if (spaces.isLoading) return null;
  if (spaces.isError) return <MakerspaceSection id="spaces" title="Book a space">
    <p role="alert" className="flex flex-wrap items-center gap-3 text-sm text-muted">Couldn't load bookable spaces.
      <button type="button" className="desk-button" onClick={() => void spaces.refetch()}>Try again</button></p>
  </MakerspaceSection>;
  const rows = spaces.data ?? [];
  if (!rows.length) return null;
  return <MakerspaceSection id="spaces" title="Book a space" subtitle="Rooms and benches you can reserve."
    more={{ label: rows.length > SPACES_PREVIEW ? `All ${rows.length} spaces` : "All spaces", href: path("bookings") }}>
    <ul className="grid gap-3">{rows.slice(0, SPACES_PREVIEW).map((space) => <li key={space.public_token}>
      <ListRow title={space.name} href={path(`bookings/${space.public_token}`)}
        identity={space.image_url ? { kind: "image", src: space.image_url } : { kind: "icon", icon: "Calendar", tone: "neutral" }}
        meta={<>{space.location ? <span className="block">{space.location}</span> : null}
          {space.capacity ? `Capacity ${space.capacity} · ` : null}{space.approval_mode === "approve" ? "Needs approval" : "Instant when available"}</>} />
    </li>)}</ul>
  </MakerspaceSection>;
}

export function MachinesSection({ path }: { path: Path }) {
  return <MakerspaceSection id="machines" title="Machines" more={{ label: "See machines", href: path("machines") }}>
    <p className="max-w-2xl text-base leading-6 text-muted">Check which machines are free right now, how long the queue is, and which ones need an induction first.</p>
  </MakerspaceSection>;
}

const JOIN_COPY: Record<TenantBootstrap["makerspace"]["membership_policy"], { body: string; label: string }> = {
  open: { body: "Membership is open. Create an account to join and start borrowing, booking and registering.", label: "Join now" },
  request: { body: "Send a membership request and the team will review it.", label: "Request to join" },
  invite_only: { body: "Membership is by invitation. Members can sign in to see their loans, bookings and events.", label: "Member sign in" },
};

export function MembershipSection({ policy, path }: { policy: TenantBootstrap["makerspace"]["membership_policy"]; path: Path }) {
  const copy = JOIN_COPY[policy] ?? JOIN_COPY.request;
  return <MakerspaceSection id="membership" title="Membership">
    <div className="desk-panel grid gap-4 p-5 sm:flex sm:items-center sm:justify-between">
      <p className="max-w-2xl text-base leading-6 text-ink">{copy.body}</p>
      <ActionControl action={{ label: copy.label, href: path("member") }} primary className="desk-button-brand shrink-0" />
    </div>
  </MakerspaceSection>;
}

export function safeEmail(value?: string) {
  return value && /^[^\s@?&#:]+@[^\s@?&#:]+\.[^\s@?&#:]+$/.test(value) ? value : null;
}
export function safeUrl(value?: string) {
  try {
    const url = new URL(value ?? "");
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

/** Address, directions and the support channels staff published; hidden when none exist. */
export function ContactSection({ bootstrap }: { bootstrap: TenantBootstrap }) {
  const location = bootstrap.makerspace.location?.trim();
  const mapUrl = safeUrl(bootstrap.makerspace.map_url?.trim());
  const email = safeEmail(bootstrap.branding.support_email);
  const supportUrl = safeUrl(bootstrap.branding.support_url);
  if (!location && !mapUrl && !email && !supportUrl) return null;
  const link = "font-semibold text-brand-ink underline-offset-2 hover:underline rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
  return <MakerspaceSection id="contact" title="Contact">
    <address className="desk-panel grid gap-3 p-5 text-sm not-italic">
      {location || mapUrl ? <p className="flex min-w-0 items-start gap-2"><MapPin aria-hidden="true" size={18} className="shrink-0 text-muted" />
        <span className="min-w-0 [overflow-wrap:anywhere]">{location}{mapUrl ? <>{location ? " · " : null}<a className={link} href={mapUrl} target="_blank" rel="noopener noreferrer">Open in Google Maps</a></> : null}</span></p> : null}
      {email || supportUrl ? <p className="flex min-w-0 flex-wrap items-start gap-2"><Mail aria-hidden="true" size={18} className="shrink-0 text-muted" />
        {email ? <a className={`${link} break-all`} href={`mailto:${encodeURI(email)}`}>{email}</a> : null}
        {supportUrl ? <a className={link} href={supportUrl} target="_blank" rel="noreferrer">Contact support</a> : null}</p> : null}
    </address>
  </MakerspaceSection>;
}
