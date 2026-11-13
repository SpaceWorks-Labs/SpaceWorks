import { plural, t } from "@lingui/core/macro";
import { useMemo } from "react";
import { BrandFacets } from "../../../components/BrandFacets";
import { HubFooter } from "../../hub/HubFooter";
import { HubHeader } from "../../hub/HubHeader";
import "../../hub/hub.css";
import { useHostingConfig } from "../../hosting/hostingApi";
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
  return <div className="sw-hub"><HubHeader /><main className="sw-layout sw-layout-wide py-8 md:py-12">
    <SpacesHero total={query.data?.length} places={places} />
    <SpacesDirectory spaces={query.data} loading={query.isLoading} error={query.isError} retrying={query.isFetching}
      onRetry={() => { void query.refetch(); }} hosting={hosting} />
  </main><HubFooter /></div>;
}
