import { useEffect } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { ThemeToggle } from "../../components/ThemeToggle";
import { StructuredApiError } from "../../lib/api";
import { readStorage } from "../../lib/safeStorage";
import { useOptionalTenant } from "../../lib/tenant";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { NotFoundPage } from "../NotFoundPage";
import { HANDLE_PATTERN, isProfileMissing, ownerEditKey, usePublicProfile } from "./publicProfileApi";
import { PublicProfileView } from "./PublicProfileView";

export function PublicProfilePage() {
  const { handle: raw = "" } = useParams();
  const handle = raw.toLowerCase();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const tenant = useOptionalTenant();
  const single = tenant?.mode === "single" ? tenant : null;
  const profile = usePublicProfile(handle);
  const current = profile.data?.handle;

  // A retired handle redirects server-side; show the address the member uses now.
  useEffect(() => {
    if (current && current !== raw) navigate({ pathname: `/${current}`, search: window.location.search }, { replace: true });
  }, [current, raw, navigate]);

  // Grammar failures never reach the API; they, unknown and unpublished handles share one 404.
  if (!HANDLE_PATTERN.test(handle) || isProfileMissing(profile.error)) return <NotFoundPage />;

  const editPath = readStorage(ownerEditKey(handle));
  const editHref = editPath.startsWith("/") && !editPath.startsWith("//") ? editPath : undefined;
  const spaceName = single?.bootstrap?.branding?.display_name || single?.bootstrap?.makerspace.name || "Space Works";
  const failure = profile.error instanceof StructuredApiError && profile.error.detail ? profile.error.detail : "Couldn't load this profile. Try again.";
  return <PublicLayout chrome="bar" width="narrow"
    makerspace={{ name: spaceName, slug: single?.slug ?? "", homeHref: "/" }}
    nav={[]} headerAction={{ label: "Sign in", href: "/member" }} liveStatus={<ThemeToggle />}
    state={profile.isLoading ? { status: "loading" } : profile.error ? { status: "error", error: failure, onRetry: () => { void profile.refetch(); } } : { status: "ready" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: "About", href: "/about" }, { label: "License", href: LICENSE_URL, external: true }] }}>
    {/* Chrome-only body: QueryContent inherits the layout's loading and error state. */}
    <QueryContent state={{ status: "ready" }}>{profile.data ? <PublicProfileView profile={profile.data} editHref={editHref}
      tab={search.get("tab") ?? "profile"} onTab={key => setSearch(previous => {
        const next = new URLSearchParams(previous);
        if (key === "profile") next.delete("tab"); else next.set("tab", key);
        return next;
      }, { replace: true })} /> : null}</QueryContent>
  </PublicLayout>;
}
