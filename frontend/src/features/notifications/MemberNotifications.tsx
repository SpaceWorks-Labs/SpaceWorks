import { useSearchParams } from "react-router-dom";
import { Tabs } from "../../components/ui";
import { useLiveUpdates } from "../../lib/useLiveUpdates";
import { AnnouncementFeed } from "./AnnouncementFeed";
import { MyNotificationSettings } from "./MyNotificationSettings";
import { PersonalInbox } from "./PersonalInbox";
import { PreferenceCentre } from "./PreferenceCentre";

export function MemberNotifications({ makerspaceId, features }: { makerspaceId: number; features: string[] }) {
  const inbox = features.includes("notifications.member_inbox");
  useLiveUpdates(inbox);
  const [search, setSearch] = useSearchParams();
  // Providers return the signed state; the settings screen retrieves its server-issued challenge.
  const section = search.has("state") ? "channels" : search.get("section") || "notices";
  const setSection = (value: string) => { const next = new URLSearchParams(search); next.set("section", value); setSearch(next); };
  const tabs = [{ key: "notices", label: "Notices", href: "#notices" }, ...(inbox && features.includes("membership.broadcasts") ? [{ key: "announcements", label: "Announcements", href: "#announcements" }] : []),
    { key: "channels", label: "Channels", href: "#channels" },
    ...(features.includes("notifications.member_preferences") ? [{ key: "preferences", label: "Preferences", href: "#preferences" }] : [])];
  const active = tabs.some(tab => tab.key === section) ? section : "notices";
  return <div className="grid gap-6"><Tabs tabs={tabs} activeKey={active} onChange={setSection} label="Inbox sections">
    {active === "announcements" && inbox && features.includes("membership.broadcasts") ? <AnnouncementFeed key={makerspaceId} makerspaceId={makerspaceId} /> : null}
    {active === "notices" && inbox ? <PersonalInbox makerspaceId={makerspaceId} member /> : null}
    {active === "channels" ? <section aria-label="Notification channels" className="desk-panel p-5">
      <h2 className="title-panel">Where you get notified</h2>
      <p className="mt-2 mb-4 text-sm text-muted">Connect the chat apps this space offers and choose which notifications go where. Account and safety emails always stay on email.</p>
      <MyNotificationSettings key={makerspaceId} makerspaceId={makerspaceId} member />
    </section> : null}
    {active === "preferences" && features.includes("notifications.member_preferences") ? <PreferenceCentre key={makerspaceId} makerspaceId={makerspaceId} digests={features.includes("notifications.digests")} /> : null}
  </Tabs></div>;
}
