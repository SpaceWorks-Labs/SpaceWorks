import { t } from "@lingui/core/macro";
import { Navigate } from "react-router-dom";
import { SettingsLayout, type SettingsLayoutSection } from "../../../components/layouts";
import { AnnouncementsSection } from "./AnnouncementsSection";
import { BillingSettingsSection } from "./BillingSettingsSection";
import { HealthSection } from "./HealthSection";
import { InvoicesSection } from "./InvoicesSection";
import { OnboardingSection } from "./OnboardingSection";
import { OrganizationReviewQueue } from "../../organizations/review/OrganizationReviewQueue";
import { useManagedPlans } from "./plansApi";
import { RequestsSection } from "../platformParity/RequestsSection";
import { useCreateSpace } from "../platformConsole/useCreateSpace";
import { PlansSection } from "./PlansSection";
import { spaceLimitsHref } from "./PlatformLimitsPage";

/**
 * The superadmin's Spaces page (#185, #187A, #190): every space's health and lifecycle controls,
 * the onboarding queue, Space Managers' requests, platform announcements and, only where the managed limiter is on, plans
 * and billing. /control/ keeps the same controls as a fallback.
 */
export function PlatformSpacesPanel() {
  const managed = useManagedPlans();
  const create = useCreateSpace();
  const sections: SettingsLayoutSection[] = [
    { id: "health", title: t`Health`, description: t`Every space at a glance. Use Manage on a card to suspend, transfer, schedule or archive it.`, rows: <HealthSection managedPlans={Boolean(managed)} /> },
    { id: "onboarding", title: t`Onboarding`, description: t`Hosting requests from people who want a space on this platform.`, rows: <OnboardingSection /> },
    { id: "organization-reviews", title: t`Organization reviews`, description: t`New organizations waiting for approval, and the standing of every other one.`, rows: <OrganizationReviewQueue /> },
    { id: "requests", title: t`Requests`, description: t`Archive requests, web-address requests and API-key requests from Space Managers.`, rows: <RequestsSection /> },
    { id: "announcements", title: t`Announcements`, description: t`Banners shown to the staff (and optionally the members) of every or selected spaces.`, rows: <AnnouncementsSection /> },
    ...(managed ? [
      { id: "plans", title: t`Plans`, description: t`The limits and price each hosted space runs under.`, rows: <PlansSection /> },
      { id: "billing", title: t`Billing`, description: managed.online_billing ? t`Invoices can be paid online by Space Managers.` : t`Invoices are settled offline; record each payment here.`, rows: <InvoicesSection /> },
      { id: "billing-settings", title: t`Billing settings`, rows: <BillingSettingsSection /> },
    ] : []),
  ];
  // A limit-reached notice links `?space=<id>&panel=limits`: open that space's limits page (read once, no router hook needed).
  const search = new URLSearchParams(window.location.search);
  const deepLink = Number(search.get("space"));
  if (search.get("panel") === "limits" && Number.isInteger(deepLink) && deepLink > 0) return <Navigate replace to={spaceLimitsHref(deepLink)} />;
  return <>
    <SettingsLayout header={{ title: t`Spaces`, eyebrow: t`Platform`, subtitle: t`Health, lifecycle, onboarding, requests and announcements for every space.`,
      primary: { label: t`Create space`, onClick: create.start } }}
      state={{ status: "ready" }} sections={sections} />
    {create.modal}
  </>;
}
