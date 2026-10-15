import { useSearchParams } from "react-router-dom";
import { Tabs } from "../../components/ui";
import { useLiveUpdates } from "../../lib/useLiveUpdates";
import { AnnouncementFeed } from "./AnnouncementFeed";
import { PersonalInbox } from "./PersonalInbox";
import { PreferenceCentre } from "./PreferenceCentre";

export function MemberNotifications({ makerspaceId, features }: { makerspaceId: number; features: string[] }) {
  const inbox = features.includes("notifications.member_inbox");
  useLiveUpdates(inbox);
  const [search, setSearch] = useSearchParams();
  const section = search.get("section") || "notices";
  const setSection = (value: string) => { const next = new URLSearchParams(search); next.set("section", value); setSearch(next); };
  const tabs = [{ key: "notices", label: "Notices", href: "#notices" }, ...(inbox && features.includes("membership.broadcasts") ? [{ key: "announcements", label: "Announcements", href: "#announcements" }] : []), ...(features.includes("notifications.member_preferences") ? [{ key: "preferences", label: "Preferences", href: "#preferences" }] : [])];
  const active = tabs.some(tab => tab.key === section) ? section : "notices";
  return <div className="grid gap-6"><Tabs tabs={tabs} activeKey={active} onChange={setSection} label="Inbox sections" />
    {active === "announcements" && inbox && features.includes("membership.broadcasts") ? <AnnouncementFeed key={makerspaceId} makerspaceId={makerspaceId} /> : null}
    {active === "notices" && inbox ? <PersonalInbox makerspaceId={makerspaceId} member /> : null}
    {active === "preferences" && features.includes("notifications.member_preferences") ? <PreferenceCentre key={makerspaceId} makerspaceId={makerspaceId} digests={features.includes("notifications.digests")} /> : null}
  </div>;
}
