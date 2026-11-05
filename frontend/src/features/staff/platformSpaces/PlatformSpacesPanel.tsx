import { SettingsLayout, type SettingsLayoutSection } from "../../../components/layouts";
import { AnnouncementsSection } from "./AnnouncementsSection";
import { BillingSettingsSection } from "./BillingSettingsSection";
import { HealthSection } from "./HealthSection";
import { InvoicesSection } from "./InvoicesSection";
import { OnboardingSection } from "./OnboardingSection";
import { useManagedPlans } from "./plansApi";
import { PlansSection } from "./PlansSection";

/**
 * The superadmin's Spaces page (#185, #187A, #190): every space's health and lifecycle controls,
 * the onboarding queue, platform announcements and, only where the managed limiter is on, plans
 * and billing. /control/ keeps the same controls as a fallback.
 */
export function PlatformSpacesPanel() {
  const managed = useManagedPlans();
  const sections: SettingsLayoutSection[] = [
    { id: "health", title: "Health", description: "Every space at a glance. Use Manage on a card to suspend, transfer, schedule or archive it.", rows: <HealthSection managedPlans={Boolean(managed)} /> },
    { id: "onboarding", title: "Onboarding", description: "Hosting requests from people who want a space on this platform.", rows: <OnboardingSection /> },
    { id: "announcements", title: "Announcements", description: "Banners shown to the staff (and optionally the members) of every or selected spaces.", rows: <AnnouncementsSection /> },
    ...(managed ? [
      { id: "plans", title: "Plans", description: "The limits and price each managed space runs under.", rows: <PlansSection /> },
      { id: "billing", title: "Billing", description: managed.online_billing ? "Invoices can be paid online by Space Managers." : "Invoices are settled offline; record each payment here.", rows: <InvoicesSection /> },
      { id: "billing-settings", title: "Billing settings", rows: <BillingSettingsSection /> },
    ] : []),
  ];
  return <SettingsLayout header={{ title: "Spaces", eyebrow: "Platform", subtitle: "Health, lifecycle, onboarding and announcements for every space." }}
    state={{ status: "ready" }} sections={sections} />;
}
