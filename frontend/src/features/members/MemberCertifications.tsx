import { formatDate } from "../../lib/format";
import { Trans } from "@lingui/react/macro";
import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, Pagination, StatusPill, RelativeTime } from "../../components/ui";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";

type Certification = { id: number; name: string; machine_type_name: string; type_active: boolean; is_live: boolean; granted_at: string; expires_at: string | null; revoked_at: string | null };
type Page = { count: number; next: string | null; previous: string | null; results: Certification[] };
export function MemberCertifications({ makerspaceId }: { makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["member", makerspaceId, "certifications", page], queryFn: () => memberRequest<Page>(`/member/makerspaces/${makerspaceId}/certifications?page=${page}`) });
  return <section className="desk-panel p-5" aria-label={t`Your certifications`}>
    <h2 className="title-panel">{t`Your certifications`}</h2>
    {query.isLoading ? <p role="status">{t`Loading certifications…`}</p> : null}
    {query.error instanceof Error ? <p role="alert" className="text-danger">{query.error.message}</p> : null}
    {query.isSuccess && !query.data.count ? <EmptyState message={t`No training records yet. Ask staff about a machine induction.`} /> : null}
    <ul className="mt-3 grid gap-3">{query.data?.results.map(row => <li key={row.id}><ListRow title={row.name}
      identity={{ kind: "icon", icon: "Wrench", tone: row.is_live ? "success" : "neutral" }}
      meta={<>{t`${row.machine_type_name} · Granted ${formatDate(row.granted_at)}`}<span className="block">{row.expires_at ? <Trans>Expires <RelativeTime date={row.expires_at} /></Trans> : t`Does not expire`}</span>{row.type_active && !row.revoked_at && row.expires_at && (!row.is_live || new Date(row.expires_at).getTime() - Date.now() < 14 * 86400000) ? <span className="mt-1 block text-warn-ink">{t`Ask staff to reassess and renew your training.`}</span> : null}</>}
      right={<StatusPill label={!row.type_active ? t`Type inactive` : row.revoked_at ? t`Revoked` : row.is_live ? t`Valid` : t`Expired`} tone={row.type_active && row.is_live && !row.revoked_at ? "success" : "warn"} />} /></li>)}</ul>
    {query.data && query.data.count > 24 ? <div className="mt-3"><Pagination page={page} totalPages={Math.ceil(query.data.count / 24)} count={query.data.count} pageSize={24} disabled={query.isFetching} onChange={setPage} /></div> : null}
  </section>;
}
