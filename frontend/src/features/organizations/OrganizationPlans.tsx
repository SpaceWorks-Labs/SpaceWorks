import { t } from "@lingui/core/macro";
import { Trans } from "@lingui/react/macro";
import type * as Api from "../../generated/api";
import { RouteLink } from "../../components/ui/RouteLink";
import { PublicPlanCards } from "../publicPages/PublicPlanCards";
import type { SpaceCard } from "../publicPages/pageTypes";
import { canonicalHref } from "./publicDirectoryApi";

// O-B5 additions to the public organization read; typed locally until `generated/api.ts` is regenerated.
export type OrganizationPlanProjection = { title: string; count: number; results: Api.PublicPlanCard[]; collection_url: string };
export type OrganizationMembershipFields = { name: string; plans?: OrganizationPlanProjection | null; home_space?: SpaceCard | null };

/**
 * PP3: the home space's listed membership plans on the organization page. Organizations have no plans
 * of their own; joining happens at the home space, whose one member card names both (decision 293).
 * The server sends `plans: null` while the home space's membership or public-plans switch is off, and
 * then the whole section is absent.
 */
export function OrganizationPlans({ organization, workspace = false }: { organization: OrganizationMembershipFields; workspace?: boolean }) {
  const { plans, home_space: home } = organization;
  if (!plans?.results.length || !home) return null;
  return <section aria-labelledby="organization-plans-title" className="grid gap-4">
    <div className="grid gap-1">
      <h2 id="organization-plans-title" className="title-panel">{t`Membership`}</h2>
      {/* Decision 295: a workspace's /m/ page redirects here, so it is not linked as "elsewhere". */}
      {workspace ? <p className="max-w-[65ch] text-sm text-muted">{t`Choose a plan to join ${organization.name}.`}</p> : <p className="max-w-[65ch] text-sm text-muted">
        <Trans>Members join through <RouteLink className="font-semibold text-brand-ink underline underline-offset-2" href={canonicalHref(home, `/m/${encodeURIComponent(home.slug)}`)}>{home.name}</RouteLink>.</Trans>{" "}
        {t`Member cards are issued by ${home.name}; one card covers the space and ${organization.name}.`}
      </p>}
    </div>
    <PublicPlanCards rows={plans.results} slug={home.slug} />
  </section>;
}
