import { LogoLoader } from "../../../components/LogoLoader";
import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useState } from "react";
import { ConfirmDialog, EmptyState, ListRow, StatusPill } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { donationStaffApi, donationStaffKeys, type StaffPledge } from "./staffDonationsApi";

const PERIOD = { monthly: "monthly", quarterly: "quarterly", yearly: "yearly" } as const;
const TONE = { active: "success", paused: "warn", cancelled: "neutral" } as const;

function PledgeActions({ makerspaceId, pledge }: { makerspaceId: number; pledge: StaffPledge }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const change = useMutation({
    mutationFn: (action: "pause" | "resume" | "cancel") => donationStaffApi.changePledge(makerspaceId, pledge.id, action),
    onSuccess: () => void client.invalidateQueries({ queryKey: donationStaffKeys.pledges(makerspaceId) }),
  });
  if (pledge.status === "cancelled") return null;
  return <div className="grid justify-items-end gap-1"><div className="flex gap-2">
    <button type="button" className="desk-button-ghost" disabled={change.isPending}
      onClick={() => change.mutate(pledge.status === "active" ? "pause" : "resume")}>{pledge.status === "active" ? t`Pause` : t`Resume`}</button>
    <button type="button" className="desk-button-ghost" disabled={change.isPending}
      onClick={() => setConfirming(true)}>{t`Cancel`}</button>
  </div>{change.error ? <p role="alert" className="text-xs text-danger">{financeError(change.error)}</p> : null}
    <ConfirmDialog open={confirming} tone="danger" title={t`Cancel this pledge?`} confirmLabel={t`Cancel pledge`} cancelLabel={t`Keep pledge`}
      message={t`Cancel this pledge? Gifts already raised stay as they are.`}
      onCancel={() => setConfirming(false)} onConfirm={() => { setConfirming(false); change.mutate("cancel"); }} /></div>;
}

/** Recurring pledges: each period raises one charge the giver pays. Nothing is taken automatically. */
export function PledgesList({ makerspaceId, canRecord }: { makerspaceId: number; canRecord: boolean }) {
  const pledges = useQuery({ queryKey: donationStaffKeys.pledges(makerspaceId), queryFn: () => donationStaffApi.pledges(makerspaceId) });
  if (pledges.error) return <p role="alert" className="text-sm text-danger">{financeError(pledges.error)}</p>;
  if (pledges.isLoading) return <LogoLoader label={t`Loading pledges…`} size={48} className="min-h-16 py-3" />;
  if (!pledges.data?.length) return <EmptyState message={t`No pledges yet.`} />;
  return <div className="grid gap-3">{pledges.data.map(pledge => <ListRow key={pledge.id}
    title={`${pledge.currency.toUpperCase()} ${pledge.amount} ${PERIOD[pledge.interval]} · ${pledge.donor_name || "Guest"}`}
    identity={{ kind: "date", date: pledge.next_due_on }}
    meta={[pledge.campaign_name, pledge.status === "active" ? `Next on ${new Date(pledge.next_due_on).toLocaleDateString(formatLocale())}` : "",
      pledge.wants_tax_receipt ? "80G" : ""].filter(Boolean).join(" · ")}
    right={<div className="grid justify-items-end gap-2"><StatusPill label={pledge.status[0].toUpperCase() + pledge.status.slice(1)}
      tone={TONE[pledge.status]} />{canRecord ? <PledgeActions makerspaceId={makerspaceId} pledge={pledge} /> : null}</div>} />)}</div>;
}
