import type { ReactNode } from "react";
import { Home, Package, CalendarClock, Calendar, Wallet, Inbox, User } from "lucide-react";
import { AppShell, type ShellUser, type ShellWorkspace } from "../../components/shell";
import { useLocation } from "react-router-dom";

export const MEMBER_TABS = ["overview", "loans", "bookings", "events", "payments", "inbox", "account"] as const;
export type MemberTab = typeof MEMBER_TABS[number];

export function memberTabs(modules: string[]) {
  return MEMBER_TABS.filter((tab) => {
    if (["overview", "payments", "account"].includes(tab)) return true;
    if (tab === "bookings") return modules.includes("bookings");
    if (!modules.includes("membership")) return false;
    if (tab === "loans") return modules.includes("request_workflow");
    if (tab === "events") return modules.includes(tab);
    return true;
  });
}

export function useMemberTab(modules: string[]) {
  const location = useLocation();
  const segment = location.pathname.match(/^((?:\/m\/[^/]+)?\/member)(?:\/([^/]+))?\/?$/)?.[2];
  const requested = segment === "account-portal" ? "account" : segment;
  const tabs = memberTabs(modules);
  return tabs.find((tab) => tab === requested) ?? "overview";
}

/** URL destinations use ordinary navigation links; the main region remains the skip target. */
export function MemberPortalTabs({ modules, active, children, workspace, user }: {
  modules: string[]; active: MemberTab; children: ReactNode; workspace?: ShellWorkspace; user: ShellUser;
}) {
  const location = useLocation();
  const base = location.pathname.match(/^((?:\/m\/[^/]+)?\/member)(?:\/[^/]+)?\/?$/)?.[1] ?? "/member";
  const icons = { overview: Home, loans: Package, bookings: CalendarClock, events: Calendar, payments: Wallet, inbox: Inbox, account: User };
  const items = memberTabs(modules).map(tab => ({ key: tab, label: tab === "overview" ? "Home" : tab[0].toUpperCase() + tab.slice(1),
    href: `${base}/${tab === "account" ? "account-portal" : tab}`, icon: icons[tab] }));
  return <AppShell variant="member" compactNav="bottom-tabs" workspace={workspace} activeKey={active}
    nav={[{ key: "member", items }]} footerLinks={workspace ? [{ label: "View public page ↗", href: base.startsWith("/m/") ? base.replace(/\/member$/, "") : "/" }] : []}
    user={user}>
    <div className="space-y-5">{children}</div>
  </AppShell>;
}
