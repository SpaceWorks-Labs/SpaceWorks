import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText, guestKeys, guestMemberApi, operationId } from "../api";
import { passStatusLabel, passStatusTone } from "../labels";
import { memberAllowancesKey, useMemberAllowances } from "../../members/MemberAllowances";

/**
 * "Bring a guest" for an active member (decision 223 b). The answer is always the same sentence
 * whether or not the e-mail has an account, so nobody can probe who uses the space; only the
 * member's own limits (tenure, check-in, guest count) are refused by name.
 */
export function BringAGuest({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [key, setKey] = useState(operationId);
  const guests = useQuery({ queryKey: guestKeys.sponsored(makerspaceId), queryFn: () => guestMemberApi.sponsored(makerspaceId), retry: false });
  // #234 addendum 3(a): how many more guests this member may bring right now (the per-sponsor limit).
  const allowance = useMemberAllowances(makerspaceId).data?.guest_passes ?? null;
  const noneLeft = allowance?.limit != null && allowance.remaining === 0;
  const refresh = () => {
    void client.invalidateQueries({ queryKey: memberAllowancesKey(makerspaceId) });
    return client.invalidateQueries({ queryKey: guestKeys.sponsored(makerspaceId) });
  };
  const invite = useMutation({
    mutationFn: () => guestMemberApi.sponsor(makerspaceId, email.trim(), key),
    onSuccess: () => { setEmail(""); setKey(operationId()); void refresh(); },
  });
  const withdraw = useMutation({ mutationFn: (passId: number) => guestMemberApi.revokeSponsored(makerspaceId, passId, ""), onSuccess: refresh });
  if (guests.isError) return null; // Guest passes off here, or no longer a member.
  const rows = guests.data ?? [];
  return <section aria-labelledby="bring-guest-title" className="desk-panel grid gap-4 p-5">
    <div><h2 id="bring-guest-title" className="title-panel">{t`Bring a guest`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Your guest needs an account here. They get a pass for today and see what it allows on their phone.`}</p>
      {allowance?.limit != null ? <p className="mt-1 text-sm text-ink">{t`You can bring ${allowance.remaining ?? 0} more of ${allowance.limit} guests right now.`}</p> : null}</div>
    <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (email.trim()) invite.mutate(); }}>
      <Field label={t`Guest's e-mail`} className="min-w-0 flex-1 basis-56">
        <input className="desk-input" type="email" autoComplete="off" value={email} onChange={(event) => { setEmail(event.target.value); invite.reset(); }} />
      </Field>
      <button type="submit" className="desk-button-brand min-h-11" disabled={!email.trim() || invite.isPending || noneLeft}
        title={noneLeft ? t`You already have the most guests allowed at once. Withdraw a pass or wait until one ends.` : undefined}>{invite.isPending ? t`Sending…` : t`Bring guest`}</button>
    </form>
    {noneLeft ? <p role="status" className="text-sm text-muted">{t`You already have the most guests allowed at once. Withdraw a pass or wait until one ends.`}</p> : null}
    {invite.data ? <p role="status" className="text-sm text-success-ink">{invite.data.detail}</p> : null}
    {invite.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(invite.error)}</p> : null}
    {guests.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading your guests…`}</p> : null}
    {rows.length ? <ul className="grid gap-2" aria-label={t`Your guests`}>
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-center gap-2 rounded-control border border-line p-3 text-sm">
        <span className="min-w-0 flex-1 basis-40 font-semibold text-ink">{row.guest_name || t`Guest`}<span className="font-normal text-muted"> · {formatDate(row.pass_date)}</span></span>
        <StatusPill tone={passStatusTone(row.status)} label={passStatusLabel(row.status)} />
        {row.items_outstanding ? <StatusPill tone="warn" label={t`Items still out`} /> : null}
        {row.status === "active" || row.status === "issued"
          ? <button type="button" className="desk-button-ghost min-h-11" disabled={withdraw.isPending} onClick={() => withdraw.mutate(row.id)}>{t`Withdraw pass`}</button> : null}
      </li>)}
    </ul> : null}
    {withdraw.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(withdraw.error)}</p> : null}
  </section>;
}
