import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Tabs } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import { CampaignsEditor } from "./CampaignsEditor";
import { DonationSettingsForm } from "./DonationSettingsForm";
import { GiftsList } from "./GiftsList";
import { PledgesList } from "./PledgesList";
import { donationStaffApi, donationStaffKeys } from "./staffDonationsApi";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** Donations (`finance.donations`): gifts, campaigns, pledges and the page settings. Finance staff only. */
export function DonationsSection({ makerspace, canRecordPayment }: { makerspace: Space; canRecordPayment: boolean }) {
  const taxOn = capabilityOn(makerspace, "finance.tax_exempt_receipts");
  const campaigns = useQuery({ queryKey: donationStaffKeys.campaigns(makerspace.id),
    queryFn: () => donationStaffApi.campaigns(makerspace.id) });
  const tabs = [{ key: "gifts", label: t`Gifts` }, { key: "campaigns", label: t`Campaigns` },
    ...(capabilityOn(makerspace, "finance.recurring_donations") ? [{ key: "pledges", label: t`Pledges` }] : []),
    { key: "settings", label: t`Settings` }];
  const [chosen, setChosen] = useState("gifts");
  const active = tabs.some(tab => tab.key === chosen) ? chosen : "gifts";
  const rows = campaigns.data ?? [];
  return <section className="grid gap-4" aria-label={t`Donations`}>
    <Tabs tabs={tabs} activeKey={active} label={t`Donation sections`} onChange={setChosen} />
    {active === "gifts" ? <GiftsList makerspaceId={makerspace.id} campaigns={rows} canRecord={canRecordPayment} taxOn={taxOn} /> : null}
    {active === "campaigns" ? <CampaignsEditor makerspaceId={makerspace.id} campaigns={rows} canRecord={canRecordPayment} /> : null}
    {active === "pledges" ? <PledgesList makerspaceId={makerspace.id} canRecord={canRecordPayment} /> : null}
    {active === "settings" ? <DonationSettingsForm makerspaceId={makerspace.id} taxOn={taxOn} /> : null}
  </section>;
}
