import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { ThemeToggle } from "../../components/ThemeToggle";
import { getAccessToken, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { ErrorBlock } from "../../components/ui";
import { useOptionalTenant } from "../../lib/tenant";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { NotFoundPage } from "../NotFoundPage";
import { HANDLE_PATTERN, isProfileMissing, usePublicProfile } from "./publicProfileApi";
import { PublicProfileView } from "./PublicProfileView";
import { useProfileEditorHref } from "./useProfileEditorHref";

export function PublicProfilePage() {
  const { handle: raw = "" } = useParams();
  const handle = raw.toLowerCase();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const tenant = useOptionalTenant();
  const single = tenant?.mode === "single" ? tenant : null;
  const [sessionReady, setSessionReady] = useState(() => Boolean(getAccessToken()));
  // Existing tokens are refreshed on 401 by the profile request; missing tokens
  // get one cookie restoration attempt before the anonymous read.
  useEffect(() => {
    if (sessionReady || !HANDLE_PATTERN.test(handle)) return;
    let active = true;
    // A signed-out or unavailable optional session must still allow the public read.
    void refreshAccessToken().catch(() => false).finally(() => { if (active) setSessionReady(true); });
    return () => { active = false; };
  }, [handle, sessionReady]);
  const profile = usePublicProfile(handle, sessionReady);
  const editor = useProfileEditorHref(profile.data?.handle ?? handle, sessionReady && Boolean(profile.data?.viewer_is_owner), single !== null);
  const current = profile.data?.handle;

  // A retired handle redirects server-side; show the address the member uses now.
  useEffect(() => {
    if (current && current !== raw) navigate({ pathname: `/${current}`, search: window.location.search }, { replace: true });
  }, [current, raw, navigate]);

  // Grammar failures never reach the API; they, unknown and unpublished handles share one 404.
  if (!HANDLE_PATTERN.test(handle) || isProfileMissing(profile.error)) return <NotFoundPage />;

  const spaceName = single?.bootstrap?.branding?.display_name || single?.bootstrap?.makerspace.name || "Space Works";
  const failure = profile.error instanceof StructuredApiError && profile.error.detail ? profile.error.detail : "Couldn't load this profile. Try again.";
  return <PublicLayout chrome="bar" width="narrow"
    makerspace={{ name: spaceName, slug: single?.slug ?? "", homeHref: "/" }}
    nav={[]} headerAction={{ label: t`Sign in`, href: "/member" }} liveStatus={<ThemeToggle />}
    state={!sessionReady || profile.isLoading ? { status: "loading" } : profile.error ? { status: "error", error: failure, onRetry: () => { void profile.refetch(); } } : { status: "ready" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }] }}>
    {/* Chrome-only body: QueryContent inherits the layout's loading and error state. */}
    <QueryContent state={{ status: "ready" }}>
      {profile.data?.viewer_is_owner && editor.error ? <ErrorBlock error={new Error(t`Couldn't find your profile editor. Try again.`)}
        onRetry={() => { void editor.refetch(); }} /> : null}
      {profile.data ? <PublicProfileView key={profile.data.handle} profile={profile.data} editHref={editor.href}
      tab={search.get("tab") ?? "profile"} onTab={key => setSearch(previous => {
        const next = new URLSearchParams(previous);
        if (key === "profile") next.delete("tab"); else next.set("tab", key);
        return next;
      }, { replace: true })} /> : null}</QueryContent>
  </PublicLayout>;
}
