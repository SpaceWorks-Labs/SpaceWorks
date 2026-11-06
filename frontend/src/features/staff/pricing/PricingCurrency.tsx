import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Coins } from "lucide-react";

import { Field } from "../../../components/ui";
import { isNotFound, pricingApi, pricingError, pricingKeys } from "./pricingApi";

/** The currency new charges are raised in. A finance setting: the Space Manager edits it; a 404 hides it. */
export function PricingCurrency({ makerspaceId, canEdit }: { makerspaceId: number; canEdit: boolean }) {
  const client = useQueryClient();
  const currency = useQuery({ queryKey: pricingKeys.currency(makerspaceId), queryFn: () => pricingApi.currency(makerspaceId),
    retry: false });
  const [value, setValue] = useState("");
  const [left, setLeft] = useState(false);
  useEffect(() => { if (currency.data) setValue(currency.data.default_currency.toUpperCase()); }, [currency.data]);
  const save = useMutation({
    mutationFn: () => pricingApi.setCurrency(makerspaceId, value.trim().toLowerCase()),
    onSuccess: data => {
      client.setQueryData(pricingKeys.currency(makerspaceId), data);
      void client.invalidateQueries({ queryKey: ["pricing", makerspaceId] });
      void client.invalidateQueries({ queryKey: ["payment-settings", makerspaceId] });
    },
  });
  if (isNotFound(currency.error) || (!currency.data && !currency.error)) return null;
  if (currency.error) return <p role="alert" className="text-sm text-danger">{pricingError(currency.error)}</p>;
  const valid = /^[A-Za-z]{3}$/.test(value.trim());
  const dirty = value.trim().toLowerCase() !== currency.data!.default_currency.toLowerCase();
  return <form className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-surface p-4"
    onSubmit={event => { event.preventDefault(); if (valid && dirty) save.mutate(); }}>
    <Coins aria-hidden="true" size={20} className="mb-3 text-muted" />
    <Field label={t`Currency for new charges`} hint={t`Three-letter code, like INR or USD. Existing charges keep their currency.`}
      error={value && !valid && (left || value.length >= 3) ? "Enter a three-letter currency code." : undefined}>
      <input className="desk-input w-28 uppercase" maxLength={3} value={value} disabled={!canEdit || save.isPending}
        onBlur={() => setLeft(true)} onChange={event => { setValue(event.target.value.toUpperCase()); save.reset(); }} />
    </Field>
    {canEdit ? <button type="submit" className="desk-button" disabled={!valid || !dirty || save.isPending}>
      {save.isPending ? t`Saving…` : t`Save currency`}</button>
      : <p className="mb-3 text-xs text-muted">{t`Only the Space Manager changes the currency.`}</p>}
    {save.isSuccess ? <p role="status" className="mb-3 text-xs text-muted">{t`Currency saved.`}</p> : null}
    {save.error ? <p role="alert" className="w-full text-sm text-danger">{pricingError(save.error)}</p> : null}
  </form>;
}
