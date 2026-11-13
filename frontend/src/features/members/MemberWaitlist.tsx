import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, ErrorText, ListRow, StatusPill } from "../../components/ui";
import { submitPublicRequest } from "../inventory/api";
import { formatWhen, waitlistApi, waitlistKeys, type WaitlistEntry } from "../inventory/waitlistApi";
import { BoxArt } from "../../components/BoxSpinner";

/** My waitlist places: position while waiting, the hold deadline once offered, and Leave. */
export function MemberWaitlist({ makerspaceId, makerspaceSlug }: { makerspaceId: number; makerspaceSlug: string }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: waitlistKeys.member(makerspaceId), queryFn: () => waitlistApi.mine(makerspaceId), retry: false });
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: waitlistKeys.member(makerspaceId) }),
    client.invalidateQueries({ queryKey: ["member", makerspaceSlug, "activity"] }),
  ]);
  const [leaving, setLeaving] = useState<WaitlistEntry | null>(null);
  const leave = useMutation({ mutationFn: (entry: WaitlistEntry) => waitlistApi.leave(makerspaceId, entry.id),
    onSuccess: () => { setLeaving(null); return refresh(); } });
  const rows = (query.data ?? []).filter(entry => entry.status !== "claimed");
  if (query.isLoading || (!rows.length && !query.error)) return null;
  return <section aria-label={t`Waitlist`} className="grid gap-3">
    <h2 className="title-panel">{t`Waitlist`}</h2>
    {query.error ? <ErrorText message={t`Couldn't load your waitlist places. Try again later.`} /> : rows.map(entry => <ListRow key={entry.id}
      title={`${entry.product_name} ×${entry.quantity}`}
      identity={{ kind: "icon", icon: entry.status === "offered" ? "CheckCircle" : "Clock", tone: entry.status === "offered" ? "success" : "info" }}
      meta={entry.status === "offered" && entry.offer_expires_at ? t`Held for you until ${formatWhen(entry.offer_expires_at)}`
        : entry.position ? t`Number ${entry.position} in line` : t`Waiting`}
      right={<div className="grid justify-items-start gap-2">
        <StatusPill label={entry.status === "offered" ? t`Ready for you` : t`Waiting`} tone={entry.status === "offered" ? "success" : "info"} />
        {entry.status === "offered" ? <ClaimOffer entry={entry} makerspaceSlug={makerspaceSlug} onDone={refresh} /> : null}
        <button type="button" className="desk-button-ghost" disabled={leave.isPending} onClick={() => setLeaving(entry)}>
          {leave.isPending && leave.variables?.id === entry.id ? t`Leaving…` : t`Leave`}</button>
      </div>} />)}
    {leave.error ? <ErrorText message={leave.error.message} /> : null}
    <ConfirmDialog open={Boolean(leaving)} title={leaving?.product_name ? t`Leave the waitlist for ${leaving.product_name}?` : t`Leave the waitlist for this item?`}
      message={leaving?.status === "offered" ? t`The items held for you go to the next person in line.` : t`You lose your place in line.`}
      confirmLabel={t`Leave waitlist`} cancelLabel={t`Stay in line`} tone="danger" pending={leave.isPending}
      onConfirm={() => { if (leaving) leave.mutate(leaving); }} onCancel={() => setLeaving(null)} />
  </section>;
}

/** Turns a held offer into a borrow request; the server matches it to the offer through `waitlist_entry_id`. */
function ClaimOffer({ entry, makerspaceSlug, onDone }: { entry: WaitlistEntry; makerspaceSlug: string; onDone: () => unknown }) {
  const [open, setOpen] = useState(false);
  const [purpose, setPurpose] = useState("");
  const claim = useMutation({
    mutationFn: () => submitPublicRequest(makerspaceSlug, { requested_for: purpose.trim(),
      items: [{ product_id: entry.product, quantity: entry.quantity }], waitlist_entry_id: entry.id }),
    onSuccess: () => { void onDone(); },
  });
  if (claim.isSuccess) return <p role="status" className="text-sm text-muted">{t`Request sent. Staff will review it.`}</p>;
  if (!open) return <button type="button" className="desk-button-brand" onClick={() => setOpen(true)}>{t`Request it`}</button>;
  return <form className="grid gap-2" onSubmit={event => { event.preventDefault(); if (purpose.trim()) claim.mutate(); }}>
    <label className="block text-sm font-semibold text-ink">{t`What do you need it for?`}<textarea className="desk-input mt-1 min-h-20 w-full" required value={purpose} onChange={event => setPurpose(event.target.value)} /></label>
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-brand" disabled={!purpose.trim() || claim.isPending}>{claim.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send request`}</button>
      <button type="button" className="desk-button-ghost" onClick={() => setOpen(false)}>{t`Cancel`}</button>
    </div>
    {claim.error ? <p role="alert" className="text-sm text-danger">{claim.error.message}</p> : null}
  </form>;
}
