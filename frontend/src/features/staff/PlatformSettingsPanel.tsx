import { t } from "@lingui/core/macro";
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
  const available = [{ key: "deployment", label: t`Deployment`, rows: <PlatformDeploymentSection /> },{ key: "email", label: t`Email`, rows: <PlatformEmailPanel embedded /> },
    { key: "sign-in", label: t`Sign-in providers`, rows: <><PlatformSocialAuthPanel embedded />
      <section aria-label={t`Sign-in methods`} className="grid gap-3 py-4"><h3 className="title-panel">{t`Sign-in methods`}</h3><Provider spec={LOGIN_METHODS} /></section></> },
    ...(platformHosting ? [{ key: "stripe", label: t`Stripe Connect`, rows: <PlatformStripeConnectPanel embedded /> }] : []),
    { key: "providers", label: t`Messaging & apps`, rows: <ProvidersSection /> },
    { key: "mobile-apps", label: t`Mobile apps`, rows: <MobileAppsSection /> },
    { key: "requests", label: t`Requests`, rows: <RequestsSection /> },
    { key: "accounts", label: t`Accounts`, rows: <AccountsSection /> },
    { key: "ip-access", label: t`IP access`, rows: <IpAccessSection /> },
    { key: "sso", label: t`Single sign-on`, rows: <SsoSection /> },
    { key: "chat-templates", label: t`Chat templates`, rows: <ChatTemplatesSection /> },
    { key: "restore-drills", label: t`Restore drills`, rows: <RestoreDrillsSection /> },
    // A deployment that does not ship tenant migration has no self-host move routes at all.
    ...(unavailableApps.includes("tenant_migration") ? [] : [{ key: "selfhost-moves", label: t`Self-host moves`, rows: <SelfhostMovesSection /> }])];
  const active = available.find(section => section.key === search.get("section")) ?? available.find(section => section.key === "email")!;
  return <SettingsLayout header={{ title: t`Platform settings`, subtitle: t`Deployment-wide settings, security and recovery.` }}
    state={{ status: "ready" }} tabs={available.map(section => { const next = new URLSearchParams(search); next.set("section", section.key);
      return { key: section.key, label: section.label, href: `?${next}` }; })} activeTab={active.key}
    sections={[{ id: active.key, title: active.label, rows: active.rows }]} />;
}
