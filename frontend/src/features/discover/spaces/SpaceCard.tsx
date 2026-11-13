import { t } from "@lingui/core/macro";
import { ArrowRight, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import { LogoLoader } from "../../../components/LogoLoader";
import { identityTone } from "../../../components/ui/tones";
import type { Makerspace } from "../../../types/inventory";
import { SpaceNextEvent, SpaceOfferChips } from "./SpaceOffers";
import "./spaces.css";

export type SpaceTone = "accent" | "info" | "success" | "warn";
export type SpaceCardLayout = "grid" | "feature";

/** The card's colour field: one of the four brand fills, stable per space (same hash as avatars). */
export function spaceTone(slug: string): SpaceTone {
  const tone = identityTone(slug);
  return tone === "info" || tone === "success" || tone === "warn" ? tone : "accent";
}

function initial(name: string) {
  return (Array.from(name.trim())[0] ?? "?").toLocaleUpperCase();
}

/**
 * One public makerspace (decision 275 change): the space's own cover image leads, with a brand colour
 * field stencilled with its public code only when it has none (a shelf label, brand p.17); then its logo
 * or initial on a reversed tile, name, place, what it offers and its next public event. The whole card is
 * one link to the space; the event and map links sit above it. Hover and focus change colour only (no
 * translate or scale, ui-brand-spec §E).
 */
export function SpaceCard({ space, layout = "grid", headingLevel = 3 }: {
  space: Makerspace; layout?: SpaceCardLayout; headingLevel?: 2 | 3;
}) {
  const tone = spaceTone(space.slug);
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const cover = space.cover_image_url;
  const location = space.location?.trim();
  return <article className={`sw-space-card${layout === "feature" ? " sw-space-card-feature" : ""}`} data-tone={tone}>
    <div className="sw-space-field" data-tile={cover ? undefined : tone} data-cover={cover ? "" : undefined}>
      {cover ? <img src={cover} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
        : <span className="sw-space-stencil" aria-hidden="true" data-text={space.public_code || initial(space.name)} />}
    </div>
    <div className="sw-space-body">
      <span className={`sw-space-mark${space.logo_url ? " sw-space-mark-logo" : ""}`} aria-hidden="true">
        {space.logo_url ? <img src={space.logo_url} alt="" loading="lazy" className="h-full w-full object-contain" /> : initial(space.name)}
      </span>
      <Heading className="sw-space-name"><Link className="sw-space-link" to={`/m/${space.slug}`}>{space.name}</Link></Heading>
      {location ? <p className="sw-space-place"><MapPin aria-hidden="true" size={16} className="mt-0.5 shrink-0" /><span>{location}</span></p> : null}
      <SpaceOfferChips offers={space.offers} />
      <SpaceNextEvent event={space.next_event} />
      <div className="sw-space-foot">
        {space.public_code ? <span className="sw-space-code"><span className="sr-only">{t`Space code`} </span>{space.public_code}</span> : null}
        {space.map_url ? <a className="sw-space-map" href={space.map_url} target="_blank" rel="noopener noreferrer"
          aria-label={t`Open ${space.name} in Google Maps (new tab)`}>{t`Map`}</a> : null}
        <span className="sw-space-go" aria-hidden="true">
          {layout === "feature" ? <span>{t`Open space`}</span> : null}<ArrowRight size={20} />
        </span>
      </div>
    </div>
  </article>;
}

/** The loading state of the spaces grid: the Space Works box, with the grid's minimum height reserved. */
export function SpaceCardSkeletons({ label = t`Loading spaces` }: { count?: number; label?: string }) {
  return <LogoLoader label={label} className="min-h-72 py-10" />;
}
