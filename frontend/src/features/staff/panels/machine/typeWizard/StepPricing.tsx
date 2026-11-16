import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { RouteLink } from "../../../../../components/ui/RouteLink";
import { getMachineTypePricing, machineKeys, setMachineTypePricing } from "../../../machinesApi";
import { usePriceDropCheck } from "../../../priceDrop/usePriceDropCheck";
import { useStaffChargesOn } from "../../../useStaffChargesOn";
import type { StepProps } from "./wizardTypes";

const CHARGE_BY = (): Record<string, string> => ({ time: t`by machine time`, material: t`by material used`, job: t`per job`, none: t`not charged` });

/** Step 5: the type's rate card, through the existing machine-type-pricing endpoint. Member and non-member prices are automatic discounts. */
export function StepPricing({ ctx }: StepProps) {
  const type = ctx.machineType!;
  const client = useQueryClient();
  const chargesOn = useStaffChargesOn("machines", ctx.makerspaceId);
  const pricing = useQuery({ queryKey: machineKeys.pricing(ctx.makerspaceId), queryFn: () => getMachineTypePricing(ctx.makerspaceId), enabled: chargesOn });
  const row = pricing.data?.results.find(item => item.machine_type_id === type.id);
  const [draft, setDraft] = useState<{ rate?: string; flat?: string; enabled?: boolean }>({});
  const body = () => ({ rate_per_unit: draft.rate ?? row?.rate_per_unit ?? "0.00", flat_fee: draft.flat ?? row?.flat_fee ?? "0.00", payment_enabled: draft.enabled ?? row?.payment_enabled ?? false });
  const save = useMutation({ mutationFn: () => setMachineTypePricing(ctx.makerspaceId, type.id, body()), onSuccess: () => client.invalidateQueries({ queryKey: machineKeys.pricing(ctx.makerspaceId) }) });
  const drop = usePriceDropCheck(ctx.makerspaceId);
  const submit = async () => { if (await drop.check(`/admin/makerspace/${ctx.makerspaceId}/machine-type-pricing/${type.id}`, "PUT", body())) save.mutate(); };
  const hint = ctx.spec ? CHARGE_BY()[ctx.spec.pricing.charge_by] : undefined;
  const currency = pricing.data?.currency ?? "";
  if (!chargesOn) return <p className="text-sm text-muted">{t`Machine charges are off in this space, so machine use is free. Turn charges on in settings to price this type.`}</p>;
  return <div className="grid gap-3">
    {hint ? <p className="text-sm text-muted">{t`The template suggests charging ${hint}.`}</p> : null}
    <p className="text-sm text-muted">{t`Member and non-member prices are set with automatic discounts, not separate rate cards.`} <RouteLink className="underline" href={ctx.hrefFor("settings")}>{t`Open pricing settings`}</RouteLink></p>
    {pricing.isLoading ? <LogoLoader label={t`Loading pricing…`} size={48} className="min-h-16 py-3" /> : null}
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); void submit(); }}>
      <label className="grid gap-1 text-sm">{t`Rate per unit (${currency})`}<input className="desk-input tabular-nums" type="number" min="0" step="any" value={draft.rate ?? row?.rate_per_unit ?? "0.00"} onChange={event => setDraft({ ...draft, rate: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">{t`Flat fee (${currency})`}<input className="desk-input tabular-nums" type="number" min="0" step="any" value={draft.flat ?? row?.flat_fee ?? "0.00"} onChange={event => setDraft({ ...draft, flat: event.target.value })} /></label>
      <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={draft.enabled ?? row?.payment_enabled ?? false} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} />{t`Enable payment`}</label>
      <div><button type="submit" className="desk-button-primary min-h-11" disabled={save.isPending || drop.checking}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save pricing`}</button></div>
    </form>
    {save.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Pricing saved.`}</p> : null}
    {[pricing.error, save.error].map((error, index) => error ? <p key={index} role="alert" className="text-sm text-danger">{error.message}</p> : null)}
    {drop.dialog}
  </div>;
}
