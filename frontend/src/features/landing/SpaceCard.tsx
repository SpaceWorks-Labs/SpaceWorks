import { Link } from "react-router-dom";
import { BrandFacets } from "../../components/BrandFacets";
import { MakerspaceBrand } from "../../components/MakerspaceBrand";
import { MakerspaceMapLink } from "../../components/MakerspaceMapLink";
import { Skeleton, StatusPill } from "../../components/ui";
import { identityTone } from "../../components/ui/tones";
import type { Makerspace } from "../../types/inventory";

// Cover placeholder: a solid brand tile per space (brand p.4 colour tiles), chosen by the same stable
// hash as avatars. Brand-tested label pairs: ink on citron 13.23, sky 9.23, yellow 10.37; cream on teal 5.68.
const TILES = {
  success: "bg-success text-on-success",
  info: "bg-info text-on-info",
  warn: "bg-warn text-on-warn",
  accent: "bg-accent text-on-accent",
} as const;

export function spaceTileTone(slug: string) {
  const tone = identityTone(slug);
  return tone in TILES ? tone as keyof typeof TILES : "accent";
}

/** Name first, details second (brand p.17); the whole card is one link to the catalogue. */
export function SpaceCard({ space }: { space: Makerspace }) {
  const tone = spaceTileTone(space.slug);
  return <article className="group relative flex min-w-0 flex-col rounded-2xl border border-line bg-panel transition-colors duration-120 hover:border-outline">
    <div className={`relative aspect-[1.8] overflow-hidden rounded-t-2xl ${space.cover_image_url ? "bg-surface" : TILES[tone]}`} data-tile={space.cover_image_url ? undefined : tone}>
      {space.cover_image_url ? <img src={space.cover_image_url} alt={`${space.name} cover`} loading="lazy" className="h-full w-full object-cover" />
        : <>
          <div className="grid h-full place-items-center text-5xl font-bold leading-none sm:text-[64px]" aria-hidden="true">{space.name.charAt(0)}</div>
          <BrandFacets size="sm" tone={tone === "accent" ? "orange" : "teal"} className="absolute -right-6 -top-8 h-auto w-[128px]" />
        </>}
      <div className="absolute left-4 top-4"><StatusPill label="Public catalogue" tone="neutral" /></div>
    </div>
    <div className="flex flex-1 flex-col gap-3 p-5 sm:p-6">
      <MakerspaceBrand name={space.name} logoUrl={space.logo_url} size="md" />
      <MakerspaceMapLink makerspace={space} className="relative z-10" locationClassName="break-words text-sm text-muted" />
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-4">
        <span className="code-text text-sm text-muted">{space.public_code}</span>
        <Link className="desk-button-ghost after:absolute after:inset-0 after:rounded-2xl after:content-['']" to={`/m/${space.slug}`} aria-label={`Open ${space.name} catalog`}>Open catalogue →</Link>
      </div>
    </div>
  </article>;
}

export function SpaceCardSkeletons() {
  return <div role="status" aria-label="Loading spaces" className="sw-space-grid">
    {[0, 1, 2].map(index => <div key={index} className="overflow-hidden rounded-2xl border border-line bg-panel" aria-hidden="true">
      <Skeleton className="aspect-[1.8] w-full rounded-none" />
      <div className="grid gap-3 p-6"><Skeleton className="h-6 w-2/3" /><Skeleton className="h-4 w-1/2" /></div>
    </div>)}
  </div>;
}
