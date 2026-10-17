import { useState } from "react";
import { ErrorBlock, Pagination } from "../../components/ui";
import { PublicEventCards, PublicSpaceCards } from "../publicPages/PublicPageSections";
import { usePublicOrganizationEvents, usePublicOrganizationSpaces } from "./publicOrganizationsApi";

export function OrganizationPublicSpaces({ slug, token }: { slug: string; token?: string }) {
  const [page, setPage] = useState(1);
  const query = usePublicOrganizationSpaces(slug, page, true, token);
  return <div className="grid gap-4">
    {query.isLoading ? <p role="status">Loading linked makerspaces…</p> : query.error ? <ErrorBlock error={query.error} onRetry={() => { void query.refetch(); }} /> : query.data ? <>
      <PublicSpaceCards rows={query.data.results} /><Pagination page={page} pageSize={24} count={query.data.count} totalPages={Math.ceil(query.data.count / 24)} onChange={setPage} />
    </> : null}
  </div>;
}
export function OrganizationPublicEventPeriod({ slug, token, period }: { slug: string; token?: string; period: "upcoming" | "past" }) {
  const [page, setPage] = useState(1);
  const query = usePublicOrganizationEvents(slug, page, period, true, token);
  return <section className="grid gap-4" aria-label={period === "past" ? "Past event archive" : "Upcoming organization events"}>
    <h3 className="title-section">{period === "past" ? "Past event archive" : "Upcoming events"}</h3>
    {query.isLoading ? <p role="status">Loading {period} events…</p> : query.error ? <ErrorBlock error={query.error} onRetry={() => { void query.refetch(); }} /> : query.data ? <>
      <PublicEventCards rows={query.data.results} past={period === "past"} />
      <Pagination page={page} pageSize={24} count={query.data.count} totalPages={Math.ceil(query.data.count / 24)} onChange={setPage} />
    </> : null}
  </section>;
}
export function OrganizationPublicEvents({ slug, token }: { slug: string; token?: string }) {
  return <div className="grid gap-8"><OrganizationPublicEventPeriod slug={slug} token={token} period="upcoming" /><OrganizationPublicEventPeriod slug={slug} token={token} period="past" /></div>;
}
