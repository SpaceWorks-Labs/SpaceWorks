import { safePublicLink } from "./PublicCollectionCards";

// Lane L18: the sponsor wall's public card (`apps.payments.donations.wall.card`). Public fields only.
export type SponsorCard = { id: number; name: string; tier: string; logo_url: string; website_url: string; blurb: string };
export type SponsorWallSection = { id: string; type: "sponsors"; enabled: boolean; payload: { title: string; results: SponsorCard[] } };

/** The opt-in sponsor wall: logo, name, tier and a line about each sponsor, linking out when given. */
export function PublicSponsorCards({ rows }: { rows: SponsorCard[] }) {
  return <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{rows.map(row => {
    const href = safePublicLink(row.website_url);
    const name = href ? <a className="inline-flex min-h-11 items-center text-brand-ink underline" href={href}
      rel="noopener noreferrer nofollow" target="_blank">{row.name}</a> : row.name;
    return <li key={row.id} className="grid content-start gap-2 rounded-xl border border-line bg-panel p-4">
      {row.logo_url ? <img src={row.logo_url} alt={`${row.name} logo`} loading="lazy" decoding="async" width={160} height={64}
        className="h-16 w-auto max-w-full object-contain" /> : null}
      <h3 className="title-section">{name}</h3>
      {row.tier ? <p className="text-xs font-semibold uppercase tracking-wide text-muted">{row.tier}</p> : null}
      {row.blurb ? <p className="text-sm text-muted">{row.blurb}</p> : null}
    </li>;
  })}</ul>;
}
