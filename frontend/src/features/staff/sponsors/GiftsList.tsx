import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { EmptyState, ListRow } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { DeskGiftForm } from "./DeskGiftForm";
import { GiftActions } from "./GiftActions";
import { GIFT_STATUS, SOURCE_LABELS, donationStaffApi, donationStaffKeys, type StaffCampaign } from "./staffDonationsApi";
import { LogoLoader } from "../../../components/LogoLoader";

/** Every gift in the space, newest first: received, waiting and cancelled, with desk recording and a CSV export. */
export function GiftsList({ makerspaceId, campaigns, canRecord, taxOn }: {
  makerspaceId: number; campaigns: StaffCampaign[]; canRecord: boolean; taxOn: boolean;
}) {
  const [status, setStatus] = useState("");
  const [campaign, setCampaign] = useState("");
  const [recording, setRecording] = useState(false);
  const filters = new URLSearchParams({ ...(status ? { status } : {}), ...(campaign ? { campaign } : {}) }).toString();
  const gifts = useQuery({ queryKey: donationStaffKeys.gifts(makerspaceId, filters),
    queryFn: () => donationStaffApi.gifts(makerspaceId, filters) });
  const exportCsv = useMutation({ mutationFn: () => donationStaffApi.exportCsv(makerspaceId, filters) });
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Status`}<select className="desk-input" value={status}
        onChange={event => setStatus(event.target.value)}><option value="">{t`All`}</option>
        {Object.entries(GIFT_STATUS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label>
      {campaigns.length ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Campaign`}<select className="desk-input"
        value={campaign} onChange={event => setCampaign(event.target.value)}><option value="">{t`All`}</option>
        {campaigns.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label> : null}
      <div className="ml-auto flex flex-wrap gap-2">
        <button type="button" className="desk-button-ghost" disabled={exportCsv.isPending}
          onClick={() => exportCsv.mutate()}>{t`Download CSV`}</button>
        {canRecord ? <button type="button" className="desk-button" onClick={() => setRecording(true)}>{t`Record a gift`}</button> : null}
      </div>
    </div>
    {exportCsv.error ? <p role="alert" className="text-sm text-danger">{financeError(exportCsv.error)}</p> : null}
    {gifts.isLoading ? <LogoLoader label={t`Loading gifts…`} size={48} className="min-h-16 py-3" /> : null}
    {gifts.error ? <p role="alert" className="text-sm text-danger">{financeError(gifts.error)}</p> : null}
    {gifts.data && !gifts.data.length ? <EmptyState message={t`No gifts yet. Share your donation page, or record one received in person.`} /> : null}
    {gifts.data?.map(gift => <ListRow key={gift.id} title={`${gift.currency.toUpperCase()} ${gift.amount} · ${gift.donor_name || t`Anonymous`}`}
      identity={{ kind: "date", date: gift.created_at }}
      meta={[SOURCE_LABELS[gift.source], gift.campaign_name, gift.is_guest ? t`Guest` : "",
        gift.recognize_publicly ? t`Named on the campaign page` : "",
        gift.wants_tax_receipt ? `${t`Tax receipt asked`}${gift.donor_pan_masked ? ` · PAN ${gift.donor_pan_masked}` : ""}` : ""]
        .filter(Boolean).join(" · ")}
      right={<GiftActions makerspaceId={makerspaceId} gift={gift} canRecord={canRecord} taxOn={taxOn} />} />)}
    {recording ? <DeskGiftForm makerspaceId={makerspaceId} campaigns={campaigns} taxOn={taxOn} onClose={() => setRecording(false)} /> : null}
  </div>;
}
