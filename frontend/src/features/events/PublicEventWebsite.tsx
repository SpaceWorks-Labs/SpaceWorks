import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { ProgrammeWebsiteSections } from "./ProgrammeWebsiteSections";
import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { markdownMode, orderedGroups, sectionGroup, sponsorTiers, type EventWebsite, type PublicEventWebsiteData, type WebsiteSection, type WebsiteSession } from "./websiteTypes";
import type { ReactNode } from "react";
import { EventEditorialSections } from "./websiteSectionRegistry";
import { usePageBranding } from "../publicPages/usePageBranding";

export type WebsiteLinks = { schedule: string; speaker: (slug: string) => string; session: (slug: string) => string };
type ImageRenderer = (url: string, alt: string) => ReactNode;
const safeLink = (value?: string) => /^https?:\/\//i.test(value ?? "");
// Links inside a title stay text-sized; standalone links get the 44px target.
const inlineLink = "rounded-control text-brand-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
const actionLink = `inline-flex min-h-11 items-center text-sm font-semibold ${inlineLink}`;
const card = "min-w-0 rounded-xl border border-line bg-panel p-5";
const groupHeading = "title-panel";

export function WebsiteSectionCard({ row, image, links }: { row: WebsiteSection; image?: ImageRenderer; links?: WebsiteLinks }) {
  return <article id={`section-${row.slug}`} className={`${card} grid gap-3`}>
    <h3 className="title-section break-words">{row.kind === "highlight" && row.icon ? <span aria-hidden="true">{row.icon} </span> : null}
      {row.kind === "speaker" && links ? <a className={inlineLink} href={links.speaker(row.slug)}>{row.title}</a> : row.title}</h3>
    {row.image_url ? image ? image(row.image_url, row.image_alt_text ?? row.title) : <img className="max-h-64 max-w-full rounded-lg object-contain" src={row.image_url} alt={row.image_alt_text ?? row.title} /> : null}
    {row.kind === "speaker" ? <div><p className="font-semibold text-ink">{row.headline}</p><p className="text-sm text-muted">{row.organization}</p></div> : null}
    <RestrictedMarkdown text={row.body ?? ""} mode={markdownMode(row.body_rendering)} />
    <div className="flex flex-wrap gap-x-4 empty:hidden">
      {safeLink(row.url) ? <a className={actionLink} href={row.url} rel="noopener noreferrer">{t`Visit ${row.title}`}</a> : null}
      {row.kind === "speaker" ? ([['website_url', 'Website'], ['linkedin_url', 'LinkedIn'], ['x_url', 'X']] as const).map(([key, label]) => safeLink(row[key]) ? <a key={key} className={actionLink} href={row[key]} rel="noopener noreferrer">{label}</a> : null) : null}
    </div>
  </article>;
}

export function WebsiteProgramme({ website, links, sessions = website.sessions }: { website: Omit<EventWebsite, "editorial_document">; links?: WebsiteLinks; sessions?: WebsiteSession[] }) {
  const rows = sessions.filter((row) => row.visibility === "published");
  const title = (slug: string | null | undefined) => website.sections.find((section) => section.slug === slug)?.title ?? slug;
  return <section aria-label={t`Programme`} className="grid gap-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className={groupHeading}>{t`Programme`}</h2>
      {links ? <a className={actionLink} href={links.schedule}>{t`Full schedule`}</a> : null}</div>
    <ol className="grid gap-3">{rows.map((row) => <li className={`${card} grid gap-1`} key={row.slug}>
      <h3 className="title-section break-words">{links ? <a className={inlineLink} href={links.session(row.slug)}>{row.title}</a> : row.title}</h3>
      <p className="text-sm font-semibold tabular-nums text-ink"><time dateTime={row.effective_starts_at ?? row.starts_at}>{new Date(row.effective_starts_at ?? row.starts_at).toLocaleString(formatLocale())}</time> – <time dateTime={row.effective_ends_at ?? row.ends_at}>{new Date(row.effective_ends_at ?? row.ends_at).toLocaleTimeString(formatLocale())}</time></p>
      {row.effective_starts_at && row.effective_starts_at !== row.starts_at ? <p className="text-sm text-muted">{t`Planned start: ${new Date(row.starts_at).toLocaleTimeString(formatLocale())}`}</p> : null}
      <p className="text-sm text-muted">{[title(row.track), title(row.room)].filter(Boolean).join(" · ")}</p>
      <p className="flex flex-wrap gap-x-3 text-sm">{(row.speakers ?? []).map((slug) => <span key={slug}>{links ? <a className={inlineLink} href={links.speaker(slug)}>{title(slug)}</a> : title(slug)}</span>)}</p>
      <RestrictedMarkdown text={row.body ?? ""} mode={markdownMode(row.body_rendering)} />
    </li>)}</ol>
  </section>;
}

