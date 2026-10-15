import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { DashboardLayout, ListLayout, PublicLayout, SettingsLayout } from "../../components/layouts";
import type { Action, QueryState, Tab } from "../../components/ui";
import type { MemberActivity } from "./MemberActivity";
import type { MemberTab } from "./MemberPortalTabs";

const titles: Record<MemberTab, string> = { overview: "Your makerspace access", loans: "Loans", bookings: "Bookings", events: "Events", payments: "Payments", inbox: "Inbox", account: "Profile & card" };
const accountSections = [["profile", "Profile"], ["card", "Card"], ["certifications", "Certifications"], ["community", "Community"], ["invitations", "Invite a friend"]];

/** Presentation only: the portal keeps every permission check and query in MemberArea. */
export function MemberScreenLayout({ tab, state, children, member, name, slug, activity, primary, section, modules, hasPartnerEvents, accountSections: allowedAccountSections, accountSelfService, canRefer }: {
  tab: MemberTab; state: QueryState; children: ReactNode; member: boolean; name: string; slug: string;
  activity?: MemberActivity; primary?: Action; section: string; modules: string[]; hasPartnerEvents: boolean; accountSections: string[]; accountSelfService: boolean; canRefer: boolean;
}) {
  const location = useLocation();
  const publicBase = slug ? `/m/${slug}` : "";
  const memberBase = slug ? `/m/${slug}/member` : "/member";
  const link = (key: string) => `${location.pathname}?section=${key}`;
  const header = { title: titles[tab], eyebrow: "Member area", primary };
  if (tab === "overview" && !member) return <PublicLayout standalone={false} state={state}
    makerspace={{ name, slug }} nav={[]} headerAction={{ label: "Browse catalogue", href: publicBase || "/" }}
    header={{ ...header, subtitle: `Join ${name} and make something together.` }} footer={{ links: [] }}>
    <div className="grid gap-6">{children}</div>
  </PublicLayout>;
  if (tab === "overview") return <DashboardLayout state={state} header={{ ...header, subtitle: name }}
    callout={activity?.accountability?.waiver_acceptance_required ? { size: "banner", tone: "warn", lead: "Accept the updated waiver to keep borrowing.", action: { label: "Read and accept", href: "#current-waiver" } } : (activity?.active_hardware_loans ?? []).some(row => row.overdue) ? { size: "banner", tone: "warn", lead: "A loan is overdue.", body: "Return it to the front desk, or check whether you can renew it.", action: { label: "View loans", href: `${memberBase}/loans` } } : undefined}
    stats={activity ? [{ label: "On loan", value: (activity.active_hardware_loans ?? []).length, href: `${memberBase}/loans` },
      { label: "Overdue", value: (activity.active_hardware_loans ?? []).filter(row => row.overdue).length, href: `${memberBase}/loans` },
      ...(modules.includes("bookings") ? [{ label: "Bookings", value: activity.bookings?.upcoming.length ?? 0, href: `${memberBase}/bookings` }] : [])] : []}
    main={[{ title: "Your membership", content: <div className="grid gap-6">{children}</div>, empty: { message: "Your membership details will appear here." } }]}
 />;
  if (tab === "account") {
    const tabs: Tab[] = accountSections.filter(([key]) => allowedAccountSections.includes(key)).map(([key, label]) => ({ key, label: key === "invitations" && !canRefer ? "Invitations" : label, href: link(key) }));
    if (section === "community") return <ListLayout state={state} header={{ ...header, secondary: { label: accountSelfService ? "Account & security" : "Two-step sign-in", href: accountSelfService ? `${memberBase}/account` : "/mfa" } }} tabs={tabs} activeTab={section} body={{ kind: "rows", rows: children }} empty={{ message: "No members have shared a profile yet." }} />;
    return <SettingsLayout state={state} header={{ ...header, subtitle: "Your identity in this makerspace.", secondary: { label: accountSelfService ? "Account & security →" : "Two-step sign-in", href: accountSelfService ? `${memberBase}/account` : "/mfa" } }}
      tabs={tabs} activeTab={section} sections={[{ id: section, title: tabs.find(row => row.key === section)?.label, rows: <div className="grid gap-6">{children}</div> }]} />;
  }
  if (tab === "inbox" && section === "preferences") return <SettingsLayout state={state} header={{ ...header, subtitle: "Choose the messages you receive from this makerspace." }} sections={[{ id: "preferences", title: "Communication preferences", rows: children }]} />;
  const tabs: Tab[] | undefined = tab === "loans" ? [["current", "Out now"], ["history", "History"]].map(([key, label]) => ({ key, label, href: link(key) }))
    : tab === "events" ? [["going", "Going"], ["past", "Past"], ...(hasPartnerEvents ? [["partners", "Partner events"]] : [])].map(([key, label]) => ({ key, label, href: link(key) })) : undefined;
  const browse = tab === "bookings" ? { label: "Book a space", href: `${publicBase}/bookings` }
    : tab === "loans" ? { label: "Browse catalogue", href: publicBase || "/" }
      : tab === "events" ? { label: "See events", href: `${publicBase}/events` } : undefined;
  return <ListLayout state={state} header={{ ...header, primary: browse }} tabs={tabs} activeTab={section}
    body={{ kind: "rows", rows: children }} empty={{ message: "Nothing here yet." }} />;
}
