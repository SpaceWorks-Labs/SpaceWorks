import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorText, Skeleton } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { rateHint, rateLabel } from "./limitCopy";
import { useRequestRates, useSaveRequestRate, type RequestRate } from "./limitsApi";

function RateRow({ row }: { row: RequestRate }) {
  const save = useSaveRequestRate();
  const [value, setValue] = useState(row.rate);
  const done = () => toast(t`Request rate saved.`);
  return <li className="grid gap-2 border-b border-line py-3 sm:grid-cols-[1fr_auto]">
    <div>
      <p className="text-sm font-medium text-ink">{rateLabel(row.scope)}</p>
      <p className="text-xs text-muted">{rateHint(row.scope)}</p>
      <p className="text-xs text-muted">{t`Write it as a count per sec, min, hour or day, for example 30/min. Standard: ${row.default} (server setting ${row.env_key}); you can choose ${row.min_rate} to ${row.max_rate}.`}</p>
      {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    </div>
    <div className="flex flex-wrap items-center gap-2">
      <input className="desk-input w-28" aria-label={t`Rate for ${rateLabel(row.scope)}`} value={value} onChange={event => setValue(event.target.value)} />
      <button type="button" className="desk-button" disabled={save.isPending || value.trim() === row.rate}
        onClick={() => save.mutate({ scope: row.scope, rate: value.trim() }, { onSuccess: done })}>{t`Save`}</button>
      {row.overridden ? <button type="button" className="desk-button" disabled={save.isPending}
        onClick={() => save.mutate({ scope: row.scope, rate: null }, { onSuccess: () => { setValue(row.default); done(); } })}>{t`Use standard rate`}</button> : null}
    </div>
  </li>;
}

/** Deployment-wide request rates: env defaults, superadmin overrides within safe bounds. */
export function RequestRatesSection() {
  const rates = useRequestRates();
  if (rates.isLoading) return <Skeleton className="h-24 w-full" />;
  if (rates.isError || !Array.isArray(rates.data)) return <ErrorText resource={t`request rates`} onRetry={() => { void rates.refetch(); }} />;
  return <ul className="grid">{rates.data.map(row => <RateRow key={`${row.scope}:${row.rate}`} row={row} />)}</ul>;
}
