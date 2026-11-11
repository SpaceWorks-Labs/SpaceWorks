import type { StaffAuthUser } from "../../../lib/api";
import type { Makerspace } from "../panels/shared";
import { AnalyticsPanel, PlatformSettingsPanel } from "../StaffTabLoaders";
import { PlatformAccessPage } from "./PlatformAccessPage";
import { PlatformDataPage } from "./PlatformDataPage";
import { PlatformSecurityPage } from "./PlatformSecurityPage";
import { PlatformInboxPage } from "./PlatformInboxPage";
import { PlatformLimitsPage, PlatformLimitsRedirect } from "../platformSpaces/PlatformLimitsPage";

type Props = { activeTab: string; activeMakerspace?: Makerspace; makerspaces: Makerspace[]; currentUser: StaffAuthUser; onAuthRefresh: () => void };

/** Renders one of `PLATFORM_CONSOLE_PAGES` (platformConsolePages.ts). */
export function PlatformConsoleContent({ activeTab, activeMakerspace, makerspaces, currentUser, onAuthRefresh }: Props) {
  // Deployment facts, the same on every space row: whether this is a hosted platform and which apps it omits.
  const facts = activeMakerspace ?? makerspaces[0];
  const unavailableApps = facts?.unavailable_apps ?? [];
  if (activeTab === "platform-inbox") return <PlatformInboxPage />;
  if (activeTab === "platform-access") return <PlatformAccessPage makerspaces={makerspaces} currentUser={currentUser} onAuthRefresh={onAuthRefresh} />;
  if (activeTab === "platform-security") return <PlatformSecurityPage makerspaces={makerspaces} />;
  if (activeTab === "platform-data") return <PlatformDataPage unavailableApps={unavailableApps} />;
  if (activeTab === "platform-limits") return <PlatformLimitsPage />;
  if (activeTab === "platform-analytics") return <AnalyticsPanel key="platform-analytics" scope={{ kind: "platform" }} />;
  if (activeTab === "platform") return <PlatformLimitsRedirect><PlatformSettingsPanel platformHosting={Boolean(facts?.platform_hosting)} unavailableApps={unavailableApps} /></PlatformLimitsRedirect>;
  return null;
}
