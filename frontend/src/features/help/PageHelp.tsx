import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { useOptionalTenant } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { HelpLink } from "./HelpLink";

type Props = {
  /** The article (`section/slug`) the link opens. */
  article: string;
  /** What the article covers, for screen readers. */
  topic: string;
  /** The space, when the page knows it but its route has no `/m/<slug>`. */
  slug?: string;
  className?: string;
};

/**
 * A member or public page's Help link. The space is the single-space origin or the page's
 * `/m/<slug>`, and its `platform.help_centre` switch hides the link; with neither, the link opens
 * the central guide, which is always up.
 */
export function PageHelp({ article, topic, slug, className = "flex justify-end" }: Props) {
  const params = useParams();
  const tenant = useOptionalTenant();
  const single = tenant?.mode === "single";
  const spaceSlug = single ? "" : slug ?? params.slug ?? "";
  const fetched = useTenantBootstrap(spaceSlug, !single && Boolean(spaceSlug));
  const bootstrap = single ? tenant?.bootstrap : spaceSlug ? fetched.data : undefined;
  // Wait for the space's switches rather than show a link its space may have turned off.
  if ((single || spaceSlug) && !bootstrap) return null;
  const makerspace = bootstrap ? { slug: bootstrap.makerspace.slug, enabled_features: bootstrap.features ?? [] } : undefined;
  return <div className={className}>
    <HelpLink article={article} makerspace={makerspace} singleTenant={single} label={t`Help with ${topic}`} />
  </div>;
}
