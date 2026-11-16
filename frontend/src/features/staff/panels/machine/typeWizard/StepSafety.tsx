import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { adapterErrorMessage } from "../adapters/adapterCopy";
import { adapterKeys, adaptersApi } from "../adapters/adaptersApi";
import { ReadOnlyStep, yesNo } from "./ReadOnlyStep";
import type { StepProps } from "./wizardTypes";

const minutes = (value: string) => { const n = Number(value); return value.trim() !== "" && Number.isInteger(n) && n >= 1 && n <= 1440 ? n : undefined; };

function SafetyForm({ ctx }: StepProps) {
  const typeId = ctx.machineType!.id;
  const client = useQueryClient();
  const profile = useQuery({ queryKey: adapterKeys.profile(ctx.makerspaceId, typeId), queryFn: () => adaptersApi.profile(ctx.makerspaceId, typeId) });
  const suggested = ctx.prefill?.safety ?? ctx.spec?.safety;
  const saved = profile.data?.config ?? {};
  const [draft, setDraft] = useState<{ idle: string; longest: string; clear: boolean; filter: boolean } | null>(null);
  const empty = !profile.data?.updated_at;
  const form = draft ?? { idle: String(saved.auto_off_idle_minutes ?? (empty ? suggested?.idle_auto_off_minutes : undefined) ?? ""),
    longest: String(saved.max_session_minutes ?? (empty ? suggested?.max_session_minutes : undefined) ?? ""),
    clear: saved.require_area_clear ?? (empty ? suggested?.area_clear_required : undefined) ?? false,
    filter: saved.require_filter_ok ?? (empty ? suggested?.filter_ok_required : undefined) ?? false };
  const bad = (value: string) => value.trim() !== "" && minutes(value) === undefined;
  const save = useMutation({ mutationFn: () => adaptersApi.setProfile(ctx.makerspaceId, typeId, {
    ...(minutes(form.idle) ? { auto_off_idle_minutes: minutes(form.idle) } : {}), ...(minutes(form.longest) ? { max_session_minutes: minutes(form.longest) } : {}),
    require_area_clear: form.clear, require_filter_ok: form.filter }),
  onSuccess: () => { setDraft(null); void client.invalidateQueries({ queryKey: adapterKeys.profile(ctx.makerspaceId, typeId) }); } });
  if (profile.isLoading) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  return <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (!bad(form.idle) && !bad(form.longest)) save.mutate(); }}>
    <p className="text-sm text-muted">{t`Defaults for every adapter target on machines of this type. A single target can override them.`}</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Switch off when idle for (minutes)`}<input className="desk-input" inputMode="numeric" value={form.idle} onChange={event => setDraft({ ...form, idle: event.target.value })} />
        {bad(form.idle) ? <span className="text-xs text-danger">{t`Use a whole number from 1 to 1440.`}</span> : null}</label>
      <label className="grid gap-1 text-sm">{t`Longest session (minutes)`}<input className="desk-input" inputMode="numeric" value={form.longest} onChange={event => setDraft({ ...form, longest: event.target.value })} />
        {bad(form.longest) ? <span className="text-xs text-danger">{t`Use a whole number from 1 to 1440.`}</span> : null}</label>
    </div>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.clear} onChange={event => setDraft({ ...form, clear: event.target.checked })} />{t`Work area must be confirmed clear before it starts`}</label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.filter} onChange={event => setDraft({ ...form, filter: event.target.checked })} />{t`Filter must be healthy before it starts`}</label>
    {save.isError || profile.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(save.error ?? profile.error)}</p> : null}
    {save.isSuccess && !draft ? <p role="status" className="text-sm text-success-ink">{t`Saved.`}</p> : null}
    <div><button type="submit" className="desk-button-primary min-h-11" disabled={save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save safety defaults`}</button></div>
  </form>;
}

/** Step 8: the adapter safety profile (`adapter-profile` PUT) when device adapters are available, otherwise the template values as notes. */
export function StepSafety({ ctx }: StepProps) {
  if (ctx.printerAdapter) return <SafetyForm ctx={ctx} />;
  const safety = ctx.prefill?.safety ?? ctx.spec?.safety;
  return <ReadOnlyStep intro={t`Device adapters are not available here, so these safety values are notes only. Staff apply them by hand.`}
    rows={safety ? [[t`Switch off when idle (minutes)`, String(safety.idle_auto_off_minutes ?? "-")], [t`Longest session (minutes)`, String(safety.max_session_minutes ?? "-")],
      [t`Area confirmed clear first`, yesNo(safety.area_clear_required)], [t`Filter healthy first`, yesNo(safety.filter_ok_required)]] : []} />;
}
