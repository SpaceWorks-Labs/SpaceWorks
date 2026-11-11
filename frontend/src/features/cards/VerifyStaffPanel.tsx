// What staff see under a scanned check link (parity C15): the member and the next steps. It asks the server
// only when someone is signed in, and any refusal (not signed in, no scan right, member outside the staff
// member's scope) renders nothing, so the public page never hints that a member exists. A scan identifies;
// it never signs anyone in. Renewing and recording a payment open the member in the console; revoking asks for a note.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ErrorBlock, Field, Modal } from "../../components/ui";
import { getAccessToken, refreshAccessToken, staffRequest } from "../../lib/api";

type StaffPanel = {
  makerspace_id: number; membership_id: number; member_url: string; card_state: "valid" | "expired" | "revoked";
  member: { name: string; number: string; plan: string; valid_until: string };
  actions: { key: "renew" | "record_payment" | "revoke_card"; method: string; path: string }[];
};

export function VerifyStaffPanel({ token, onChanged }: { token: string; onChanged: () => void }) {
  const [revoking, setRevoking] = useState(false);
  const [note, setNote] = useState("");
  const panel = useQuery({ queryKey: ["card-verify-staff", token], retry: false, staleTime: 0, gcTime: 0,
    queryFn: async () => {
      if (!getAccessToken("person") && !(await refreshAccessToken("person"))) throw new Error("no session");
      return staffRequest<StaffPanel>(`/admin/card-verifications/${encodeURIComponent(token)}/staff`, {}, "person");
    } });
  const revoke = useMutation({
    mutationFn: (path: string) => staffRequest(`/admin/${path}`, { method: "POST", body: JSON.stringify({ note: note.trim() }) }, "person"),
    onSuccess: () => { setRevoking(false); setNote(""); void panel.refetch(); onChanged(); },
  });
  const data = panel.data;
  if (!data) return null;
  const has = (key: StaffPanel["actions"][number]["key"]) => data.actions.find((action) => action.key === key);
  const revokeAction = has("revoke_card");
  const facts = [[t`Name`, data.member.name], [t`Number`, data.member.number], [t`Plan`, data.member.plan], [t`Valid until`, data.member.valid_until]]
    .filter((row): row is [string, string] => Boolean(row[1]));

  return <section className="mt-4 grid gap-3 rounded-card border border-line bg-panel p-6" aria-label={t`For staff`}>
    <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-muted">{t`For staff`}</h2>
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
      {facts.map(([label, value]) => <div key={label} className="grid gap-0.5"><dt className="text-xs text-muted">{label}</dt><dd className="font-medium text-ink">{value}</dd></div>)}
    </dl>
    <div className="flex flex-wrap gap-2">
      <a className="desk-button min-h-11" href={data.member_url}>
        {has("renew") || has("record_payment") ? t`Open member to renew or record a payment` : t`Open member`}</a>
      {revokeAction && data.card_state !== "revoked" ? <button type="button" className="desk-button-danger min-h-11" onClick={() => setRevoking(true)}>{t`Revoke card`}</button> : null}
    </div>
    <Modal open={revoking} onClose={() => setRevoking(false)} title={t`Revoke this card?`}
      footer={<div className="desk-actions flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={revoke.isPending} onClick={() => setRevoking(false)}>{t`Cancel`}</button>
        <button type="button" className="desk-button-danger" disabled={revoke.isPending || note.trim().length < 3}
          onClick={() => revokeAction && revoke.mutate(revokeAction.path)}>{revoke.isPending ? t`Revoking…` : t`Revoke card`}</button>
      </div>}>
      <p className="text-sm text-muted">{t`${data.member.name}'s card stops working at the door and on this page.`}</p>
      <Field label={t`Why is it revoked?`} hint={t`Seen by staff only.`} className="mt-3">
        <input className="desk-input min-h-11" value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
      </Field>
      {revoke.error ? <div className="mt-3"><ErrorBlock error={revoke.error} /></div> : null}
    </Modal>
  </section>;
}
