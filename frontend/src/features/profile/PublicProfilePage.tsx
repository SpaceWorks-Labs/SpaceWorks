import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { ThemeToggle } from "../../components/ThemeToggle";
import { getAccessToken, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useOptionalTenant } from "../../lib/tenant";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { NotFoundPage } from "../NotFoundPage";
import { HANDLE_PATTERN, isProfileMissing, usePublicProfile } from "./publicProfileApi";
import { useProfileEditorHref } from "./useProfileEditorHref";
import { GlobalProfileView } from "./view/GlobalProfileView";

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

/** /:handle. Owner, signed-in member and logged-out visitor each get the body the server built for them. */
export function PublicProfilePage() {
  const { handle: raw = "" } = useParams();
  const handle = raw.toLowerCase();
  const navigate = useNavigate();
  const [sessionReady, setSessionReady] = useState(() => Boolean(getAccessToken()));
  // Existing tokens are refreshed on 401 by the profile request; missing tokens get one cookie restoration
  // attempt before the read, so a signed-in member is not served the logged-out view.
  useEffect(() => {
    if (sessionReady || !HANDLE_PATTERN.test(handle)) return;
    let active = true;
    void refreshAccessToken().catch(() => false).finally(() => { if (active) setSessionReady(true); });
    return () => { active = false; };
  }, [handle, sessionReady]);
  const profile = usePublicProfile(handle, sessionReady);
  const current = profile.data?.handle;
  const editor = useProfileEditorHref(profile.data?.audience === "owner");

  // A retired handle redirects server-side (302, 30 days); show the address the member uses now.
  useEffect(() => {
    if (current && current !== handle) navigate({ pathname: `/${current}`, search: window.location.search }, { replace: true });
  }, [current, handle, navigate]);

  // Grammar failures never reach the API; they, hidden, unknown and restricted profiles share one 404.
  if (!HANDLE_PATTERN.test(handle) || isProfileMissing(profile.error)) return <NotFoundPage />;
  const failure = profile.error instanceof StructuredApiError && profile.error.detail ? profile.error.detail : t`Couldn't load this profile. Try again.`;
  return <ProfileFrame state={!sessionReady || profile.isLoading ? { status: "loading" }
    : profile.error ? { status: "error", error: failure, onRetry: () => { void profile.refetch(); } } : { status: "ready" }}>
    {profile.data ? <GlobalProfileView key={profile.data.account_id} profile={profile.data} editHref={editor.href} /> : null}
  </ProfileFrame>;
}
