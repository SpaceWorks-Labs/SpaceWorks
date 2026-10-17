import { useParams, useSearchParams } from "react-router-dom";
import { useTenant } from "../../lib/tenant";
import { NotFoundPage } from "../NotFoundPage";
import { PasswordRecoveryFlow } from "./PasswordRecoveryFlow";

/** Recovery is a signed-out route: never restore a session or mount the staff console. */
export function ConsolePasswordResetPage() {
  const tenant = useTenant();
  const { slug: routeSlug } = useParams();
  const [params] = useSearchParams();
  const platform = !routeSlug && (params.get("context") === "platform" || tenant.mode === "central");
  if (tenant.mode === "single" && routeSlug && routeSlug !== tenant.slug) return <NotFoundPage />;
  const slug = routeSlug || tenant.slug;
  const recoveryContext = platform ? { context: "platform" as const } : { context: "staff" as const, makerspace: slug };
  const signInHref = platform ? "/admin?context=platform" : tenant.mode === "single" ? "/admin" : `/m/${encodeURIComponent(slug)}/admin`;
  return <PasswordRecoveryFlow key={`${recoveryContext.context}:${slug}`} recoveryContext={recoveryContext}
    signInHref={signInHref} initialStep={params.get("step") === "request" ? "request" : "confirm"} />;
}
