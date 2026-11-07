import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "../../components/layouts";
import { getAccessToken, staffRequest } from "../../lib/api";
import { browserSessionIdentity } from "../../lib/api/reauthentication";
import { eventErrorText } from "../staff/eventUi";
type Insights = {
  window: { starts_at: string; ends_at: string };
  growth: { date: string; accounts: number; makerspaces: number }[];
  staff_mfa: { active: number; enabled: number; without_mfa: number; adoption_percent: number | null };
  outbox: { kind: string; pending: number; failed: number; oldest_pending_at: string | null }[];
};
export function PlatformInsightsPage() {
  const query = useQuery({ queryKey: ["platform-insights", browserSessionIdentity(getAccessToken("platform"))], queryFn: () => staffRequest<Insights>("/admin/platform/insights/", {}, "platform"), refetchInterval: 60000 });
  const row = query.data;
  return <DashboardLayout header={{ eyebrow: t`Platform`, title: t`Platform insights`, subtitle: t`Counts across the platform over the last 30 days.` }} state={{ status: query.isLoading ? "loading" : query.error ? "error" : "ready", error: query.error ? eventErrorText(query.error) : undefined, onRetry: () => { void query.refetch(); } }}
    stats={row ? [{ label: t`Active staff`, value: row.staff_mfa.active }, { label: t`MFA enabled`, value: row.staff_mfa.enabled }, { label: t`Without MFA`, value: row.staff_mfa.without_mfa }, { label: t`MFA adoption`, value: row.staff_mfa.adoption_percent === null ? "—" : `${row.staff_mfa.adoption_percent}%` }] : []}
    main={[{ title: t`Account and makerspace growth`, empty: { message: t`No growth data for this window.` }, isEmpty: row?.growth.length === 0,
      content: row ? <div className="overflow-x-auto rounded-2xl border border-line bg-panel p-4"><table className="w-full text-left text-sm"><caption className="mb-2 text-left text-muted">{row.window.starts_at.slice(0, 10)} to {row.window.ends_at.slice(0, 10)}</caption><thead><tr><th scope="col" className="p-2">{t`Date`}</th><th scope="col" className="p-2">{t`Accounts`}</th><th scope="col" className="p-2">{t`Makerspaces`}</th></tr></thead><tbody>{row.growth.map(day => <tr key={day.date}><th scope="row" className="p-2 font-normal">{day.date}</th><td className="p-2 tabular-nums">{day.accounts}</td><td className="p-2 tabular-nums">{day.makerspaces}</td></tr>)}</tbody></table></div> : null },
    { title: t`Notification outbox`, empty: { message: t`No pending or failed delivery groups.` }, isEmpty: row?.outbox.length === 0,
      content: row ? <ul className="grid gap-3">{row.outbox.map(item => <li key={item.kind} className="grid gap-2 rounded-2xl border border-line bg-panel p-4"><h3 className="font-semibold">{item.kind.replace(/_/g, " ")}</h3><p className="text-sm">{t`${item.pending} pending · ${item.failed} failed`}</p><p className="text-xs text-muted">{t`Oldest pending: `}{item.oldest_pending_at ? new Date(item.oldest_pending_at).toLocaleString(formatLocale()) : t`None`}</p></li>)}</ul> : null }]} />;
}
