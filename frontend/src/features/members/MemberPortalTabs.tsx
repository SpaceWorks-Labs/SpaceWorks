import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { Home, Package, CalendarClock, Calendar, Wallet, Inbox, User } from "lucide-react";
import { AppShell, type ShellUser, type ShellWorkspace } from "../../components/shell";
import { useLocation } from "react-router-dom";
import { ThemeToggle } from "../../components/ThemeToggle";
import { PlatformNoticeBanners } from "../platformNotices/PlatformNoticeBanners";
import { PausedSpacePage } from "../platformNotices/PausedSpacePage";
import { spaceNotice, usePlatformNotices } from "../platformNotices/platformNoticesApi";

export const MEMBER_TABS = ["overview", "loans", "bookings", "events", "payments", "inbox", "account"] as const;
export type MemberTab = typeof MEMBER_TABS[number];

/** `features` (the bootstrap capability list) is optional: callers without it keep the module-only rule. */
export function memberTabs(modules: string[], features?: readonly string[]) {
  return MEMBER_TABS.filter((tab) => {
    if (["overview", "payments", "account"].includes(tab)) return true;
    if (tab === "bookings") return modules.includes("bookings");
    if (!modules.includes("membership")) return false;
    // Lending switched off (`loans.enabled`) removes the tab, as it removes the staff loan tabs (#218).
    if (tab === "loans") return modules.includes("request_workflow") && (!features || features.includes("loans.enabled"));
    if (tab === "events") return modules.includes(tab);
    // The member inbox is the notifications module's surface: no tab while it is off (#183B).
    if (tab === "inbox") return modules.includes("notifications");
    return true;
  });
}

/** The tab's name in the nav; translated (the nav used to capitalise the raw key). */
export function memberTabLabel(tab: MemberTab): string {
  return { overview: t`Home`, loans: t`Loans`, bookings: t`Bookings`, events: t`Events`, payments: t`Payments`,
    inbox: t`Inbox`, account: t`Account` }[tab];
}

export function useMemberTab(modules: string[], features?: readonly string[]) {
  const location = useLocation();
  const segment = location.pathname.match(/^((?:\/m\/[^/]+)?\/member)(?:\/([^/]+))?\/?$/)?.[2];
  const requested = segment === "account-portal" ? "account" : segment;
  const tabs = memberTabs(modules, features);
  return tabs.find((tab) => tab === requested) ?? "overview";
}

/** URL destinations use ordinary navigation links; the main region remains the skip target. */
export function MemberPortalTabs({ modules, features, active, children, workspace, user, space }: {
  modules: string[]; features?: readonly string[]; active: MemberTab; children: ReactNode; workspace?: ShellWorkspace; user: ShellUser;
  /** The member's space, for the platform banners and the paused page. */
  space?: { id?: number; slug?: string };
}) {
  const location = useLocation();
  // Signed-in only: an anonymous visitor has no notices, and a paused space 404s its bootstrap instead.
  const notices = usePlatformNotices(Boolean(user.onSignOut), "person");
  const paused = space ? spaceNotice(notices.data, space) : undefined;
  // Deeper member pages (member/machine-jobs/12) keep the tenant prefix for the nav links too.
  const base = location.pathname.match(/^((?:\/m\/[^/]+)?\/member)(?:\/.*)?$/)?.[1] ?? "/member";
  const icons = { overview: Home, loans: Package, bookings: CalendarClock, events: Calendar, payments: Wallet, inbox: Inbox, account: User };
  // A signed-out visitor gets Home (sign in, join) only: every other tab is their own
  // account's data, which the server answers with 401.
  const items = (user.onSignOut ? memberTabs(modules, features) : (["overview"] as const)).map(tab => ({ key: tab, label: memberTabLabel(tab),
    href: `${base}/${tab === "account" ? "account-portal" : tab}`, icon: icons[tab] }));
  if (paused?.state === "suspended") {
    return <PausedSpacePage name={paused.name} reason={paused.reason} primary={{ label: t`Find another space`, href: "/" }}
      escape={user.onSignOut ? { label: t`Sign out`, onClick: user.onSignOut } : undefined} />;
  }
  return <AppShell variant="member" compactNav="bottom-tabs" workspace={workspace} activeKey={active}
    nav={[{ key: "member", items }]} footerLinks={workspace ? [{ label: t`View public page ↗`, href: base.startsWith("/m/") ? base.replace(/\/member$/, "") : "/" }] : []}
    user={user}>
    {/* Below lg the shell pins a bottom tab bar. Sticky save bars sit above it, and a field
        scrolled into view for the on-screen keyboard keeps clear of it. A list row's text keeps
        at least 12rem, so on a phone its status/amount/actions drop under the title instead of
        squeezing it to a few characters per line. */}
    <div className="min-w-0 space-y-5 [&_:is(input,select,textarea)]:scroll-mb-28 [&_.sticky.bottom-0]:bottom-[calc(var(--shell-bottom-tabs,0px)+env(safe-area-inset-bottom,0px))] lg:[&_.sticky.bottom-0]:bottom-0 [&_.rounded-2xl.flex-wrap>:first-child]:basis-48">
      {/* Visible on every member screen, as the old header's toggle was; the user menu keeps its copy. */}
      <div className="flex justify-end"><ThemeToggle variant="icon" /></div>
      <PlatformNoticeBanners data={notices.data} space={space} surface="member" />
      {children}</div>
  </AppShell>;
}
