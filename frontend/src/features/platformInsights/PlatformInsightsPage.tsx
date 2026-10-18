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
  return <DashboardLayout header={{ eyebrow: "Platform", title: "Platform insights", subtitle: "Counts across the platform over the last 30 days." }} state={{ status: query.isLoading ? "loading" : query.error ? "error" : "ready", error: query.error ? eventErrorText(query.error) : undefined, onRetry: () => { void query.refetch(); } }}
    stats={row ? [{ label: "Active staff", value: row.staff_mfa.active }, { label: "MFA enabled", value: row.staff_mfa.enabled }, { label: "Without MFA", value: row.staff_mfa.without_mfa }, { label: "MFA adoption", value: row.staff_mfa.adoption_percent === null ? "—" : `${row.staff_mfa.adoption_percent}%` }] : []}
    main={[{ title: "Account and makerspace growth", empty: { message: "No growth data for this window." }, isEmpty: row?.growth.length === 0,
      content: row ? <div className="overflow-x-auto rounded-2xl border border-line bg-panel p-4"><table className="w-full text-left text-sm"><caption className="mb-2 text-left text-muted">{row.window.starts_at.slice(0, 10)} to {row.window.ends_at.slice(0, 10)}</caption><thead><tr><th scope="col" className="p-2">Date</th><th scope="col" className="p-2">Accounts</th><th scope="col" className="p-2">Makerspaces</th></tr></thead><tbody>{row.growth.map(day => <tr key={day.date}><th scope="row" className="p-2 font-normal">{day.date}</th><td className="p-2 tabular-nums">{day.accounts}</td><td className="p-2 tabular-nums">{day.makerspaces}</td></tr>)}</tbody></table></div> : null },
    { title: "Notification outbox", empty: { message: "No pending or failed delivery groups." }, isEmpty: row?.outbox.length === 0,
      content: row ? <ul className="grid gap-3">{row.outbox.map(item => <li key={item.kind} className="grid gap-2 rounded-2xl border border-line bg-panel p-4"><h3 className="font-semibold">{item.kind.replace(/_/g, " ")}</h3><p className="text-sm">{item.pending} pending · {item.failed} failed</p><p className="text-xs text-muted">Oldest pending: {item.oldest_pending_at ? new Date(item.oldest_pending_at).toLocaleString() : "None"}</p></li>)}</ul> : null }]} />;
}
