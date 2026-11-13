import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListLayout } from "../../components/layouts";
import { getAccessToken, memberRequest } from "../../lib/api";
import { browserSessionIdentity } from "../../lib/api/reauthentication";
import { eventErrorText } from "../staff/eventUi";
type Activity = { id: number; action: string; created_at: string };
export function SecurityActivityPage() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["member-security-activity", browserSessionIdentity(getAccessToken("person")), page], queryFn: () => memberRequest<{ count: number; results: Activity[] }>(`/member/security-activity/?page=${page}`), staleTime: 0 });
  return <ListLayout header={{ title: t`Security activity`, subtitle: t`Recent sign-in and security changes for your account.` }} state={{ status: query.isLoading ? "loading" : query.error ? "error" : "ready", error: query.error ? eventErrorText(query.error) : undefined, onRetry: () => { void query.refetch(); } }} isEmpty={query.data?.count === 0} empty={{ message: t`No recent security activity.` }} body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="flex flex-wrap justify-between gap-2 rounded-2xl border border-line bg-panel p-4"><h2 className="font-semibold">{row.action.replace(/[._]/g, " ")}</h2><time className="text-sm text-muted" dateTime={row.created_at}>{new Date(row.created_at).toLocaleString(formatLocale())}</time></article>) }} pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }} />;
}
