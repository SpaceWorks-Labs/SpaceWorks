import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, ListRow, StatusPill } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { DeskGiftForm } from "./DeskGiftForm";
import {
  GIFT_STATUS, SOURCE_LABELS, donationStaffApi, donationStaffKeys, type StaffCampaign, type StaffDonation,
} from "./staffDonationsApi";

function GiftActions({ makerspaceId, gift, canRecord, taxOn }: {
  makerspaceId: number; gift: StaffDonation; canRecord: boolean; taxOn: boolean;
}) {
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: ["staff-donations", makerspaceId] });
  const cancel = useMutation({ mutationFn: (reason: string) => donationStaffApi.cancel(makerspaceId, gift.id, reason), onSuccess: refresh });
  const back = useMutation({ mutationFn: (reason: string) => donationStaffApi.openReturn(makerspaceId, gift.id, reason), onSuccess: refresh });
  const pdf = useMutation({ mutationFn: () => donationStaffApi.taxReceipt(makerspaceId, gift) });
  const [mode, setMode] = useState<"cancel" | "return" | null>(null);
  const [reason, setReason] = useState("");
  const error = cancel.error || back.error || pdf.error;
  return <div className="grid justify-items-end gap-2">
    <StatusPill label={GIFT_STATUS[gift.status].label} tone={GIFT_STATUS[gift.status].tone} />
    <div className="flex flex-wrap justify-end gap-2">
      {taxOn && gift.tax_receipt_number ? <button type="button" className="desk-button-ghost" disabled={pdf.isPending}
        onClick={() => pdf.mutate()}>80G receipt</button> : null}
      {canRecord && gift.status === "pending" ? <button type="button" className="desk-button-ghost"
        aria-expanded={mode === "cancel"} onClick={() => setMode(mode === "cancel" ? null : "cancel")}>Cancel</button> : null}
      {canRecord && gift.status === "paid" ? <button type="button" className="desk-button-ghost"
        aria-expanded={mode === "return"} onClick={() => setMode(mode === "return" ? null : "return")}>Return…</button> : null}
    </div>
    {mode ? <form className="flex flex-wrap items-end justify-end gap-2" aria-label={mode === "cancel" ? "Cancel this gift" : "Return this gift"}
      onSubmit={event => { event.preventDefault(); (mode === "cancel" ? cancel : back).mutate(reason, { onSuccess: () => setMode(null) }); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{mode === "cancel" ? "Why cancel? (optional)" : "Why return it?"}
        <input className="desk-input" maxLength={500} required={mode === "return"} value={reason}
          onChange={event => setReason(event.target.value)} /></label>
      <button type="submit" className="desk-button" disabled={cancel.isPending || back.isPending}>
        {mode === "cancel" ? "Cancel gift" : "Open refund case"}</button>
    </form> : null}
    {back.isSuccess ? <p role="status" className="text-xs text-muted">Refund case opened. Decide it under Refunds.</p> : null}
    {error ? <p role="alert" className="text-xs text-danger">{financeError(error)}</p> : null}
  </div>;
}

/** Every gift in the space, newest first: received, waiting and cancelled, with desk recording. */
export function GiftsList({ makerspaceId, campaigns, canRecord, taxOn }: {
  makerspaceId: number; campaigns: StaffCampaign[]; canRecord: boolean; taxOn: boolean;
}) {
  const [status, setStatus] = useState("");
  const [campaign, setCampaign] = useState("");
  const [recording, setRecording] = useState(false);
  const filters = new URLSearchParams({ ...(status ? { status } : {}), ...(campaign ? { campaign } : {}) }).toString();
  const gifts = useQuery({ queryKey: donationStaffKeys.gifts(makerspaceId, filters),
    queryFn: () => donationStaffApi.gifts(makerspaceId, filters) });
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-sm font-semibold text-ink">Status<select className="desk-input" value={status}
        onChange={event => setStatus(event.target.value)}><option value="">All</option>
        {Object.entries(GIFT_STATUS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label>
      {campaigns.length ? <label className="grid gap-1 text-sm font-semibold text-ink">Campaign<select className="desk-input"
        value={campaign} onChange={event => setCampaign(event.target.value)}><option value="">All</option>
        {campaigns.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label> : null}
      {canRecord ? <button type="button" className="desk-button ml-auto" onClick={() => setRecording(true)}>Record a gift</button> : null}
    </div>
    {gifts.isLoading ? <p role="status" className="text-sm text-muted">Loading gifts…</p> : null}
    {gifts.error ? <p role="alert" className="text-sm text-danger">{financeError(gifts.error)}</p> : null}
    {gifts.data && !gifts.data.length ? <EmptyState message="No gifts yet. Share your donation page, or record one received in person." /> : null}
    {gifts.data?.map(gift => <ListRow key={gift.id} title={`${gift.currency.toUpperCase()} ${gift.amount} · ${gift.donor_name || "Anonymous"}`}
      identity={{ kind: "date", date: gift.created_at }}
      meta={[SOURCE_LABELS[gift.source], gift.campaign_name, gift.is_guest ? "Guest" : "", gift.wants_tax_receipt
        ? `80G${gift.donor_pan_masked ? ` · PAN ${gift.donor_pan_masked}` : ""}` : ""].filter(Boolean).join(" · ")}
      right={<GiftActions makerspaceId={makerspaceId} gift={gift} canRecord={canRecord} taxOn={taxOn} />} />)}
    {recording ? <DeskGiftForm makerspaceId={makerspaceId} campaigns={campaigns} taxOn={taxOn} onClose={() => setRecording(false)} /> : null}
  </div>;
}
