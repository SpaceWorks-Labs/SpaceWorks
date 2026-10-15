import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { orderedGroups, sectionGroup, sponsorTiers, type EventWebsite, type WebsiteSection, type WebsiteSession } from "./websiteTypes";
import type { ReactNode } from "react";

export type WebsiteLinks = { schedule: string; speaker: (slug: string) => string; session: (slug: string) => string };
type ImageRenderer = (url: string, alt: string) => ReactNode;
const safeLink = (value?: string) => /^https?:\/\//i.test(value ?? "");

export function WebsiteSectionCard({ row, image, links }: { row: WebsiteSection; image?: ImageRenderer; links?: WebsiteLinks }) {
  return <article id={`section-${row.slug}`} className="rounded-xl border border-border p-4">
    <h3 className="title-section">{row.kind === "highlight" && row.icon ? <span aria-hidden="true">{row.icon} </span> : null}
      {row.kind === "speaker" && links ? <a className="underline" href={links.speaker(row.slug)}>{row.title}</a> : row.title}</h3>
    {row.image_url ? image ? image(row.image_url, row.image_alt_text ?? row.title) : <img className="my-3 max-h-64 max-w-full rounded-lg object-contain" src={row.image_url} alt={row.image_alt_text ?? row.title} /> : null}
    {row.kind === "speaker" ? <><p className="font-semibold">{row.headline}</p><p className="text-muted">{row.organization}</p></> : null}
    <RestrictedMarkdown text={row.body} />
    <div className="mt-2 flex flex-wrap gap-3">
      {safeLink(row.url) ? <a className="underline" href={row.url} rel="noopener noreferrer">Visit {row.title}</a> : null}
      {row.kind === "speaker" ? ([['website_url', 'Website'], ['linkedin_url', 'LinkedIn'], ['x_url', 'X']] as const).map(([key, label]) => safeLink(row[key]) ? <a key={key} className="underline" href={row[key]} rel="noopener noreferrer">{label}</a> : null) : null}
    </div>
  </article>;
}

export function WebsiteProgramme({ website, links, sessions = website.sessions }: { website: EventWebsite; links?: WebsiteLinks; sessions?: WebsiteSession[] }) {
  const rows = sessions.filter((row) => row.visibility === "published");
  const title = (slug: string | null) => website.sections.find((section) => section.slug === slug)?.title ?? slug;
  return <section aria-label="Programme"><h2 className="title-section">Programme</h2>
    {links ? <a className="underline" href={links.schedule}>Full schedule</a> : null}
    <ol className="mt-3 grid gap-3">{rows.map((row) => <li className="rounded-lg border border-border p-3" key={row.slug}>
      <h3 className="font-semibold">{links ? <a className="underline" href={links.session(row.slug)}>{row.title}</a> : row.title}</h3>
      <p>{new Date(row.effective_starts_at ?? row.starts_at).toLocaleString()} – {new Date(row.effective_ends_at ?? row.ends_at).toLocaleTimeString()}</p>
      {row.effective_starts_at && row.effective_starts_at !== row.starts_at ? <p className="text-sm text-muted">Planned start: {new Date(row.starts_at).toLocaleTimeString()}</p> : null}
      <p className="text-sm text-muted">{[title(row.track), title(row.room)].filter(Boolean).join(" · ")}</p>
      <p className="flex flex-wrap gap-2">{row.speakers.map((slug) => <span key={slug}>{links ? <a className="underline" href={links.speaker(slug)}>{title(slug)}</a> : title(slug)}</span>)}</p>
      <RestrictedMarkdown text={row.body} />
    </li>)}</ol>
  </section>;
}

export function PublicEventWebsite({ website, image, links }: { website: EventWebsite; image?: ImageRenderer; links?: WebsiteLinks }) {
  const rows = website.sections.filter((row) => row.visibility === "published");
  return <div className="grid gap-6" aria-label="Event website" style={/^#([\da-f]{3}|[\da-f]{6})$/i.test(website.accent_color ?? "") ? { borderColor: website.accent_color, borderInlineStartWidth: 4, paddingInlineStart: 16 } : undefined}>
    {orderedGroups(website).filter((group) => website.section_enabled?.[group] !== false).map((group) => {
      const sections = rows.filter((row) => sectionGroup(row.kind) === group);
      const cards = sections.map((row) => <WebsiteSectionCard key={row.slug} row={row} image={image} links={links} />);
      if (group === "SCHEDULE") return cards.length || website.sessions.some((row) => row.visibility === "published") ? <section key={group} aria-label="Schedule" className="grid gap-3">{cards.length ? <section aria-label="Tracks"><h2 className="title-section">Tracks</h2>{cards}</section> : null}{website.sessions.some((row) => row.visibility === "published") ? <WebsiteProgramme website={website} links={links} /> : null}</section> : null;
      if (group === "SPONSORS") return sections.length ? <section key={group} aria-label="Sponsors" className="grid gap-4"><h2 className="title-section">Sponsors</h2>{sponsorTiers.map((tier) => {
        const sponsors = sections.filter((row) => (row.sponsor_tier ?? "community_partner") === tier);
        return sponsors.length ? <section key={tier} aria-label={`${tier.replace(/_/g, " ")} sponsors`}><h3 className="mb-2 font-semibold capitalize">{tier.replace(/_/g, " ")}</h3><div className="grid gap-3">{sponsors.map((row) => <WebsiteSectionCard key={row.slug} row={row} image={image} />)}</div></section> : null;
      })}</section> : null;
      if (group === "VENUE" && website.venue) {
        const venue = website.venue;
        return <section key={group} aria-label="Venue" className="grid gap-3"><h2 className="title-section">Venue</h2><h3 className="font-semibold">{venue.name}</h3><p className="whitespace-pre-line">{[venue.address, venue.city, venue.country].filter(Boolean).join(", ")}</p>
          {venue.latitude != null && venue.longitude != null ? <p>Coordinates: {venue.latitude}, {venue.longitude}</p> : null}
          {safeLink(venue.map_url) ? <a className="underline" href={venue.map_url} rel="noopener noreferrer">View venue map</a> : null}
          {([['directions', 'Directions'], ['parking', 'Parking'], ['public_transport', 'Public transport'], ['accessibility_notes', 'Accessibility']] as const).map(([key, label]) => venue[key] ? <section key={key}><h3 className="font-semibold">{label}</h3><RestrictedMarkdown text={venue[key]} /></section> : null)}{cards}</section>;
      }
      return cards.length || group === "HERO" && website.tagline ? <section key={group} aria-label={group} className="grid gap-3">
        {group === "HERO" && website.tagline ? <p className="text-xl font-semibold">{website.tagline}</p> : null}
        {cards.length ? <><h2 className="title-section capitalize">{group.toLowerCase()}</h2>{cards}</> : null}
      </section> : null;
    })}
  </div>;
}
