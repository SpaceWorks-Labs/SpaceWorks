import { t } from "@lingui/core/macro";
import { useSearchParams } from "react-router-dom";
import { Tabs } from "../../components/ui";
import { useLiveUpdates } from "../../lib/useLiveUpdates";
import { AnnouncementFeed } from "./AnnouncementFeed";
import { MyNotificationSettings } from "./MyNotificationSettings";
import { FirebaseAlertsSetupLink } from "./firebase/FirebaseAlertsSetupLink";
import { PersonalInbox } from "./PersonalInbox";
import { PreferenceCentre } from "./PreferenceCentre";

export function MemberNotifications({ makerspaceId, features }: { makerspaceId: number; features: string[] }) {
  const inbox = features.includes("notifications.member_inbox");
  useLiveUpdates(inbox);
  const [search, setSearch] = useSearchParams();
  // Providers return the signed state; the settings screen retrieves its server-issued challenge.
  const section = search.has("state") ? "channels" : search.get("section");
  const setSection = (value: string) => { const next = new URLSearchParams(search); next.set("section", value); setSearch(next); };
  const tabs = [
    ...(inbox ? [{ key: "notices", label: t`Notices`, href: "#notices" }] : []),
    ...(inbox && features.includes("membership.broadcasts") ? [{ key: "announcements", label: t`Announcements`, href: "#announcements" }] : []),
    { key: "channels", label: t`Channels`, href: "#channels" },
    ...(features.includes("notifications.member_preferences") ? [{ key: "preferences", label: t`Preferences`, href: "#preferences" }] : []),
  ];
  const active = tabs.find(tab => tab.key === section)?.key ?? tabs[0].key;
  return <div className="grid gap-6"><Tabs tabs={tabs} activeKey={active} onChange={setSection} label={t`Inbox sections`}>
    {active === "announcements" && inbox && features.includes("membership.broadcasts") ? <AnnouncementFeed key={makerspaceId} makerspaceId={makerspaceId} /> : null}
    {active === "notices" && inbox ? <PersonalInbox makerspaceId={makerspaceId} member /> : null}
    {active === "channels" ? <section aria-label={t`Notification channels`} className="desk-panel p-5">
      <h2 className="title-panel">{t`Where you get notified`}</h2>
      <p className="mt-2 mb-4 text-sm text-muted">{t`Connect the chat apps this space offers and choose which notifications go where. Account and safety emails always stay on email.`}</p>
      {features.includes("notifications.web_push") ? <FirebaseAlertsSetupLink makerspaceId={makerspaceId} member /> : null}
      <MyNotificationSettings key={makerspaceId} makerspaceId={makerspaceId} member />
    </section> : null}
    {active === "preferences" && features.includes("notifications.member_preferences") ? <PreferenceCentre key={makerspaceId} makerspaceId={makerspaceId} digests={features.includes("notifications.digests")} /> : null}
  </Tabs></div>;
}
