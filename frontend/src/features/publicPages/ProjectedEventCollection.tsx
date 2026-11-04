import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorBlock, Pagination } from "../../components/ui";
import { publicV1Request, tenantPublicRequest } from "../../lib/api";
import { hostScope, pageApiPath, publicPagePolicy } from "./pageApi";
import { PublicEventCards } from "./PublicCollectionCards";
import type { PublicPageProjection, PublicSectionPayloads } from "./pageTypes";

export function ProjectedEventCollection({ collection, token, slug }: {
  collection: PublicSectionPayloads["upcoming_events"]; token?: string; slug?: string;
}) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["public-page-collection", hostScope(), slug, collection.collection_url, token, page], ...publicPagePolicy,
    enabled: page > 1, queryFn: async () => {
      const path = pageApiPath(collection.collection_url);
      const separator = path.includes("?") ? "&" : "?";
      const url = `${path}${separator}events_page=${page}`;
      const projection = await (slug ? tenantPublicRequest<PublicPageProjection>(slug, url, { cache: "no-store" }) : publicV1Request<PublicPageProjection>(url, { cache: "no-store" }));
      return projection.sections.find(section => section.type === "upcoming_events")?.payload ?? { results: [], count: 0 };
    },
  });
  const data = page === 1 ? collection : query.error ? undefined : query.data;
  return <div className="grid gap-4">
    {page > 1 && query.isLoading ? <p role="status">Loading public events…</p> : query.error && page > 1 ? <ErrorBlock error={query.error} onRetry={() => { void query.refetch(); }} /> : data ? <PublicEventCards rows={data.results} /> : null}
    <Pagination page={page} pageSize={24} count={data?.count ?? collection.count} totalPages={Math.ceil((data?.count ?? collection.count) / 24)} onChange={setPage} />
  </div>;
}
