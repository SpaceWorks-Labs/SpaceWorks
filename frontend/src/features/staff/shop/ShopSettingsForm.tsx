import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { FormPageLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui";
import { errorCode, fetchSettings, saveSettings, staffShopError, staffShopKeys, type ShopSettings } from "./staffShopApi";

type Values = Required<Omit<ShopSettings, "updated_at">>;
const NUMBERS: { key: keyof Omit<Values, "policy_text" | "pickup_note">; label: string; hint: string }[] = [
  { key: "online_hold_minutes", label: "Online hold (minutes)", hint: "How long stock is set aside while a buyer pays online." },
  { key: "desk_hold_hours", label: "Pay-at-desk hold (hours)", hint: "How long an unpaid order waits at the desk." },
  { key: "returns_window_days", label: "Returns window (days)", hint: "Days after collection that items can come back." },
  { key: "first_reminder_days", label: "First pickup reminder (days)", hint: "Days after an order is ready." },
  { key: "second_reminder_days", label: "Second pickup reminder (days)", hint: "Days after an order is ready." },
  { key: "uncollected_cancel_days", label: "Cancel uncollected after (days)", hint: "Paid orders then open a refund case." },
];
const LOCKED = ["setting_not_delegated", "setting_locked"];

/** Shop settings. When the platform locks them, or they are not delegated to this role, they show read-only with the reason. */
export function ShopSettingsForm({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: staffShopKeys.settings(makerspaceId), queryFn: () => fetchSettings(makerspaceId), retry: false });
  const [values, setValues] = useState<Values | null>(null);
  useEffect(() => { if (query.data) setValues({ online_hold_minutes: 15, desk_hold_hours: 48, returns_window_days: 0, first_reminder_days: 0,
    second_reminder_days: 0, uncollected_cancel_days: 0, policy_text: "", pickup_note: "", ...query.data } as Values); }, [query.data]);
  const save = useMutation({ mutationFn: () => saveSettings(makerspaceId, values!),
    onSuccess: saved => client.setQueryData(staffShopKeys.settings(makerspaceId), saved) });
  const lockedError = [query.error, save.error].find(error => LOCKED.includes(errorCode(error) ?? ""));
  const readOnly = Boolean(lockedError);
  if (query.error && !query.data) return <FormPageLayout header={{ eyebrow: "Shop", title: "Shop settings" }} form={null}
    submit={{ label: "Save", disabled: true, disabledReason: staffShopError(query.error) }}
    state={readOnly ? { status: "ready" } : { status: "error", error: staffShopError(query.error), onRetry: () => { void query.refetch(); } }}
    isEmpty={readOnly} empty={{ message: staffShopError(query.error) }} />;
  const set = (patch: Partial<Values>) => setValues(current => current ? { ...current, ...patch } : current);
  return <FormPageLayout header={{ eyebrow: "Shop", title: "Shop settings", subtitle: "Holds, reminders, returns and what buyers read before ordering." }}
    state={!values ? { status: "loading" } : { status: "ready" }}
    submit={{ label: "Save settings", pending: save.isPending, pendingLabel: "Saving…", onClick: () => save.mutate(),
      disabled: readOnly, disabledReason: readOnly ? staffShopError(lockedError) : undefined }}
    form={values ? <fieldset className="grid gap-5" disabled={readOnly}>
      <legend className="sr-only">Shop settings</legend>
      {readOnly ? <p role="status" className="rounded-xl border border-line bg-surface p-3 text-sm">{staffShopError(lockedError)}</p> : null}
      {save.error && !readOnly ? <p role="alert" className="text-sm text-danger">{staffShopError(save.error)}</p> : null}
      {save.isSuccess ? <p role="status" className="text-sm text-muted">Settings saved.</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">{NUMBERS.map(field => <Field key={field.key} label={field.label} hint={field.hint}>
        <input className="desk-input min-h-11 w-32 tabular-nums" type="number" min={0} value={values[field.key]}
          onChange={event => set({ [field.key]: Math.max(0, Number(event.target.value) || 0) })} /></Field>)}</div>
      <Field label="Pickup note" hint="Shown to buyers before they order: where and when to collect.">
        <textarea className="desk-input" rows={3} value={values.pickup_note} onChange={event => set({ pickup_note: event.target.value })} /></Field>
      <Field label="Shop policy" hint="Shown to buyers before they order and pay.">
        <textarea className="desk-input" rows={5} value={values.policy_text} onChange={event => set({ policy_text: event.target.value })} /></Field>
    </fieldset> : null} />;
}
