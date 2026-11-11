import { plural, t } from "@lingui/core/macro";
import { useMemo } from "react";
import { BrandFacets } from "../../../components/BrandFacets";
import { PublicLayout } from "../../../components/layouts";
import { ThemeToggle } from "../../../components/ThemeToggle";
import { useHostingConfig } from "../../hosting/hostingApi";
import { LICENSE_URL } from "../../inventory/PublicPageChrome";
import { usePublicMakerspaces } from "../../inventory/usePublicInventory";
import { SpacesDirectory } from "./SpacesDirectory";
import { placesOf } from "./spacesFilter";

function SpacesHero({ total, places }: { total?: number; places: number }) {
  const summary = total ? places > 1
    ? `${plural(total, { one: "# makerspace", other: "# makerspaces" })} · ${plural(places, { one: "# place", other: "# places" })}`
    : plural(total, { one: "# makerspace", other: "# makerspaces" }) : null;
  return <section aria-labelledby="spaces-title" className="sw-field-teal sw-spaces-hero">
    <div className="sw-spaces-hero-copy">
      <h1 id="spaces-title" className="sw-spaces-hero-title">{t`Find a makerspace near you`}</h1>
      <p className="sw-hero-lede">{t`Community workshops, labs and makerspaces: what each one offers and what's on next.`}</p>
      <p className="min-h-5 text-sm font-semibold tabular-nums">{summary}</p>
    </div>
    <BrandFacets size="md" className="sw-spaces-hero-facets" />
  </section>;
}

/** `/spaces`: every public makerspace on this deployment, as a searchable, filterable, paged directory (decision 275). */
export function SpacesPage() {
  const query = usePublicMakerspaces();
  const hosting = useHostingConfig().data === true;
  const places = useMemo(() => placesOf(query.data ?? []).length, [query.data]);
  const hostLink = hosting ? [{ label: t`Host your makerspace`, href: "/hosting" }] : [];
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }} chrome="canvas"
    nav={[{ label: t`About`, href: "/about" }, ...hostLink]} headerAction={{ label: t`Sign in`, href: "/member" }}
    liveStatus={<ThemeToggle variant="icon" />} state={{ status: "ready" }}
    hero={<SpacesHero total={query.data?.length} places={places} />}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: t`About`, href: "/about" }, ...hostLink,
      { label: t`License`, href: LICENSE_URL, external: true }, { label: t`Platform sign-in`, href: "/admin" }] }}>
    <SpacesDirectory spaces={query.data} loading={query.isLoading} error={query.isError} retrying={query.isFetching}
      onRetry={() => { void query.refetch(); }} hosting={hosting} />
  </PublicLayout>;
}
