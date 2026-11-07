import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { BadgePercent } from "lucide-react";
import { Card } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { panelField, panelInput } from "../eventPanelStyles";
import { useRefundPolicy, type RefundPolicyInput } from "./staffTicketingApi";

const blank: RefundPolicyInput = { enabled: false, full_before_minutes: 1440, partial_before_minutes: 0, partial_percent: 0,
  cancellation_fee: "0.00", policy_text: "" };

/** G34: this event's own refund policy. Once anything is sold it may only become more generous. */
export function EventRefundPolicyForm({ eventId, disabled = false }: { eventId: number; disabled?: boolean }) {
  const { policy, save } = useRefundPolicy(eventId);
  const [values, setValues] = useState(blank);
  useEffect(() => {
    const data = policy.data;
    if (!data) return;
    setValues({ enabled: data.overridden, policy_text: data.text,
      full_before_minutes: Number(data.terms?.full_before_minutes ?? 1440), partial_before_minutes: Number(data.terms?.partial_before_minutes ?? 0),
      partial_percent: Number(data.terms?.partial_percent ?? 0), cancellation_fee: data.terms?.cancellation_fee ?? "0.00" });
  }, [policy.data]);
  const set = <K extends keyof RefundPolicyInput>(key: K, value: RefundPolicyInput[K]) => setValues(current => ({ ...current, [key]: value }));
  const refused = save.error instanceof StructuredApiError && save.error.code === "policy_less_generous";
  return <Card><form className="grid gap-4" aria-label={t`Refund policy`} onSubmit={event => { event.preventDefault(); save.mutate(values); }}>
    <h3 className="title-section flex items-center gap-2"><BadgePercent aria-hidden="true" size={18} />{t`Refund policy for this event`}</h3>
    {policy.data?.locked ? <p className="text-sm text-muted">{t`Tickets have been sold, so this policy can only become more generous.`}</p> : null}
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={values.enabled} disabled={disabled}
      onChange={event => set("enabled", event.target.checked)} />{t`Use this event's own policy instead of the space's`}</label>
    {values.enabled ? <>
      <label className={panelField}>{t`Full refund until (hours before the start)`}<input className={panelInput} type="number" min="0" value={values.full_before_minutes / 60} disabled={disabled}
          onChange={event => set("full_before_minutes", Math.round(Number(event.target.value) * 60))} /></label>
      <label className={panelField}>{t`Partial refund until (hours before the start)`}<input className={panelInput} type="number" min="0" value={values.partial_before_minutes / 60} disabled={disabled}
          onChange={event => set("partial_before_minutes", Math.round(Number(event.target.value) * 60))} /></label>
      <label className={panelField}>{t`Partial refund, percent`}<input className={panelInput} type="number" min="0" max="100" value={values.partial_percent} disabled={disabled}
          onChange={event => set("partial_percent", Number(event.target.value))} /></label>
      <label className={panelField}>{t`Cancellation fee kept`}<input className={panelInput} type="number" min="0" step="0.01" value={values.cancellation_fee} disabled={disabled}
          onChange={event => set("cancellation_fee", event.target.value)} /></label>
    </> : null}
    <label className={panelField}>{t`Words buyers see before paying`}<textarea className={panelInput} rows={3} maxLength={2000} value={values.policy_text} disabled={disabled}
        onChange={event => set("policy_text", event.target.value)} /></label>
    {save.error ? <p role="alert" className="text-sm text-danger">{refused ? t`After the first sale the policy can only get more generous.` : save.error.message}</p> : null}
    <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || save.isPending}>{t`Save refund policy`}</button>
  </form></Card>;
}
