import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { financeError } from "./financeApi";

type GstinResult = { valid: true; gstin: string; state_code: string; state_name: string };

/** Offline GSTIN check (format, state code, check character). Nothing is looked up or saved. */
export function GstinCheck({ makerspaceId, gstin }: { makerspaceId: number; gstin: string }) {
  const check = useMutation({
    mutationFn: (value: string) => staffRequest<GstinResult>(`/admin/makerspace/${makerspaceId}/billing/tax/validate-gstin`,
      { method: "POST", body: JSON.stringify({ gstin: value }) }),
  });
  const value = gstin.trim().toUpperCase();
  const current = check.variables === value;
  return <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
    <button type="button" className="desk-button-ghost" disabled={value.length !== 15 || check.isPending} onClick={() => check.mutate(value)}>
      {check.isPending ? t`Checking…` : t`Check GSTIN`}</button>
    {current && check.data ? <p role="status" className="text-sm">{t`Valid GSTIN for ${check.data.state_name} (state ${check.data.state_code}).`}</p> : null}
    {current && check.error ? <p role="alert" className="text-sm text-danger">{financeError(check.error)}</p> : null}
  </div>;
}
