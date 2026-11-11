import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ErrorText, Field, Modal } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import type { ToBuyItem } from "./ProcurementPanelRows";

/**
 * Credits a received to-buy item back to the machine consumable that raised it, once. Used
 * when the item reached Received without "Mark bought" (which refills in the same step).
 */
export function RefillConsumableDialog({ item, onClose, onDone }: { item: ToBuyItem; onClose: () => void; onDone: () => void }) {
  const [amount, setAmount] = useState("");
  const refill = useMutation({
    mutationFn: () => staffRequest<ToBuyItem>(`/procurement/to-buy/${item.id}/refill-consumable`,
      { method: "POST", body: JSON.stringify({ amount: amount.trim() }) }),
    onSuccess: () => { onDone(); onClose(); },
  });
  const ready = /^\d{1,10}(\.\d{1,2})?$/.test(amount.trim()) && Number(amount) > 0;
  return <Modal open onClose={onClose} title={t`Refill consumable from ${item.name}`}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (ready) refill.mutate(); }}>
      <p className="text-sm text-muted">{t`Adds what arrived to the machine consumable this request came from. It can only be credited once.`}</p>
      <Field label={t`Amount received (grams)`}><input className="desk-input" inputMode="decimal" required value={amount}
        onChange={event => setAmount(event.target.value)} /></Field>
      <ErrorText message={refill.error?.message} />
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || refill.isPending}>{refill.isPending ? t`Saving…` : t`Refill`}</button>
      </div>
    </form>
  </Modal>;
}
