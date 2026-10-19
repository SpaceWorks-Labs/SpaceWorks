import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../components/layouts";
import { StructuredApiError } from "../../lib/api";
import { NotFoundPage } from "../NotFoundPage";
import { PublicProfilePage } from "../profile/PublicProfilePage";
import { HANDLE_PATTERN } from "../profile/publicProfileApi";
import { MakerspacePage } from "../public/MakerspacePage";
import { PublicOrganizationPage } from "../organizations/PublicOrganizationPage";
import { pageApiPath, usePageHandle } from "./pageApi";
import { CanonicalPageRedirect } from "./CanonicalPageRedirect";

export function PublicHandlePage() {
  const { handle = "" } = useParams();
  const valid = HANDLE_PATTERN.test(handle.toLowerCase());
  const query = usePageHandle(handle.toLowerCase(), valid);
  if (!valid || query.data === null || query.error instanceof StructuredApiError && query.error.status === 404) return <NotFoundPage />;
  // A failed refetch keeps the last resolution; the error state is only for a handle never resolved.
  if (query.error && !query.data) return <CenteredCardLayout state={{ status: "error", error: "Couldn't load this public page.", onRetry: () => { void query.refetch(); } }} title="Public page" body="" primary={{ label: "Try again", onClick: () => { void query.refetch(); } }} />;
  if (!query.data) return <CenteredCardLayout state={{ status: "loading" }} title="Opening public page…" body="" primary={{ label: "Loading", disabled: true }} />;
  const resolution = query.data;
  let url: URL; let path: string;
  try {
    url = new URL(resolution.canonical_url);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return <NotFoundPage />;
    path = pageApiPath(resolution.content_url);
  } catch { return <NotFoundPage />; }
  if (resolution.redirected) return <CanonicalPageRedirect url={url.href} />;
  if (resolution.kind === "member") return <PublicProfilePage />;
  const match = resolution.kind === "makerspace" ? /^\/public\/([^/]+)\/page\/$/.exec(path) : /^\/public\/organizations\/([^/]+)\/page\/$/.exec(path);
  if (!match) return <NotFoundPage />;
  const slug = decodeURIComponent(match[1]);
  return resolution.kind === "makerspace" ? <MakerspacePage profileSlug={slug} profileOnly /> : <PublicOrganizationPage profileSlug={slug} profileOnly />;
}
