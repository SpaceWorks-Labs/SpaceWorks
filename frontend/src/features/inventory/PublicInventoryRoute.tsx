import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../components/layouts";
import { publicFamilies } from "../../lib/publicHome";
import { useTenant } from "../../lib/tenant";
import { NotFoundPage } from "../NotFoundPage";
import { PublicInventoryPage } from "./PublicInventoryPage";
import { useTenantBootstrap } from "./usePublicInventory";

/** Gate the standalone inventory before mounting any stock, category or request queries. */
export function PublicInventoryRoute() {
  const { slug = "" } = useParams();
  const tenant = useTenant();
  const query = useTenantBootstrap(slug, tenant.mode === "central" && Boolean(slug));
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : query.data;
  if (!bootstrap) return <CenteredCardLayout title={t`Inventory`}
    state={query.error ? { status: "error", error: t`Couldn't load this space. Try again.`, onRetry: () => void query.refetch() } : { status: "loading" }}
    body="" primary={{ label: t`Opening inventory…`, disabled: true, disabledReason: t`The page is opening.` }} />;
  if (!publicFamilies(bootstrap).includes("inventory")) return <NotFoundPage />;
  return <PublicInventoryPage />;
}
