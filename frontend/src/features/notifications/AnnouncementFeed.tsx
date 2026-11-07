import { t } from "@lingui/core/macro";
import { EmptyState, ErrorBlock, ListRow, RelativeTime } from "../../components/ui";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { personalRecipientKey } from "./personalQueryKeys";

type Page = { next: string | null; previous: string | null; results: { id: number; title: string; summary: string; created_at: string }[] };

export function AnnouncementFeed({ makerspaceId }: { makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const feed = useQuery({ queryKey: ["notifications-inbox", makerspaceId, "member", personalRecipientKey(), "announcements", page],
    queryFn: () => memberRequest<Page>(`/notifications/announcements/${makerspaceId}?page=${page}`), refetchInterval: 60_000 });
  return <section className="desk-panel p-5" aria-label={t`Member announcements`}>
    <h2 className="title-panel">{t`Announcements`}</h2>
    {feed.isLoading ? <p role="status">{t`Loading announcements…`}</p> : null}
    {feed.error ? <ErrorBlock error={new Error(t`Couldn't load announcements. Try again.`)} onRetry={() => void feed.refetch()} /> : null}
    {feed.data?.results.length === 0 ? <EmptyState message={t`No announcements yet.`} /> : null}
    <ul className="mt-3 grid gap-3">{feed.data?.results.map((row) => <li key={row.id}><ListRow title={row.title} meta={<><span className="block whitespace-pre-wrap break-words">{row.summary}</span><RelativeTime date={row.created_at} /></>} /></li>)}</ul>
    {feed.data?.next || feed.data?.previous ? <div className="mt-3 flex flex-wrap gap-2"><button className="desk-button" disabled={!feed.data.previous || feed.isFetching} onClick={() => setPage(page - 1)}>{t`Previous`}</button><button className="desk-button" disabled={!feed.data.next || feed.isFetching} onClick={() => setPage(page + 1)}>{t`Next`}</button></div> : null}
  </section>;
}
