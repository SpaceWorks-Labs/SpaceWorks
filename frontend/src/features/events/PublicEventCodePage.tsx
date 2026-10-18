import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../components/layouts";
import { publicV1Request, StructuredApiError } from "../../lib/api";
import { NotFoundPage } from "../NotFoundPage";
import { PublicEventDetailPage } from "../inventory/PublicEventDetailPage";
import { hostScope, pageApiPath, publicOrMissing, publicPagePolicy } from "../publicPages/pageApi";
import type { PublicEventDetail } from "./eventTicketTypes";

export type PublicEventCode = PublicEventDetail & { canonical_url: string; content_url: string };
export function PublicEventCodePage() {
  const { publicToken = "" } = useParams();
  const valid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(publicToken);
  const query = useQuery({ queryKey: ["public-event-code", hostScope(), publicToken], ...publicPagePolicy, enabled: valid,
    queryFn: () => publicOrMissing(() => publicV1Request<PublicEventCode>(`/public/event-codes/${encodeURIComponent(publicToken)}/`, { cache: "no-store" })),
  });
  if (!valid || query.isSuccess && !query.data || query.error instanceof StructuredApiError && query.error.status === 404) return <NotFoundPage />;
  if (query.error) return <CenteredCardLayout state={{ status: "error", error: "Couldn't load this event.", onRetry: () => { void query.refetch(); } }} title="Event" body="" primary={{ label: "Try again", onClick: () => { void query.refetch(); } }} />;
  if (!query.data) return <CenteredCardLayout state={{ status: "loading" }} title="Opening event…" body="" primary={{ label: "Loading", disabled: true }} />;
  let match: RegExpExecArray | null;
  try { match = /^\/public\/([^/]+)\/events\/([^/]+)\/$/.exec(pageApiPath(query.data.content_url)); } catch { return <NotFoundPage />; }
  if (!match || match[2].toLowerCase() !== publicToken.toLowerCase()) return <NotFoundPage />;
  return <PublicEventDetailPage resolvedSlug={decodeURIComponent(match[1])} resolvedToken={publicToken} canonicalUrl={query.data.canonical_url} />;
}