function Venue({ venue, cards }: { venue: NonNullable<EventWebsite["venue"]>; cards: ReactNode[] }) {
  return <section aria-label={t`Venue`} className="grid gap-3"><h2 className={groupHeading}>{t`Venue`}</h2>
    <div className={`${card} grid gap-3`}>
      <div><h3 className="title-section break-words">{venue.name}</h3><p className="whitespace-pre-line text-sm text-muted">{[venue.address, venue.city, venue.country].filter(Boolean).join(", ")}</p></div>
      {venue.latitude != null && venue.longitude != null ? <p className="text-sm tabular-nums">{t`Coordinates: ${venue.latitude}, ${venue.longitude}`}</p> : null}
      {safeLink(venue.map_url) ? <a className={actionLink} href={venue.map_url} rel="noopener noreferrer">{t`View venue map`}</a> : null}
      {([['directions', 'Directions'], ['parking', 'Parking'], ['public_transport', 'Public transport'], ['accessibility_notes', 'Accessibility']] as const).map(([key, label]) => venue[key] ? <section key={key}><h3 className="title-section">{label}</h3><RestrictedMarkdown text={venue[key]} /></section> : null)}
    </div>{cards}</section>;
}

export function PublicEventWebsite({ website, image, links }: { website: PublicEventWebsiteData; image?: ImageRenderer; links?: WebsiteLinks }) {
  const rows = website.sections.filter((row) => row.visibility === "published");
  const style = usePageBranding(website.presentation?.resolved_theme ?? (website.accent_color ? { primary_color: website.accent_color, accent_color: website.accent_color } : undefined), website.presentation?.accent_choice ?? website.editorial_document?.accent_choice);
  const renderImage: ImageRenderer = image ?? ((url, alt) => <img src={url} alt={alt} className="max-h-96 max-w-full rounded-xl object-contain" />);
  return <div className="grid min-w-0 gap-8" aria-label={t`Event website`} style={style}>
    {orderedGroups(website).filter((group) => website.section_enabled?.[group] !== false).map((group) => {
      const sections = rows.filter((row) => sectionGroup(row.kind) === group);
      const cards = sections.map((row) => <WebsiteSectionCard key={row.slug} row={row} image={image} links={links} />);
      if (group === "EDITORIAL") return website.editorial_document ? <EventEditorialSections key={group} projection={website.editorial_document} image={renderImage} /> : null;
      if (group === "SCHEDULE") return cards.length || website.sessions.some((row) => row.visibility === "published") ? <section key={group} aria-label={t`Schedule`} className="grid gap-6">{cards.length ? <section aria-label={t`Tracks`} className="grid gap-3"><h2 className={groupHeading}>{t`Tracks`}</h2>{cards}</section> : null}{website.sessions.some((row) => row.visibility === "published") ? <WebsiteProgramme website={website} links={links} /> : null}</section> : null;
      if (group === "SPONSORS") return sections.length ? <section key={group} aria-label={t`Sponsors`} className="grid gap-4"><h2 className={groupHeading}>{t`Sponsors`}</h2>{sponsorTiers.map((tier) => {
        const sponsors = sections.filter((row) => (row.sponsor_tier ?? "community_partner") === tier);
        return sponsors.length ? <section key={tier} aria-label={`${tier.replace(/_/g, " ")} sponsors`} className="grid gap-3"><h3 className="eyebrow">{tier.replace(/_/g, " ")}</h3><div className="grid gap-3 sm:grid-cols-2">{sponsors.map((row) => <WebsiteSectionCard key={row.slug} row={row} image={image} />)}</div></section> : null;
      })}</section> : null;
      if (group === "VENUE" && website.venue) return <Venue key={group} venue={website.venue} cards={cards} />;
      return cards.length || group === "HERO" && (website.tagline || website.cover) ? <section key={group} aria-label={group} className="grid gap-3">
        {group === "HERO" && website.cover ? renderImage(website.cover.url, website.cover.alt) : null}
        {group === "HERO" && website.tagline ? <p className="break-words font-accent text-xl text-brand-ink md:text-2xl">{website.tagline}</p> : null}
        {cards.length ? <><h2 className={`${groupHeading} capitalize`}>{group.toLowerCase()}</h2>{cards}</> : null}
      </section> : null;
    })}
    <ProgrammeWebsiteSections rows={website.programme_sections} />
  </div>;
}
