import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { DashboardLayout, ListLayout, SettingsLayout } from "../../components/layouts";
import type { Action, QueryState, Tab } from "../../components/ui";
import type { MemberActivity } from "./MemberActivity";
import type { MemberTab } from "./MemberPortalTabs";

const titles: Record<MemberTab, string> = { overview: "Your makerspace access", loans: "Loans", bookings: "Bookings", events: "Events", payments: "Payments", inbox: "Inbox", account: "Profile & card" };
const accountSections = [["profile", "Profile"], ["card", "Card"], ["certifications", "Certifications"], ["community", "Community"], ["invitations", "Invite a friend"], ["channels", "Channels"], ["phone", "Verify phone"]];

/** Presentation only: the portal keeps every permission check and query in MemberArea. */
export function MemberScreenLayout({ tab, state, children, member, name, slug, activity, primary, section, modules, hasPartnerEvents, accountSections: allowedAccountSections, accountSelfService, canRefer, status, requested }: {
  tab: MemberTab; state: QueryState; children: ReactNode; member: boolean; name: string; slug: string;
  activity?: MemberActivity; primary?: Action; section: string; modules: string[]; hasPartnerEvents: boolean; accountSections: string[]; accountSelfService: boolean; canRefer: boolean;
  status?: string; requested?: boolean;
}) {
  const location = useLocation();
  const publicBase = slug ? `/m/${slug}` : "";
  const memberBase = slug ? `/m/${slug}/member` : "/member";
  const link = (key: string) => `${location.pathname}?section=${key}`;
  const header = { title: titles[tab], eyebrow: t`Member area`, primary };
  // Inside the member shell already: one header, no second public header or footer.
  if (tab === "overview" && !member) {
    // A visitor can join; a pending or paused member must not be invited to "join" a space they are already in.
    const awaiting = requested || Boolean(status && /^(pending|awaiting)/.test(status));
    const paused = Boolean(status && status !== "revoked" && !awaiting);
    const joinable = !awaiting && !paused;
    return <DashboardLayout state={state}
      header={{ ...header, subtitle: awaiting ? t`Your request to join ${name} is awaiting review.` : paused ? t`Your access to ${name} is paused. Contact the front desk to restore it.` : t`Join ${name} and make something together.`,
        primary: primary ?? { label: t`Back to home`, href: publicBase || "/" } }}
      stats={[]} main={[{ title: joinable ? t`Join this makerspace` : t`Your membership`, content: <div className="grid gap-6">{children}</div>, empty: { message: joinable ? t`Joining options will appear here.` : t`Your membership details will appear here.` } }]} />;
  }
  if (tab === "overview") return <DashboardLayout state={state} header={{ ...header, subtitle: name }}
    callout={activity?.accountability?.waiver_acceptance_required ? { size: "banner", tone: "warn", lead: "Accept the updated waiver to keep borrowing.", action: { label: t`Read and accept`, href: "#current-waiver" } } : (activity?.active_hardware_loans ?? []).some(row => row.overdue) ? { size: "banner", tone: "warn", lead: "A loan is overdue.", body: t`Return it to the front desk, or check whether you can renew it.`, action: { label: t`View loans`, href: `${memberBase}/loans` } } : undefined}
    stats={activity ? [{ label: t`On loan`, value: (activity.active_hardware_loans ?? []).length, href: `${memberBase}/loans` },
      { label: t`Overdue`, value: (activity.active_hardware_loans ?? []).filter(row => row.overdue).length, href: `${memberBase}/loans` },
      ...(modules.includes("bookings") ? [{ label: t`Bookings`, value: activity.bookings?.upcoming.length ?? 0, href: `${memberBase}/bookings` }] : [])] : []}
    main={[{ title: t`Your membership`, content: <div className="grid gap-6">{children}</div>, empty: { message: t`Your membership details will appear here.` } }]}
 />;
  if (tab === "account") {
    const tabs: Tab[] = accountSections.filter(([key]) => allowedAccountSections.includes(key)).map(([key, label]) => ({ key, label: key === "invitations" && !canRefer ? t`Invitations` : label, href: link(key) }));
    if (section === "community") return <ListLayout state={state} header={{ ...header, secondary: { label: accountSelfService ? t`Account & security` : t`Two-step sign-in`, href: accountSelfService ? `${memberBase}/account` : "/mfa" } }} tabs={tabs} activeTab={section} body={{ kind: "rows", rows: children }} empty={{ message: t`No members have shared a profile yet.` }} />;
    return <SettingsLayout state={state} header={{ ...header, subtitle: t`Your identity in this makerspace.`, secondary: { label: accountSelfService ? t`Account & security →` : t`Two-step sign-in`, href: accountSelfService ? `${memberBase}/account` : "/mfa" } }}
      tabs={tabs} activeTab={section} sections={[{ id: section, title: tabs.find(row => row.key === section)?.label, rows: <div className="grid gap-6">{children}</div> }]} />;
  }
  if (tab === "inbox" && section === "preferences") return <SettingsLayout state={state} header={{ ...header, subtitle: t`Choose the messages you receive from this makerspace.` }} sections={[{ id: "preferences", title: t`Communication preferences`, rows: children }]} />;
  const tabs: Tab[] | undefined = tab === "loans" ? [["current", "Out now"], ["history", "History"]].map(([key, label]) => ({ key, label, href: link(key) }))
    : tab === "events" ? [["going", "Going"], ["past", "Past"], ...(hasPartnerEvents ? [["partners", "Partner events"]] : [])].map(([key, label]) => ({ key, label, href: link(key) })) : undefined;
  const browse = tab === "bookings" ? { label: t`Book a space`, href: `${publicBase}/bookings` }
    : tab === "loans" ? { label: t`Browse inventory`, href: `${publicBase}/inventory` }
      : tab === "events" ? { label: t`See events`, href: `${publicBase}/events` } : undefined;
  return <ListLayout state={state} header={{ ...header, primary: browse }} tabs={tabs} activeTab={section}
    body={{ kind: "rows", rows: children }} empty={{ message: t`Nothing here yet.` }} />;
}
