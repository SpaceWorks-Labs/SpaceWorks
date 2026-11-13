import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field } from "../../../components/ui";
import { formatMoney, formatPrice } from "../../../lib/money";
import { PayNextStep } from "../../payments/PayNextStep";
import { guestErrorText, guestKeys, guestMemberApi, operationId, type PurchaseResult } from "../api";
import { LogoLoader } from "../../../components/LogoLoader";

/**
 * Buy a day pass from the member area (decision 223 b). A priced pass is pending until paid,
 * online when the space offers it or at the desk; PayNextStep says where. Hidden when the
 * space sells none, or the feature is off (the list answers 404).
 */
export function DayPassShop({ makerspaceId, paymentsHref }: { makerspaceId: number; paymentsHref: string }) {
  const client = useQueryClient();
  const [day, setDay] = useState("");
  const [bought, setBought] = useState<PurchaseResult | null>(null);
  const offers = useQuery({ queryKey: guestKeys.offers(makerspaceId), queryFn: () => guestMemberApi.offers(makerspaceId), retry: false });
  const buy = useMutation({
    mutationFn: (productId: number) => guestMemberApi.purchase(makerspaceId, productId, { ...(day ? { day } : {}), operation_id: operationId() }),
    onSuccess: (result) => {
      setBought(result);
      void client.invalidateQueries({ queryKey: guestKeys.mine(makerspaceId) });
      void client.invalidateQueries({ queryKey: ["member"] });
    },
  });
  const rows = offers.data ?? [];
  if (offers.isError || (offers.isSuccess && !rows.length)) return null;
  return <section aria-labelledby="day-pass-title" className="desk-panel grid gap-4 p-5">
    <div><h2 id="day-pass-title" className="title-panel">{t`Day passes`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Visit for a day without joining. A day pass is not a membership.`}</p></div>
    {offers.isLoading ? <LogoLoader label={t`Loading day passes…`} size={48} className="min-h-16 py-3" /> : null}
    <Field label={t`Day`} hint={t`Leave blank for today.`} className="max-w-xs">
      <input className="desk-input" type="date" value={day} onChange={(event) => setDay(event.target.value)} />
    </Field>
    <ul className="grid gap-2">
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-control border border-line p-3">
        <span className="min-w-0 flex-1 basis-40 text-sm font-semibold text-ink">{row.name}<span className="font-normal text-muted"> · {formatPrice(row.amount, row.currency)}</span></span>
        <button type="button" className="desk-button-brand min-h-11" disabled={buy.isPending}
          onClick={() => { setBought(null); buy.mutate(row.id); }}>{buy.isPending && buy.variables === row.id ? t`Buying…` : t`Buy ${row.name}`}</button>
      </li>)}
    </ul>
    {bought ? <div role="status" className="text-sm">
      <p className="font-semibold text-ink">{bought.payment_id && Number(bought.amount) > 0
        ? t`Your pass is reserved. ${formatMoney(bought.amount, bought.currency)} is due before it goes live.`
        : t`Your day pass is ready. It appears under My passes.`}</p>
      {bought.payment_id && bought.payment_status === "pending" ? <PayNextStep paymentsHref={paymentsHref} /> : null}
    </div> : null}
    {buy.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(buy.error)}</p> : null}
  </section>;
}
