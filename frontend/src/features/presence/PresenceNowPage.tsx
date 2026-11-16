import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../components/layouts";
import { useTenant } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { PresenceNowBoard } from "./PresenceNowBoard";
import { isRetryable } from "../../lib/api/errors";

/** Route entry for /m/:slug/now (and /now on a single-tenant frontend). Works signed out. */
export function PresenceNowPage() {
  const { slug: routeSlug } = useParams();
  const tenant = useTenant();
  const slug = tenant.mode === "single" ? tenant.slug : routeSlug ?? "";
  const bootstrapQuery = useTenantBootstrap(slug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap ?? undefined);
  if (!bootstrap) {
    const failed = tenant.mode === "central" ? bootstrapQuery.isError : Boolean(tenant.error);
    // Gate on the error that actually failed: in single mode the route bootstrap query is disabled (decision 588).
    const failure = tenant.mode === "central" ? bootstrapQuery.error : tenant.error;
    return <CenteredCardLayout state={failed ? (isRetryable(failure)
      ? { status: "error", error: t`Couldn't load this makerspace. Try again.`, onRetry: () => void bootstrapQuery.refetch() }
      : { status: "error", error: failure instanceof Error ? failure.message : t`This makerspace isn't available.` }) : { status: "loading" }}
      title={t`Opening the display…`} body="" primary={{ label: t`Loading…`, disabled: true, disabledReason: "The display is opening." }} />;
  }
  const spaceName = bootstrap.branding.display_name || bootstrap.makerspace.name;
  return <div style={brandStyle}><PresenceNowBoard slug={slug} spaceName={spaceName} enabled={bootstrap.modules.includes("presence")} /></div>;
}
