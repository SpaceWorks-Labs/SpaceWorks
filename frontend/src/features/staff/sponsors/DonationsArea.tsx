import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { EmptyState, ErrorBlock, ProgressBar, Skeleton, Tabs } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import { formatMoney } from "../../../lib/money";
import { useRoutedSubTab } from "../useRoutedSubTab";
import { CampaignsEditor } from "./CampaignsEditor";
import { DonationSettingsForm } from "./DonationSettingsForm";
import { DonorsList } from "./DonorsList";
import { GiftsList } from "./GiftsList";
import { PledgesList } from "./PledgesList";
import { SponsorsSection } from "./SponsorsSection";
import { donationStaffApi, donationStaffKeys, type StaffCampaign } from "./staffDonationsApi";

type Space = { id: number; name?: string; enabled_modules?: string[]; enabled_features?: string[] };

function CampaignProgress({ campaigns }: { campaigns: StaffCampaign[] }) {
  const open = campaigns.filter(row => row.is_active);
  if (!open.length) return <EmptyState message={t`No open campaigns. Gifts go to the space in general.`} />;
  return <ul className="grid gap-3">{open.map(row => {
    const raised = Number(row.raised_amount ?? 0);
    const goal = Number(row.goal_amount ?? 0);
    return <li key={row.id} className="grid gap-1 rounded-md border border-line p-3">
      <span className="font-semibold text-ink">{row.name}</span>
      {goal > 0 ? <ProgressBar value={Math.min(raised / goal, 1)} label={t`${row.name}: ${Math.round((raised / goal) * 100)} percent of the goal raised`} /> : null}
      <span className="text-sm text-muted tabular-nums">{goal > 0
        ? t`${formatMoney(row.raised_amount ?? "0", row.currency)} of ${formatMoney(row.goal_amount ?? "0", row.currency)}`
        : t`${formatMoney(row.raised_amount ?? "0", row.currency)} raised`}</span>
    </li>;
  })}</ul>;
}

/**
 * Decision 242(m): the one Donations area. The Space Manager runs it, and may hand it to the
 * Fundraising role; finance staff read it. Gifts, campaigns, pledges, donors, sponsors and the
 * non-profit profile. Money here never shows in an area manager's Finance views.
 */
export function DonationsArea({ makerspace, actions, isSuperadmin = false }: {
  makerspace: Space; actions: readonly string[]; isSuperadmin?: boolean;
}) {
  const has = (action: string) => isSuperadmin || actions.includes(action);
  const canRecord = has("manage_donations") || has("record_payment");
  const canEditProfile = isSuperadmin || has("manage_makerspace");
  const taxOn = capabilityOn(makerspace, "finance.tax_exempt_receipts");
  const donationsOn = capabilityOn(makerspace, "finance.donations");
  const campaigns = useQuery({ queryKey: donationStaffKeys.campaigns(makerspace.id),
    queryFn: () => donationStaffApi.campaigns(makerspace.id), enabled: donationsOn });
  const sections = [
    ...(donationsOn ? [{ key: "overview", label: t`Overview` }, { key: "gifts", label: t`Gifts` },
      { key: "campaigns", label: t`Campaigns` }] : []),
    ...(donationsOn && capabilityOn(makerspace, "finance.recurring_donations") ? [{ key: "pledges", label: t`Pledges` }] : []),
    ...(donationsOn ? [{ key: "donors", label: t`Donors` }] : []),
    ...(capabilityOn(makerspace, "finance.sponsors") ? [{ key: "sponsors", label: t`Sponsors` }] : []),
    ...(donationsOn ? [{ key: "profile", label: t`Non-profit and receipts` }] : []),
  ];
  const route = useRoutedSubTab();
  const active = sections.some(section => section.key === route.segment) ? route.segment : sections[0]?.key;
  const rows = campaigns.data ?? [];
  const needsCampaigns = active === "overview" || active === "gifts" || active === "campaigns";
  return <section className="grid min-w-0 gap-4" aria-labelledby="donations-heading">
    <header className="grid gap-1">
      <h2 id="donations-heading" className="title-page">{t`Donations`}</h2>
      <p className="text-sm text-muted">{t`Campaigns, gifts, regular givers, sponsors and receipts. Nothing here moves money by itself.`}</p>
    </header>
    {!sections.length ? <p className="rounded-lg border border-line bg-panel p-4 text-sm text-muted">
      {t`Donations are switched off for this space. A Space Manager turns them on under Features.`}</p> : null}
    {sections.length ? <Tabs tabs={sections} activeKey={active ?? ""} label={t`Donation sections`} onChange={route.select} /> : null}
    {needsCampaigns && campaigns.error ? <ErrorBlock error={campaigns.error} resource={t`campaigns`} onRetry={() => void campaigns.refetch()} /> : null}
    {needsCampaigns && campaigns.isLoading ? <Skeleton className="h-16 w-full" /> : null}
    {active === "overview" && campaigns.isSuccess ? <CampaignProgress campaigns={rows} /> : null}
    {active === "gifts" && !campaigns.error ? <GiftsList makerspaceId={makerspace.id} campaigns={rows} canRecord={canRecord} taxOn={taxOn} /> : null}
    {active === "campaigns" && campaigns.isSuccess ? <CampaignsEditor makerspaceId={makerspace.id} campaigns={rows} canRecord={canRecord} /> : null}
    {active === "pledges" ? <PledgesList makerspaceId={makerspace.id} canRecord={canRecord} /> : null}
    {active === "donors" ? <DonorsList makerspaceId={makerspace.id} /> : null}
    {active === "sponsors" ? <SponsorsSection makerspaceId={makerspace.id} canRecordPayment={canRecord} /> : null}
    {active === "profile" ? <DonationSettingsForm makerspaceId={makerspace.id} taxOn={taxOn} canEdit={canEditProfile} /> : null}
  </section>;
}
