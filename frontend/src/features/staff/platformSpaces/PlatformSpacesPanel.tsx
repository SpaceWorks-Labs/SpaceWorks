import { t } from "@lingui/core/macro";
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
    { id: "health", title: t`Health`, description: t`Every space at a glance. Use Manage on a card to suspend, transfer, schedule or archive it.`, rows: <HealthSection managedPlans={Boolean(managed)} /> },
    { id: "onboarding", title: t`Onboarding`, description: t`Hosting requests from people who want a space on this platform.`, rows: <OnboardingSection /> },
    { id: "announcements", title: t`Announcements`, description: t`Banners shown to the staff (and optionally the members) of every or selected spaces.`, rows: <AnnouncementsSection /> },
    ...(managed ? [
      { id: "plans", title: t`Plans`, description: t`The limits and price each managed space runs under.`, rows: <PlansSection /> },
      { id: "billing", title: t`Billing`, description: managed.online_billing ? t`Invoices can be paid online by Space Managers.` : t`Invoices are settled offline; record each payment here.`, rows: <InvoicesSection /> },
      { id: "billing-settings", title: t`Billing settings`, rows: <BillingSettingsSection /> },
    ] : []),
  ];
  return <SettingsLayout header={{ title: t`Spaces`, eyebrow: t`Platform`, subtitle: t`Health, lifecycle, onboarding and announcements for every space.` }}
    state={{ status: "ready" }} sections={sections} />;
}
