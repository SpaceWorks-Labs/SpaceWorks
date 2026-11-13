import { t } from "@lingui/core/macro";
import { ArrowRight } from "lucide-react";
import { RouteLink } from "../../../components/ui/RouteLink";
import { useHostingConfig } from "../../hosting/hostingApi";
import { usePublicMakerspaces } from "../../inventory/usePublicInventory";
import { SpaceCardSkeletons } from "./SpaceCard";
import { SpacesCards } from "./SpacesDirectory";
import { SpacesEmpty, SpacesError } from "./SpacesStates";

export type SpacesSectionProps = {
  /** How many cards to show before "See all spaces" (the API returns spaces A-Z). */
  limit?: number;
  heading?: string;
  description?: string;
  /** Where "See all spaces" goes; `null` hides the link. */
  seeAllHref?: string | null;
  /** id for the section landmark's heading, so a landing page can link to `#spaces`. */
  id?: string;
};

/** The directory as one section of a landing page: a heading, the first few spaces and a link to `/spaces`. */
export function SpacesSection({ limit = 6, heading = t`Find a makerspace near you`,
  description = t`Community workshops, labs and makerspaces: what each one offers and what's on next.`, seeAllHref = "/spaces", id = "spaces" }: SpacesSectionProps) {
  const query = usePublicMakerspaces();
  const hosting = useHostingConfig().data === true;
  const spaces = query.data ?? [];
  const shown = spaces.slice(0, Math.max(1, limit));
  let body;
  if (query.isError && !spaces.length) body = <SpacesError onRetry={() => { void query.refetch(); }} retrying={query.isFetching} />;
  else if (query.isLoading) body = <SpaceCardSkeletons count={Math.min(Math.max(1, limit), 3)} />;
  else if (!spaces.length) body = <SpacesEmpty hosting={hosting} />;
  else body = <SpacesCards spaces={shown} />;
  return <section aria-labelledby={id} className="min-w-0">
    <div className="sw-spaces-section-head">
      <div className="grid max-w-2xl gap-2">
        <h2 id={id} className="sw-spaces-section-title">{heading}</h2>
        {description ? <p className="text-[17px] leading-7 text-muted">{description}</p> : null}
      </div>
      {seeAllHref && spaces.length > shown.length ? <RouteLink href={seeAllHref} className="desk-button gap-2">
        {t`See all ${spaces.length} makerspaces`}<ArrowRight aria-hidden="true" size={18} />
      </RouteLink> : null}
    </div>
    {body}
  </section>;
}
