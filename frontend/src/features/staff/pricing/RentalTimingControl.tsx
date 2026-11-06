import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { pricingApi, pricingError, pricingKeys, type RentalTiming } from "./pricingApi";

const OPTIONS: [RentalTiming["rental_timing"], string, string][] = [
  ["at_checkout", "At checkout, for the planned days", "The rental is charged when the loan is issued, for the days until it is due."],
  ["at_return", "At return, for the actual days", "The rental is charged when the item comes back, for the days it was out."],
];

/** When per-day rental is charged: its own endpoint, so an Inventory Manager can change it without a grant. */
export function RentalTimingControl({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const timing = useQuery({ queryKey: pricingKeys.timing(makerspaceId), queryFn: () => pricingApi.timing(makerspaceId) });
  const save = useMutation({
    mutationFn: (value: RentalTiming["rental_timing"]) => pricingApi.setTiming(makerspaceId, value),
    onSuccess: data => {
      client.setQueryData(pricingKeys.timing(makerspaceId), data);
      void client.invalidateQueries({ queryKey: pricingKeys.card(makerspaceId, "loans") });
    },
  });
  if (timing.isLoading) return <p role="status" className="text-sm text-muted">{t`Loading rental timing…`}</p>;
  if (timing.error) return <p role="alert" className="text-sm text-danger">{pricingError(timing.error)}</p>;
  if (!timing.data) return null;
  const { editable, locked } = timing.data;
  const current = save.isPending && save.variables ? save.variables : timing.data.rental_timing;
  return <fieldset className="grid gap-2 rounded-xl border border-line bg-surface p-4">
    <legend className="px-1 font-semibold text-ink">{t`Rental timing`}</legend>
    <p className="text-xs text-muted">{t`Applies to loans issued after you change it.`}</p>
    {OPTIONS.map(([value, label, explanation]) => <label key={value} className="flex min-h-11 items-start gap-3 text-sm">
      <input type="radio" name={`rental-timing-${makerspaceId}`} className="mt-1 h-4 w-4" checked={current === value}
        disabled={!editable} onChange={() => { if (!save.isPending) save.mutate(value); }} />
      <span><span className="font-semibold text-ink">{label}</span>
        <span className="block text-xs text-muted">{explanation}</span></span>
    </label>)}
    {locked ? <p className="text-xs text-muted">{t`The Space Manager has locked this setting`}{editable ? t`; other managers cannot change it.` : "."}</p> : null}
    {!editable && !locked ? <p className="text-xs text-muted">{t`Only the Space Manager or the Inventory Manager can change this.`}</p> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{pricingError(save.error)}</p> : null}
    {save.isSuccess && !save.isPending ? <p role="status" className="text-xs text-muted">{t`Rental timing saved.`}</p> : null}
  </fieldset>;
}
