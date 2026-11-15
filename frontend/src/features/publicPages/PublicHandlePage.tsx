import { t } from "@lingui/core/macro";
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
import { isRetryable } from "../../lib/api/errors";

export function PublicHandlePage() {
  const { handle = "" } = useParams();
  const memberHandle = handle.startsWith("@");
  const normalized = handle.replace(/^@/, "").toLowerCase();
  const valid = HANDLE_PATTERN.test(normalized);
  const query = usePageHandle(normalized, valid && !memberHandle);
  if (!valid) return <NotFoundPage />;
  if (memberHandle) return <PublicProfilePage />;
  // The shared namespace also contains space and organization pages. Member cards
  // have their own resolver and retain the legacy /<handle> entry point.
  if (query.data === null || query.error instanceof StructuredApiError && query.error.status === 404) return <PublicProfilePage />;
  // A failed refetch keeps the last resolution; the error state is only for a handle never resolved.
  if (query.error && !query.data) return <CenteredCardLayout state={{ status: "error", error: t`Couldn't load this public page.`, onRetry: isRetryable(query.error) ? () => { void query.refetch(); } : undefined }} title={t`Public page`} body="" primary={isRetryable(query.error) ? { label: t`Try again`, onClick: () => { void query.refetch(); } } : { label: t`Home`, href: "/" }} />;
  if (!query.data) return <CenteredCardLayout state={{ status: "loading" }} title={t`Opening public page…`} body="" primary={{ label: t`Loading`, disabled: true }} />;
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
