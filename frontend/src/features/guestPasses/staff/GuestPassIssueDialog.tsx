import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, Modal } from "../../../components/ui";
import { formatMoney, formatPrice } from "../../../lib/money";
import { guestErrorText, guestKeys, guestStaffApi, operationId, personRef, type PurchaseResult } from "../api";

type Mode = "issue" | "sell";

/**
 * Staff issue a free pass (optionally on a member's behalf) or sell a day pass at the desk.
 * The person must already have an account: give their e-mail or account number. A priced
 * day pass records the amount owed; staff settle it with a cash receipt under Payments.
 */
export function GuestPassIssueDialog({ makerspaceId, mode, onClose }: { makerspaceId: number; mode: Mode; onClose: () => void }) {
  const client = useQueryClient();
  const [person, setPerson] = useState("");
  const [sponsor, setSponsor] = useState("");
  const [day, setDay] = useState("");
  const [productId, setProductId] = useState<number | null>(null);
  const [key] = useState(operationId);
  const [sold, setSold] = useState<PurchaseResult | null>(null);
  const products = useQuery({ queryKey: guestKeys.products(makerspaceId), queryFn: () => guestStaffApi.products(makerspaceId), enabled: mode === "sell" });
  const live = (products.data ?? []).filter((row) => row.is_active && !row.archived_at);
  const chosen = productId ?? live[0]?.id ?? null;
  const ref = personRef(person);
  const save = useMutation({
    mutationFn: async () => {
      if (!ref) throw new Error(t`Enter the person's e-mail or account number.`);
      const base = { ...ref, ...(day ? { day } : {}), operation_id: key };
      if (mode === "sell") return guestStaffApi.sell(makerspaceId, { ...base, product_id: chosen! });
      await guestStaffApi.issue(makerspaceId, { ...base, ...(/^\d+$/.test(sponsor.trim()) ? { sponsor_id: Number(sponsor.trim()) } : {}) });
      return null;
    },
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: guestKeys.all(makerspaceId) });
      if (result) { setSold(result); void client.invalidateQueries({ queryKey: ["payments", makerspaceId] }); } else onClose();
    },
  });
  const title = mode === "sell" ? t`Sell a day pass` : t`Issue a guest pass`;
  if (sold) {
    return <Modal open title={title} onClose={onClose} footer={<button type="button" className="desk-button-primary" onClick={onClose}>{t`Done`}</button>}>
      <div role="status" className="grid gap-2 text-sm">
        <p className="font-semibold text-ink">{t`Day pass recorded.`}</p>
        {sold.payment_id && Number(sold.amount) > 0
          ? <p className="text-muted">{t`${formatMoney(sold.amount, sold.currency)} is owed. Take payment and record it with a receipt under Payments; the pass goes live once it is paid or waived.`}</p>
          : <p className="text-muted">{t`This pass is free and live for the day.`}</p>}
      </div>
    </Modal>;
  }
  return <Modal open title={title} onClose={() => { if (!save.isPending) onClose(); }} footer={<div className="flex flex-wrap justify-end gap-2">
    <button type="button" className="desk-button" disabled={save.isPending} onClick={onClose}>{t`Cancel`}</button>
    <button type="button" className="desk-button-primary" disabled={!ref || save.isPending || (mode === "sell" && !chosen)} onClick={() => save.mutate()}>
      {save.isPending ? t`Saving…` : mode === "sell" ? t`Record sale` : t`Issue pass`}</button>
  </div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`A pass is a dated permit for an existing account. It is never a membership and the guest gets no member card.`}</p>
      <Field label={t`Guest's e-mail or account number`} hint={t`The guest needs an account. Add a walk-in from Direct handout if they have none.`}>
        <input className="desk-input" autoComplete="off" value={person} onChange={(event) => setPerson(event.target.value)} />
      </Field>
      {mode === "issue" ? <Field label={t`Sponsoring member's account number (optional)`} hint={t`Leave blank for a pass from the space itself.`}>
        <input className="desk-input" inputMode="numeric" value={sponsor} onChange={(event) => setSponsor(event.target.value.replace(/\D/g, ""))} />
      </Field> : null}
      {mode === "sell" ? <Field label={t`Day pass`}>
        {products.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading day passes…`}</p>
          : live.length ? <select className="desk-input" value={chosen ?? ""} onChange={(event) => setProductId(Number(event.target.value))}>
            {live.map((row) => <option key={row.id} value={row.id}>{`${row.name} · ${formatPrice(row.amount, row.currency)}`}</option>)}
          </select> : <p className="text-sm text-muted">{t`No day passes are on sale. Add one under Settings › Guest passes.`}</p>}
      </Field> : null}
      <Field label={t`Day`} hint={t`Leave blank for today.`}>
        <input className="desk-input" type="date" value={day} onChange={(event) => setDay(event.target.value)} />
      </Field>
      {products.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(products.error)}</p> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(save.error)}</p> : null}
    </div>
  </Modal>;
}
