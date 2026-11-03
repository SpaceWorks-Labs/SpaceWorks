import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { PublicPrintRequestPage } from "../printing/PublicPrintRequestPage";

/**
 * The old `/print` link. A tracking link (`?token=`) opens the job's status page; otherwise, where
 * the space takes job requests, the uniform "Request a job" form opens with the 3D printer chosen.
 * A space with job requests switched off keeps the old print form.
 */
export function PrintRequestAlias() {
  const { slug } = useParams();
  const [search] = useSearchParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const path = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const token = search.get("token")?.trim();
  if (token) return <Navigate replace to={path(`machine-service/requests/${encodeURIComponent(token)}`)} />;
  if (!bootstrap && !bootstrapQuery.isError) return <div role="status"><CenteredCardLayout state={{ status: "loading" }} title="Opening the print form…" body=""
    primary={{ label: "Loading…", disabled: true, disabledReason: "The page is opening." }} /></div>;
  if (bootstrap?.features.includes("machines.job_requests")) return <Navigate replace to={path("machine-jobs/new?type=printer")} />;
  return <PublicPrintRequestPage />;
}
