import { t } from "@lingui/core/macro";
import { lazy } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { CenteredCardLayout, PublicLayout } from "../../components/layouts";
import { useTenant } from "../../lib/tenant";
import { publicFamilies, publicHome } from "../../lib/publicHome";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MakerspacePage } from "./MakerspacePage";

const PublicBookingsPage = lazy(() => import("../bookings/PublicBookingsPage").then(m => ({ default: m.PublicBookingsPage })));

/** Tenant roots show an overview; retained legacy booking query links still open bookings. */
export function FamilyHome() {
  const tenant = useTenant();
  const { slug = "" } = useParams();
  const bootstrapQuery = useTenantBootstrap(slug, tenant.mode === "central" && Boolean(slug));
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const homeHref = tenant.mode === "single" ? "/" : `/m/${slug}`;
  const memberHref = tenant.mode === "single" ? "/member" : `/m/${slug}/member`;
  const [params] = useSearchParams();
  if (!bootstrap) {
    if (bootstrapQuery.error) return <PublicLayout state={{ status: "error", error: t`Couldn't load this space. Try again.`, onRetry: () => void bootstrapQuery.refetch() }}
      makerspace={{ name: "Space Works", slug, homeHref }} headerAction={{ label: t`Sign in`, href: memberHref }} nav={[]} header={{ title: t`We couldn't load this space` }}
      footer={{ credit: "Powered by Space Works", links: [] }}><span /></PublicLayout>;
    return <RouteFallback />;
  }
  // Old home links that opened a space (?space=, ?confirmation=) still land on the bookings page.
  if ((params.has("space") || params.has("confirmation")) && publicFamilies(bootstrap).includes("bookings")) return <PublicBookingsPage />;
  if (publicHome(bootstrap) === "makerspace") return <MakerspacePage />;
  return <PublicLayout state={{ status: "ready" }} isEmpty empty={{ message: t`${bootstrap.branding.display_name || bootstrap.makerspace.name} hasn't published anything yet. Check back soon.` }}
    makerspace={{ name: bootstrap.branding.display_name || bootstrap.makerspace.name, slug, homeHref }} headerAction={{ label: t`Sign in`, href: memberHref }} nav={[]}
    header={{ title: bootstrap.branding.display_name || bootstrap.makerspace.name }} footer={{ credit: "Powered by Space Works", links: [] }}><span /></PublicLayout>;
}

export function RouteFallback() {
  return <div role="status"><CenteredCardLayout state={{ status: "loading" }} title={t`Opening Space Works…`} body=""
    primary={{ label: t`Loading…`, disabled: true, disabledReason: "The page is opening." }} /></div>;
}
