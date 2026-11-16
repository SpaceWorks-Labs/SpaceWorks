import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { lifecycleApi, lifecycleKeys } from "../staff/membershipLifecycleApi";
import { financeError } from "./financeApi";

type Space = { id: number; enabled_features?: string[] };
const FEATURE = "billing.fy_receipts";

/** Mirrors `numbering_fy_receipts.prefix_for`: the receipt prefix when it is 1-4 of A-Z 0-9 - /, else "R". */
export function fyReceiptPrefix(prefix: string | undefined): string {
  const value = (prefix ?? "").trim();
  return /^[A-Z0-9/-]{1,4}$/.test(value) ? value : "R";
}

/** "2026-27" -> "26-27", "2026" -> "26": the compact year the server puts in the number. */
export function fyShort(label: string | undefined): string {
  return /^\d{4}(-\d{2})?$/.test(label ?? "") ? label!.slice(2) : (label ?? "");
}

/**
 * Parity O-B3 Settings › Payments & billing: number receipts per financial year (`billing.fy_receipts`) while no
 * tax is charged. The same switch as under Features; it needs Receipt documents. Turning it on never renumbers.
 */
export function FyReceiptsSetting({ makerspace }: { makerspace: Space }) {
  const client = useQueryClient();
  const features = makerspace.enabled_features ?? [];
  const on = features.includes(FEATURE);
  const documentsOn = features.includes("billing.documents");
  const year = useQuery({ queryKey: lifecycleKeys.financialYear(makerspace.id), queryFn: () => lifecycleApi.financialYear(makerspace.id) });
  const policy = useQuery({ queryKey: ["billing-policy", makerspace.id], enabled: documentsOn,
    queryFn: () => staffRequest<{ number_prefix: string }>(`/admin/makerspace/${makerspace.id}/billing-settings`) });
  const sample = `${fyReceiptPrefix(policy.data?.number_prefix)}${fyShort(year.data?.current_label)}/0001`;
  const toggle = useMutation({
    mutationFn: (next: boolean) => staffRequest(`/admin/makerspaces/${makerspace.id}`, { method: "PATCH",
      body: JSON.stringify({ enabled_features: next ? [...features, FEATURE] : features.filter((key) => key !== FEATURE) }) }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      void client.invalidateQueries({ queryKey: ["makerspaces"] });
      void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });
  return <SettingsRow label={t`Receipt numbers per financial year`}
    helper={t`For spaces that charge no tax: receipts are numbered per financial year and start again at 0001 each year. With tax on, tax documents already follow their own yearly series.`}>
    <div className="grid min-w-0 gap-3">
      <label className="flex min-h-11 items-center gap-3 text-sm font-semibold text-ink">
        <input type="checkbox" role="switch" className="h-5 w-5" checked={on} disabled={(!documentsOn && !on) || toggle.isPending}
          aria-checked={on} onChange={(event) => toggle.mutate(event.target.checked)} />
        {on ? t`On: new receipts are numbered per financial year` : t`Off: receipts use one running number`}
      </label>
      {year.data ? <p className="text-sm text-ink">{on ? t`This year's receipts read ` : t`Once on, this year's receipts read `}
        <strong className="tabular-nums">{sample}</strong>{t`, then 0002 and so on (FY ${year.data.current_label}).`}</p> : null}
      <p className="text-sm text-muted">{t`The day you turn this on is the cut-over: receipts already issued keep their numbers, and nothing is ever renumbered. The prefix is your receipt prefix when it is up to four capital letters, digits, "-" or "/", otherwise R.`}</p>
      {!documentsOn ? <p className="text-sm text-muted">{t`Turn on “Receipt documents” under Features first; this numbering applies to the receipts it issues.`}</p> : null}
      {toggle.error ? <p role="alert" className="text-sm text-danger">{financeError(toggle.error)}</p> : null}
    </div>
  </SettingsRow>;
}
