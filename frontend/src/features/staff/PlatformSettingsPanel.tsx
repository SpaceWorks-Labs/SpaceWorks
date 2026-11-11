import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { SettingsLayout } from "../../components/layouts";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { PlatformDeploymentSection } from "./PlatformDeploymentSection";
import { PlatformEmailPanel } from "./PlatformEmailPanel";
import { PlatformSocialAuthPanel } from "./PlatformSocialAuthPanel";
import { PlatformStripeConnectPanel } from "./PlatformStripeConnectPanel";
import { ChatTemplatesSection } from "./platformParity/ChatTemplatesSection";
import { MobileAppsSection } from "./platformParity/MobileAppsSection";
import { LOGIN_METHODS } from "./platformParity/providerSpecs";
import { Provider, ProvidersSection } from "./platformParity/ProvidersSection";
import { SsoSection } from "./platformParity/SsoSection";
import { sectionHref } from "./platformConsole/PlatformSectionPage";
import { ModuleDefaultsSection } from "./platformConsole/PlatformDefaultsSections";
import { SettingsSectionNav } from "./SettingsSectionNav";
import { platformSettingsGroups, platformSettingsLinks } from "./platformSettingsGroups";
import { WalletCredentialsCard } from "../walletCredentials/WalletCredentialsCard";
import { LegalPagesEditor } from "../legal/LegalPagesEditor";

type Props = { platformHosting: boolean; unavailableApps?: readonly string[] };
type Section = { key: string; label: string; description: string; rows: ReactNode };

// Sections that moved to their own platform page in 0.12.0: an old `?section=` link still lands on them.
const MOVED: Record<string, string> = {
  accounts: "/admin/platform-access?section=accounts",
  "ip-access": "/admin/platform-security?section=ip-access",
  audit: "/admin/platform-security?section=audit",
  "restore-drills": "/admin/platform-data?section=restore-drills",
  "selfhost-moves": "/admin/platform-data?section=selfhost-moves",
  requests: "/admin/platform-spaces#requests",
};

/**
 * Deployment-wide configuration (#190), grouped like a space's settings (decision 255):
 * People (sign-in), Areas (what new spaces start with), Money, Communication, Integrations
 * and Administration, with a search over every page's one-line help. Each page keeps its
 * `?section=` key, so existing links still open it.
 */
export function PlatformSettingsPanel({ platformHosting }: Props) {
  const [search] = useSearchParams();
  const moved = MOVED[search.get("section") ?? ""];
  if (moved) return <Navigate replace to={consoleSessionHref(moved, "platform")} />;
  const sections: Section[] = [
    { key: "sign-in", label: t`Sign-in providers`, description: t`Google, GitHub and other accounts people can sign in with, and which sign-in methods are offered.`,
      rows: <><PlatformSocialAuthPanel embedded />
        <section aria-label={t`Sign-in methods`} className="grid gap-3 py-4"><h3 className="title-panel">{t`Sign-in methods`}</h3><Provider spec={LOGIN_METHODS} /></section></> },
    { key: "sso", label: t`Single sign-on`, description: t`Let an organization's own identity provider sign its people in.`, rows: <SsoSection /> },
    { key: "feature-defaults", label: t`Feature defaults`, description: t`What a new space starts with and how many spaces use each feature.`, rows: <ModuleDefaultsSection /> },
    ...(platformHosting ? [{ key: "stripe", label: t`Stripe Connect`, description: t`Let hosted spaces take card payments through the platform's Stripe account.`,
      rows: <PlatformStripeConnectPanel embedded /> }] : []),
    { key: "email", label: t`Email`, description: t`The server and address the platform sends email from, used by spaces without their own.`, rows: <PlatformEmailPanel embedded /> },
    { key: "providers", label: t`Messaging providers`, description: t`SMS, WhatsApp and app push accounts spaces can send through.`, rows: <ProvidersSection /> },
    { key: "chat-templates", label: t`Chat templates`, description: t`The default wording of chat and SMS messages.`, rows: <ChatTemplatesSection /> },
    { key: "mobile-apps", label: t`Mobile apps`, description: t`The phone apps allowed to sign in, and the links that open them.`, rows: <MobileAppsSection /> },
    { key: "wallet", label: t`Wallet passes`, description: t`The wallet-pass credentials every space uses unless it sets its own.`, rows: <WalletCredentialsCard scope={{ kind: "platform" }} /> },
    // Parity A13: the operator's privacy and terms text, shown on every space without its own.
    { key: "legal", label: t`Privacy and terms`, description: t`The privacy policy and terms of use every space shows unless it writes its own.`, rows: <LegalPagesEditor scope={{ kind: "platform" }} /> },
    { key: "deployment", label: t`Version & deployment`, description: t`Which version runs here and how this server is set up.`, rows: <PlatformDeploymentSection /> },
  ];
  const active = sections.find(section => section.key === search.get("section")) ?? sections[0];
  const titles = Object.fromEntries(sections.map(section => [section.key, section.label]));
  const links = platformSettingsLinks();
  const help = { ...Object.fromEntries(sections.map(section => [section.key, section.description])),
    ...Object.fromEntries(Object.entries(links).map(([key, link]) => [key, link.help])) };
  return <SettingsLayout header={{ title: t`Platform settings`, subtitle: t`Sign-in, email and messaging, apps, payments and deployment for every space on this server.` }}
    state={{ status: "ready" }}
    nav={<SettingsSectionNav groups={platformSettingsGroups()} titles={titles} links={links} help={help} active={active.key}
      href={key => sectionHref(search, key)} canLeave={() => true} />}
    sections={[{ id: active.key, title: active.label, description: active.description, rows: active.rows }]} />;
}
