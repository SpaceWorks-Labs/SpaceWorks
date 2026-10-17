import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { staffRequest } from "../../lib/api";

type Billing = { number_prefix: string; bill_prefix: string; payment_instructions: string; legal_name: string; address: string; tax_id: string; footer: string; account_codes: Record<string, string> };

export function BillingDocumentsSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const key = ["billing-policy", makerspaceId];
  const path = `/admin/makerspace/${makerspaceId}/billing-settings`;
  const policy = useQuery({ queryKey: key, queryFn: () => staffRequest<Billing>(path), enabled: expanded });
  const [draft, setDraft] = useState<Billing | null>(null);
  const [codes, setCodes] = useState("");
  useEffect(() => { if (policy.data) { setDraft(policy.data); setCodes(JSON.stringify(policy.data.account_codes, null, 2)); } }, [policy.data]);
  const save = useMutation({
    mutationFn: () => {
      const account_codes: unknown = JSON.parse(codes);
      return staffRequest<Billing>(path, { method: "PATCH", body: JSON.stringify({
        number_prefix: draft?.number_prefix, bill_prefix: draft?.bill_prefix,
        payment_instructions: draft?.payment_instructions, legal_name: draft?.legal_name, address: draft?.address,
        tax_id: draft?.tax_id, footer: draft?.footer, account_codes,
      }) });
    },
    onSuccess: (data) => { client.setQueryData(key, data); void client.invalidateQueries({ queryKey: ["operations-report", "accounting-journal"] }); },
  });
  return <SettingsRow label="Billing documents and accounting" helper="Gross-only documents. Settings apply to newly issued bills, receipts and credit notes."><div className="@container grid min-w-0 gap-4">


    <button className="desk-button mt-2" type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>Configure documents</button>
    {expanded ? <SettingsQueryState query={policy} resource="receipt settings"><>
      {policy.isLoading ? <p>Loading billing settings…</p> : null}
      {policy.error || save.error ? <p role="alert" className="text-danger">{(policy.error || save.error)?.message}</p> : null}
      {draft ? <form className="mt-3 grid gap-3" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
        {([ ["number_prefix", "Number prefix", 32], ["bill_prefix", "Bill prefix", 32], ["legal_name", "Issuer name", 150], ["address", "Issuer address", 1000], ["tax_id", "Issuer identifier (no tax calculation)", 64], ["footer", "Footer", 1000] ] as const).map(([name, label, length]) =>
          <Field key={name} label={label}><input className="desk-input" maxLength={length} value={draft[name]} onChange={(event) => setDraft({ ...draft, [name]: event.target.value })} /></Field>)}
        <Field label="Payment instructions"><textarea className="desk-input" rows={4} maxLength={2000} value={draft.payment_instructions} onChange={event => setDraft({ ...draft, payment_instructions: event.target.value })} /></Field>
        <Field label="Accounting account codes (JSON)"><textarea className="desk-input code-text" rows={6} value={codes} onChange={(event) => setCodes(event.target.value)} /></Field>
        <p className="text-xs text-muted">Defaults: income 4000, cash 1000, online 1010, loan-deposit liability 2100. Override individual payment subject types as needed.</p>
        <SettingsEditorActions dirty={Boolean(draft && policy.data && (JSON.stringify(draft) !== JSON.stringify(policy.data) || codes !== JSON.stringify(policy.data.account_codes, null, 2)))} onDiscard={() => { setDraft(policy.data ?? null); setCodes(JSON.stringify(policy.data?.account_codes ?? {}, null, 2)); }} pending={save.isPending} disabled={save.isPending} />
        {save.isSuccess ? <p role="status">Document settings saved.</p> : null}
      </form> : null}
    </></SettingsQueryState> : null}
  </div></SettingsRow>;
}
