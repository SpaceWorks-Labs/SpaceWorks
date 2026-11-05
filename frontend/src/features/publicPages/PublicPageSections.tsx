import type { ReactNode } from "react";
import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { RouteLink } from "../../components/ui/RouteLink";
import { sectionLabels } from "./documentDefaults";
import type { PublicPageSection } from "./pageTypes";
import { PublicEventCards, PublicSpaceCards, safePublicLink } from "./PublicCollectionCards";
export { PublicEventCards, PublicSpaceCards, safePublicLink } from "./PublicCollectionCards";
import { ProjectedEventCollection } from "./ProjectedEventCollection";
import { PublicPlanCards } from "./PublicPlanCards";
import { PublicSponsorCards } from "./PublicSponsorCards";
import { PublicShopCards } from "./PublicShopCards";
import { PublicCrewCards } from "./PublicCrewCards";
const metricLabels = {
  public_exact_count_subset_units: "Exact-count inventory subset",
  published_event_count: "Published events",
  public_member_count: "Public members",
};


function Content({ section, image, functional, organizationCollections, token, slug }: {
  section: PublicPageSection; image: (url: string, alt: string) => ReactNode; functional?: ReactNode; organizationCollections?: ReactNode;
  token?: string; slug?: string;
}) {
  switch (section.type) {
    case "about": return <RestrictedMarkdown text={section.payload.markdown} />;
    case "gallery": return <div className="grid gap-4 sm:grid-cols-2">{section.payload.items.map((item, index) => <figure key={index} className="grid gap-2">{item.url ? image(item.url, item.alt) : null}{item.caption ? <figcaption className="text-sm text-muted">{item.caption}</figcaption> : null}</figure>)}</div>;
    case "team": return <ul className="grid gap-3 sm:grid-cols-2">{section.payload.entries.map((entry, index) => <li key={entry.id ?? index} className="rounded-xl border border-line bg-panel p-4">
      {entry.kind === "member" && entry.avatar_url ? <img src={entry.avatar_url} alt="" width={64} height={64} className="h-16 w-16 rounded-full object-cover" /> : null}
      <h3 className="title-section">{safePublicLink(entry.url) ? <RouteLink className="inline-flex min-h-11 items-center text-brand-ink underline" href={entry.url}>{entry.display_name}</RouteLink> : entry.display_name}</h3><p className="text-sm text-muted">{entry.role}</p>
    </li>)}</ul>;
    case "stats": return <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">{Object.entries(section.payload.metrics).map(([key, value]) => <div key={key} className="rounded-xl border border-line bg-panel p-4"><dt className="text-sm text-muted">{metricLabels[key as keyof typeof metricLabels]}</dt><dd className="text-2xl font-semibold tabular-nums">{value?.toLocaleString()}</dd></div>)}</dl>;
    case "testimonials": return <div className="grid gap-4 sm:grid-cols-2">{section.payload.entries.map(entry => <figure key={entry.id} className="rounded-xl border border-line bg-panel p-4"><blockquote className="whitespace-pre-wrap">{entry.quote}</blockquote><figcaption className="mt-3 text-sm text-muted">{entry.attribution}</figcaption></figure>)}</div>;
    case "links": return <ul className="flex flex-wrap gap-2">{section.payload.entries.filter(entry => safePublicLink(entry.url)).map(entry => <li key={entry.id}><a className="desk-button" href={entry.url} rel="noopener noreferrer">{entry.label}</a></li>)}</ul>;
    case "location": return <div className="grid gap-3"><p className="whitespace-pre-wrap">{section.payload.address}</p><p className="whitespace-pre-wrap text-sm text-muted">{section.payload.directions}</p>{safePublicLink(section.payload.map_url) ? <a className="desk-button justify-self-start" href={section.payload.map_url} rel="noopener noreferrer">View map</a> : null}</div>;
    case "upcoming_events": return <ProjectedEventCollection key={`${section.id}-${token}`} collection={section.payload} token={token} slug={slug} />;
    case "linked_makerspaces": return <PublicSpaceCards rows={section.payload.results} />;
    case "membership_plans": return <PublicPlanCards rows={section.payload.results} slug={slug} />;
    case "sponsors": return <PublicSponsorCards rows={section.payload.results} />;
    case "shop": return <PublicShopCards shop={section.payload} slug={slug} />;
    case "crew": return <PublicCrewCards rows={section.payload.results} />;
    case "organization_events": return organizationCollections ?? <div className="grid gap-6"><section><h3 className="title-section mb-3">Upcoming events</h3><PublicEventCards rows={section.payload.upcoming.results} /></section><section><h3 className="title-section mb-3">Past event archive</h3><PublicEventCards rows={section.payload.past.results} past /></section></div>;
    case "functional_content": return functional ?? <ul className="flex flex-wrap gap-2">{section.payload.links.map(link => <li key={link.url}><RouteLink className="desk-button" href={safePublicLink(link.url)}>{({ inventory: "Browse inventory", events: "See events", bookings: "Book a space", machines: "Explore machines", membership: "Member area" })[link.family]}</RouteLink></li>)}</ul>;
    default: return null;
  }
}

/** The server omits these when empty; skip them defensively so a heading never stands alone. */
function isEmptyDerived(section: PublicPageSection) {
  if (section.type === "stats") return Object.keys(section.payload.metrics).length === 0;
  if (section.type === "location") return !section.payload.enabled_publicly;
  if (section.type === "sponsors" || section.type === "crew") return !section.payload.results?.length;
  return false;
}

/** Projections are already live-filtered on the server. Never fill missing entries from editor data. */
export function PublicPageSections({ sections, image, functional, organizationCollections, linkedMakerspaces, token, slug }: {
  sections: PublicPageSection[]; image: (url: string, alt: string) => ReactNode; functional?: ReactNode;
  organizationCollections?: ReactNode; linkedMakerspaces?: ReactNode;
  token?: string; slug?: string;
}) {
  return <div className="grid min-w-0 gap-8">{sections.map(section => {
    if (!(section.type in sectionLabels) || section.enabled === false || isEmptyDerived(section)) return null;
    const title = "title" in section.payload ? section.payload.title || sectionLabels[section.type] : sectionLabels[section.type];
    return <section key={section.id} aria-labelledby={`page-section-${section.id}`} className="grid min-w-0 gap-4 scroll-mt-6">
      <h2 id={`page-section-${section.id}`} className="title-panel">{title}</h2>
      {section.type === "linked_makerspaces" && linkedMakerspaces ? linkedMakerspaces : <Content section={section} image={image} functional={functional} organizationCollections={organizationCollections} token={token} slug={slug} />}
    </section>;
  })}</div>;
}
