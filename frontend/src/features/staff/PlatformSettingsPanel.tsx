import { useSearchParams } from "react-router-dom";
import { SettingsLayout } from "../../components/layouts";
import { PlatformDeploymentSection } from "./PlatformDeploymentSection";
import { PlatformEmailPanel } from "./PlatformEmailPanel";
import { PlatformSocialAuthPanel } from "./PlatformSocialAuthPanel";
import { PlatformStripeConnectPanel } from "./PlatformStripeConnectPanel";

export function PlatformSettingsPanel({ platformHosting }: { platformHosting: boolean }) {
  const [search] = useSearchParams();
  const available = [{ key: "deployment", label: "Deployment", rows: <PlatformDeploymentSection /> },{ key: "email", label: "Email", rows: <PlatformEmailPanel embedded /> },
    { key: "sign-in", label: "Sign-in providers", rows: <PlatformSocialAuthPanel embedded /> },
    ...(platformHosting ? [{ key: "stripe", label: "Stripe Connect", rows: <PlatformStripeConnectPanel embedded /> }] : [])];
  const active = available.find(section => section.key === search.get("section")) ?? available.find(section => section.key === "email")!;
  return <SettingsLayout header={{ title: "Platform settings", subtitle: "Manage deployment-wide email, sign-in providers and payments." }}
    state={{ status: "ready" }} tabs={available.map(section => { const next = new URLSearchParams(search); next.set("section", section.key);
      return { key: section.key, label: section.label, href: `?${next}` }; })} activeTab={active.key}
    sections={[{ id: active.key, title: active.label, rows: active.rows }]} />;
}
