import { useSearchParams } from "react-router-dom";
import { SettingsLayout } from "../../components/layouts";
import { PlatformDeploymentSection } from "./PlatformDeploymentSection";
import { PlatformEmailPanel } from "./PlatformEmailPanel";
import { PlatformSocialAuthPanel } from "./PlatformSocialAuthPanel";
import { PlatformStripeConnectPanel } from "./PlatformStripeConnectPanel";
import { AccountsSection } from "./platformParity/AccountsSection";
import { ChatTemplatesSection } from "./platformParity/ChatTemplatesSection";
import { IpAccessSection } from "./platformParity/IpAccessSection";
import { MobileAppsSection } from "./platformParity/MobileAppsSection";
import { LOGIN_METHODS } from "./platformParity/providerSpecs";
import { Provider, ProvidersSection } from "./platformParity/ProvidersSection";
import { RequestsSection } from "./platformParity/RequestsSection";
import { RestoreDrillsSection } from "./platformParity/RestoreDrillsSection";
import { SelfhostMovesSection } from "./platformParity/SelfhostMovesSection";
import { SsoSection } from "./platformParity/SsoSection";

type Props = { platformHosting: boolean; unavailableApps?: readonly string[] };

/** Deployment-wide settings, plus the security and recovery controls that used to live only in /control/ (#190). */
export function PlatformSettingsPanel({ platformHosting, unavailableApps = [] }: Props) {
  const [search] = useSearchParams();
  const available = [{ key: "deployment", label: "Deployment", rows: <PlatformDeploymentSection /> },{ key: "email", label: "Email", rows: <PlatformEmailPanel embedded /> },
    { key: "sign-in", label: "Sign-in providers", rows: <><PlatformSocialAuthPanel embedded />
      <section aria-label="Sign-in methods" className="grid gap-3 py-4"><h3 className="title-panel">Sign-in methods</h3><Provider spec={LOGIN_METHODS} /></section></> },
    ...(platformHosting ? [{ key: "stripe", label: "Stripe Connect", rows: <PlatformStripeConnectPanel embedded /> }] : []),
    { key: "providers", label: "Messaging & apps", rows: <ProvidersSection /> },
    { key: "mobile-apps", label: "Mobile apps", rows: <MobileAppsSection /> },
    { key: "requests", label: "Requests", rows: <RequestsSection /> },
    { key: "accounts", label: "Accounts", rows: <AccountsSection /> },
    { key: "ip-access", label: "IP access", rows: <IpAccessSection /> },
    { key: "sso", label: "Single sign-on", rows: <SsoSection /> },
    { key: "chat-templates", label: "Chat templates", rows: <ChatTemplatesSection /> },
    { key: "restore-drills", label: "Restore drills", rows: <RestoreDrillsSection /> },
    // A deployment that does not ship tenant migration has no self-host move routes at all.
    ...(unavailableApps.includes("tenant_migration") ? [] : [{ key: "selfhost-moves", label: "Self-host moves", rows: <SelfhostMovesSection /> }])];
  const active = available.find(section => section.key === search.get("section")) ?? available.find(section => section.key === "email")!;
  return <SettingsLayout header={{ title: "Platform settings", subtitle: "Deployment-wide settings, security and recovery." }}
    state={{ status: "ready" }} tabs={available.map(section => { const next = new URLSearchParams(search); next.set("section", section.key);
      return { key: section.key, label: section.label, href: `?${next}` }; })} activeTab={active.key}
    sections={[{ id: active.key, title: active.label, rows: active.rows }]} />;
}
