import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Field, SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { EventMoneySettingsRead, PatchedEventMoneySettingsInput } from "../../generated/api";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";

type Draft = { prize_tds_enabled: boolean; prize_tds_rate: string; prize_tds_threshold: string; payee_templates: string[] };

const pairKey = (pair: string[]) => pair.join(":");
const METHOD_LABELS: Record<string, string> = {
  bank_transfer: t`Bank transfer`, upi: "UPI", paypal: t`PayPal`, wise: t`Wise`, cash: t`Cash`, cheque: t`Cheque`, other: t`Other`,
};

export function draftFrom(data: EventMoneySettingsRead): Draft {
  return { prize_tds_enabled: data.prize_tds_enabled, prize_tds_rate: data.prize_tds_rate,
    prize_tds_threshold: data.prize_tds_threshold, payee_templates: data.payee_templates.map(pairKey).sort() };
}

export function payloadFrom(draft: Draft, version: number): PatchedEventMoneySettingsInput {
  return { expected_version: version, prize_tds_enabled: draft.prize_tds_enabled, prize_tds_rate: draft.prize_tds_rate.trim(),
    prize_tds_threshold: draft.prize_tds_threshold.trim(), payee_templates: draft.payee_templates.map(key => key.split(":")) };
}

/** Hack-money (#181 G7, #180 G13): the space's own prize-tax proposal and accepted payee country/method pairs.
 *  Space Manager only. Prize tax is record only: nothing is filed or certified here. */
export function EventMoneySettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const key = ["event-money-settings", makerspaceId];
  const path = `/admin/makerspace/${makerspaceId}/event-money-settings`;
  const settings = useQuery({ queryKey: key, queryFn: () => staffRequest<EventMoneySettingsRead>(path), enabled: expanded });
  const [draft, setDraft] = useState<Draft | null>(null);
  useEffect(() => { if (settings.data) setDraft(draftFrom(settings.data)); }, [settings.data]);
  const save = useMutation({
    mutationFn: (body: PatchedEventMoneySettingsInput) => staffRequest<EventMoneySettingsRead>(path, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: data => client.setQueryData(key, data),
  });
  const data = settings.data;
  const dirty = Boolean(draft && data && JSON.stringify(draft) !== JSON.stringify(draftFrom(data)));
  const togglePair = (pair: string) => draft && setDraft({ ...draft, payee_templates: draft.payee_templates.includes(pair)
    ? draft.payee_templates.filter(item => item !== pair) : [...draft.payee_templates, pair].sort() });
  return <SettingsRow label={t`Event prizes: tax and payee options`} helper={t`How prize payouts propose tax, and where winners and reimbursed people can be paid.`}><div className="@container grid min-w-0 gap-4">
    <button className="desk-button mt-2" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{t`Configure prize tax and payees`}</button>
    {expanded ? <SettingsQueryState query={settings} resource="event money settings"><>
      {settings.error || save.error ? <p role="alert" className="text-danger">{(settings.error || save.error)?.message}</p> : null}
      {draft && data ? <form className="mt-3 grid gap-4" onSubmit={event => { event.preventDefault(); save.mutate(payloadFrom(draft, data.version)); }}>
        <fieldset className="grid gap-3"><legend className="font-semibold">{t`Prize tax (TDS)`}</legend>
          <label className="flex min-h-11 items-start gap-3">
            <input type="checkbox" className="mt-1" checked={draft.prize_tds_enabled} onChange={event => setDraft({ ...draft, prize_tds_enabled: event.target.checked })} />
            <span>{t`Record prize tax (TDS). SpaceWorks proposes the deduction on each prize payout; you deduct and file it yourself. No certificates or filing reports are produced.`}</span>
          </label>
          <Field label={t`Rate (%)`} hint={t`Default 30%.`}>
            <input className="desk-input min-h-11" inputMode="decimal" disabled={!draft.prize_tds_enabled} value={draft.prize_tds_rate}
              onChange={event => setDraft({ ...draft, prize_tds_rate: event.target.value })} /></Field>
          <Field label={t`Threshold (${data.currency.toUpperCase()})`} hint={t`A payout above this amount gets a proposed deduction. Default 10,000.`}>
            <input className="desk-input min-h-11" inputMode="decimal" disabled={!draft.prize_tds_enabled} value={draft.prize_tds_threshold}
              onChange={event => setDraft({ ...draft, prize_tds_threshold: event.target.value })} /></Field>
        </fieldset>
        <fieldset className="grid gap-2"><legend className="font-semibold">{t`Accepted payee options`}</legend>
          <p className="text-sm text-muted">{t`Choose where this space pays winners and reimbursed people. Leave every box empty to keep the deployment operator's setting.`}</p>
          {data.available_payee_templates.length ? <div className="grid gap-1 @md:grid-cols-2">
            {data.available_payee_templates.map(pair => { const id = pairKey(pair);
              return <label key={id} className="flex min-h-11 items-center gap-3">
                <input type="checkbox" checked={draft.payee_templates.includes(id)} onChange={() => togglePair(id)} />
                {pair[0]} · {METHOD_LABELS[pair[1]] ?? pair[1]}</label>; })}
          </div> : <p className="text-sm text-muted" role="status">{t`This deployment offers no payee options to choose from.`}</p>}
        </fieldset>
        <SettingsEditorActions dirty={dirty} onDiscard={() => setDraft(draftFrom(data))} pending={save.isPending} disabled={save.isPending} />
        {save.isSuccess ? <p role="status">{t`Prize tax and payee settings saved.`}</p> : null}
      </form> : null}
    </></SettingsQueryState> : null}
  </div></SettingsRow>;
}
