import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { ThemeToggle } from "../../components/ThemeToggle";
import { StructuredApiError } from "../../lib/api";
import { useOptionalTenant } from "../../lib/tenant";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { NotFoundPage } from "../NotFoundPage";
import { HANDLE_PATTERN, isProfileMissing, usePublicProfile } from "./publicProfileApi";
import { PublicProfileCard } from "./view/PublicProfileCard";
import { isRetryable } from "../../lib/api/errors";

/** Chrome shared by the handle page and the by-account page. */
export function ProfileFrame({ state, children }: { state: Parameters<typeof PublicLayout>[0]["state"]; children: React.ReactNode }) {
  const tenant = useOptionalTenant();
  const single = tenant?.mode === "single" ? tenant : null;
  const spaceName = single?.bootstrap?.branding?.display_name || single?.bootstrap?.makerspace.name || "Space Works";
  return <PublicLayout chrome="bar" width="narrow" makerspace={{ name: spaceName, slug: single?.slug ?? "", homeHref: "/" }}
    nav={[]} headerAction={{ label: t`Sign in`, href: "/member" }} liveStatus={<ThemeToggle />} state={state}
    footer={{ credit: "Powered by Space Works", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }] }}>
    {/* Chrome-only body: QueryContent inherits the layout's loading and error state. */}
    <QueryContent state={{ status: "ready" }}>{children}</QueryContent>
  </PublicLayout>;
}

/** /@<handle>, with the old /<handle> URL retained as an alias. */
export function PublicProfilePage() {
  const { handle: raw = "" } = useParams();
  const handle = raw.replace(/^@/, "").toLowerCase();
  const navigate = useNavigate();
  const profile = usePublicProfile(handle);
  const current = profile.data?.handle;

  // A retired handle redirects server-side (302, 30 days); show the address the member uses now.
  useEffect(() => {
    if (current && current !== handle) navigate({ pathname: `/@${current}`, search: window.location.search }, { replace: true });
  }, [current, handle, navigate]);

  // Grammar failures never reach the API; missing handles use the shared 404 page.
  if (!HANDLE_PATTERN.test(handle) || isProfileMissing(profile.error)) return <NotFoundPage />;
  const failure = profile.error instanceof StructuredApiError && profile.error.detail ? profile.error.detail : t`Couldn't load this profile. Try again.`;
  return <ProfileFrame state={profile.isLoading ? { status: "loading" }
    : profile.error ? { status: "error", error: failure, onRetry: isRetryable(profile.error) ? () => { void profile.refetch(); } : undefined } : { status: "ready" }}>
    {profile.data ? <PublicProfileCard profile={profile.data} /> : null}
  </ProfileFrame>;
}
