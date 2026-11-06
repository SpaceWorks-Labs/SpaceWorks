import { t } from "@lingui/core/macro";
import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../components/layouts";
import { publicV1Request, StructuredApiError } from "../../lib/api";
import { NotFoundPage } from "../NotFoundPage";
import { PublicEventDetailPage } from "../inventory/PublicEventDetailPage";
import { hostScope, pageApiPath, publicOrMissing, publicPagePolicy } from "../publicPages/pageApi";


export type PublicEventCode = import("../../generated/api").PublicEventCode;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** A 7-character base62 short code (L1). A UUID always has hyphens, so the shapes never overlap. */
const SHORT_CODE = /^[0-9A-Za-z]{7}$/;

export function PublicEventCodePage() {
  const { publicToken: code = "" } = useParams();
  const isUuid = UUID.test(code);
  const isShort = SHORT_CODE.test(code);
  // The short-link visit counter counts one person per page load: only the first resolve
  // carries `X-SW-Visit`, never a background refetch or a refocus.
  const visitSent = useRef(false);
  const query = useQuery({ queryKey: ["public-event-code", hostScope(), code], ...publicPagePolicy, enabled: isUuid || isShort,
    queryFn: () => {
      const headers: Record<string, string> = {};
      if (isShort && !visitSent.current) { visitSent.current = true; headers["X-SW-Visit"] = "1"; }
      return publicOrMissing(() => publicV1Request<PublicEventCode>(`/public/event-codes/${encodeURIComponent(code)}/`, { cache: "no-store", headers }));
    },
  });
  if (!(isUuid || isShort) || query.isSuccess && !query.data || query.error instanceof StructuredApiError && query.error.status === 404) return <NotFoundPage />;
  if (query.error) return <CenteredCardLayout state={{ status: "error", error: "Couldn't load this event.", onRetry: () => { void query.refetch(); } }} title={t`Event`} body="" primary={{ label: t`Try again`, onClick: () => { void query.refetch(); } }} />;
  if (!query.data) return <CenteredCardLayout state={{ status: "loading" }} title={t`Opening event…`} body="" primary={{ label: t`Loading`, disabled: true }} />;
  let match: RegExpExecArray | null;
  try { match = /^\/public\/([^/]+)\/events\/([^/]+)\/$/.exec(pageApiPath(query.data.content_url)); } catch { return <NotFoundPage />; }
  // A UUID address must name the event it resolved to; a short code resolves server-side.
  if (!match || !UUID.test(match[2]) || isUuid && match[2].toLowerCase() !== code.toLowerCase()) return <NotFoundPage />;
  return <PublicEventDetailPage resolvedSlug={decodeURIComponent(match[1])} resolvedToken={match[2]} canonicalUrl={query.data.canonical_url} />;
}
