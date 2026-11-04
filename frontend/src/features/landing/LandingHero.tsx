import { BrandFacets } from "../../components/BrandFacets";
import { FilterBar } from "../../components/ui";
import { plural } from "../../lib/plural";
import { SpaceWorksDemo } from "./SpaceWorksDemo";

/**
 * The landing page's one bold moment (brand p.13): a Maker Teal field holding the Unbounded accent
 * phrase, the p.16 Citron search and the open-box facets cropped by the field's corner. Identical in
 * light and dark. Static, so it renders before the space list loads.
 */
export function LandingHero({ search, onSearch, shown, total }: {
  search: string; onSearch: (value: string) => void; shown: number; total: number;
}) {
  return <section aria-labelledby="landing-title"
    className="sw-field-teal relative mb-8 overflow-hidden rounded-[20px] md:mb-10 md:rounded-[28px] xl:mb-12 xl:min-h-[440px] min-[1680px]:mb-14 min-[1680px]:min-h-[520px]">
    <div className="relative z-10 grid gap-5 px-5 pb-32 pt-7 md:gap-6 md:p-10 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] xl:px-14 xl:py-16 min-[1680px]:px-[72px] min-[1680px]:py-20">
      <div className="grid min-w-0 content-start gap-5 md:gap-6">
        <h1 id="landing-title" className="sw-hero-title"><span className="block">Less searching.</span> <span className="block">More making.</span></h1>
        <p className="sw-hero-lede max-w-xl min-[1680px]:max-w-3xl">Find shared tools and your next community workshop.</p>
        <form role="search" className="mt-2 grid w-full min-w-0 gap-3 md:max-w-[440px] xl:mt-4 xl:max-w-[600px]" onSubmit={event => event.preventDefault()}>
          <FilterBar variant="hero" searchLabel="Search makerspaces" placeholder="Search by name, code or place" value={search} onChange={onSearch} />
          <div className="flex min-h-11 flex-wrap items-center gap-3">
            <p className="text-sm font-medium tabular-nums" aria-live="polite">{shown} / {plural(total, "space")}</p>
            {search ? <button className="desk-button" type="button" onClick={() => onSearch("")}>Clear search</button> : null}
          </div>
        </form>
      </div>
      <SpaceWorksDemo />
    </div>
    <BrandFacets size="sm" className="absolute -bottom-10 -right-6 h-auto w-[128px] md:-bottom-[72px] md:-right-8 md:w-[216px] xl:-bottom-[72px] xl:-right-12 xl:w-[360px] min-[1680px]:-bottom-[88px] min-[1680px]:-right-14 min-[1680px]:w-[440px]" />
  </section>;
}
