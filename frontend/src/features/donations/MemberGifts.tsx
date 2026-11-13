import { t } from "@lingui/core/macro";
import { formatMoney } from "../../lib/money";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ListRow, StatusPill } from "../../components/ui";
import { memberRequestBlob } from "../../lib/api";
import { useTenantPath } from "../../lib/tenant";
import { useSpaceSwitches } from "../members/calendarFeeds/MemberCalendarLinks";
import { donationKeys, donationsApi, giveError, type GiftStatus, type PledgeAction } from "./donationsApi";
import { PledgeCard } from "./PledgeCard";

const STATUS = { paid: ["Received", "success"], pending: ["Waiting for payment", "warn"], cancelled: ["Cancelled", "neutral"] } as const;

function GiftRow({ makerspaceId, gift }: { makerspaceId: number; gift: GiftStatus }) {
  const pdf = useMutation({ mutationFn: async () => {
    const blob = await memberRequestBlob(donationsApi.memberReceiptPath(makerspaceId, gift.id));
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `${gift.tax_receipt_number || `donation-${gift.id}`}.pdf`; link.click(); URL.revokeObjectURL(url);
  } });
  const [label, tone] = STATUS[gift.status];
  return <ListRow title={formatMoney(gift.amount, gift.currency)} identity={{ kind: "date", date: gift.created_at }}
    meta={[gift.campaign, gift.receipt_number ? `Receipt ${gift.receipt_number}` : "",
      gift.status === "pending" ? "Pay it from your payments" : ""].filter(Boolean).join(" · ")}
    right={<div className="grid justify-items-end gap-2"><StatusPill label={label} tone={tone} />
      {gift.tax_receipt_number ? <button type="button" className="desk-button-ghost" disabled={pdf.isPending}
        onClick={() => pdf.mutate()}>{t`Tax receipt`}</button> : null}
      {pdf.error ? <p role="alert" className="text-xs text-danger">{giveError(pdf.error)}</p> : null}</div>} />;
}

/** A member's own gifts and pledges to this space, when the space takes donations. */
export function MemberGifts({ makerspaceId, makerspaceSlug }: { makerspaceId: number; makerspaceSlug: string }) {
  const on = useSpaceSwitches(makerspaceSlug);
  const path = useTenantPath(makerspaceSlug);
  const client = useQueryClient();
  const giving = on("finance.donations");
  const pledgesOn = giving && on("finance.recurring_donations");
  const gifts = useQuery({ queryKey: donationKeys.memberGifts(makerspaceId), queryFn: () => donationsApi.memberGifts(makerspaceId),
    enabled: giving, retry: false });
  const pledges = useQuery({ queryKey: donationKeys.memberPledges(makerspaceId),
    queryFn: () => donationsApi.memberPledges(makerspaceId), enabled: pledgesOn, retry: false });
  const change = useMutation({
    mutationFn: ({ id, body }: { id: number; body: PledgeAction }) => donationsApi.changeMemberPledge(makerspaceId, id, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: donationKeys.memberPledges(makerspaceId) }),
  });
  if (!giving) return null;
  return <section className="grid gap-3" aria-labelledby="member-gifts-heading">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 id="member-gifts-heading" className="title-panel">{t`My gifts`}</h2>
      {/* #184: with donation charges off the space takes no gifts; past gifts stay listed as history. */}
      {on("charges.enabled") && on("charges.donations") ? <a className="desk-button" href={path("donate")}>{t`Give again`}</a> : null}
    </div>
    {gifts.data?.length ? gifts.data.map(gift => <GiftRow key={gift.id} makerspaceId={makerspaceId} gift={gift} />)
      : <p className="text-sm text-muted">{t`You haven't given to this space yet.`}</p>}
    {pledges.data?.filter(row => row.status !== "cancelled").map(pledge => <PledgeCard key={`${pledge.id}-${pledge.amount}-${pledge.interval}`}
      pledge={pledge} onAction={body => change.mutate({ id: pledge.id, body })} pending={change.isPending} error={change.error} />)}
  </section>;
}
