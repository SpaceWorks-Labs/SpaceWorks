import { t } from "@lingui/core/macro";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { useStaffGet } from "./panels/shared";

export type LoanPolicy = {
  id: number; default_loan_days: number; loan_renewal_mode: "off" | "auto";
  loan_max_renewals: number; loan_renewal_days: number; loan_max_active: number;
  loan_max_items: number; loan_reminder_offsets_hours: number[]; loan_escalate_overdue_days: number;
  /** Decision 221(a): account-only borrowers renew their own loans. Space Manager only. */
  account_self_renewal?: boolean;
};
const NUMBERS = [
  ["default_loan_days", t`Loan period in days`, 1, 365, null],
  ["loan_max_renewals", t`Maximum renewals`, 0, 100, "loans.renewals"],
  ["loan_renewal_days", t`Renewal length in days`, 1, 365, "loans.renewals"],
  ["loan_max_active", t`Maximum active loans (0 = unlimited)`, 0, undefined, "loans.limits"],
  ["loan_max_items", t`Maximum outstanding items (0 = unlimited)`, 0, undefined, "loans.limits"],
  ["loan_escalate_overdue_days", t`Escalate to staff after days overdue (0 = off)`, 0, 365, null],
] as const;

export function MakerspaceLoanPolicySettings({ makerspaceId, enabledFeatures, enabledModules = [], canManageMakerspace = false }: {
  makerspaceId: number; enabledFeatures: readonly string[];
  /** With `canManageMakerspace`, decides whether the account-only self-renewal switch shows (221a). */
  enabledModules?: readonly string[]; canManageMakerspace?: boolean;
}) {
  const client = useQueryClient();
  const key = ["staff", "loan-policy", makerspaceId];
  const path = `/admin/makerspace/${makerspaceId}/return-policy`;
  const query = useStaffGet<LoanPolicy>(key, path);
  const [form, setForm] = useState<LoanPolicy | null>(null);
  const [offsets, setOffsets] = useState("0");
  const [problem, setProblem] = useState("");
  useEffect(() => {
    if (query.data) {
      setForm(query.data);
      setOffsets(query.data.loan_reminder_offsets_hours.join(", "));
    }
  }, [query.data]);
  const save = useMutation({
    mutationFn: (value: LoanPolicy) => staffRequest<LoanPolicy>(path, { method: "PATCH", body: JSON.stringify(value) }),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: key }),
      client.invalidateQueries({ queryKey: ["makerspace-settings", makerspaceId] }),
      client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
    ]),
  });
  // Self-renewal only matters for account-only borrowers: member accounts on, membership off.
  const selfRenewal = canManageMakerspace && enabledFeatures.includes("loans.renewals")
    && enabledModules.includes("member_accounts") && !enabledModules.includes("membership");
  if (query.error) return <SettingsQueryState query={query} resource={t`loan policy`} />;
  if (!form) return <SettingsQueryState query={query} resource={t`loan policy`} />;
  return <SettingsQueryState query={query} resource={t`loan policy`}><SettingsRow label={t`Loan policy`} helper={t`Set loan periods and borrower reminders.`}><form className="@container mt-5 grid gap-3 rounded-md border border-line p-4" onSubmit={(event) => {
    event.preventDefault();
    const parts = offsets.trim() ? offsets.split(",").map((part) => part.trim()) : [];
    const numbers = parts.map(Number);
    if (parts.some((part) => !/^-?\d+$/.test(part)) || numbers.length > 100 || new Set(numbers).size !== numbers.length || numbers.some((n) => n < -8760 || n > 8760)) {
      setProblem(t`Use up to 100 unique whole-hour offsets between -8760 and 8760.`);
      return;
    }
    setProblem("");
    save.mutate({ ...form, loan_reminder_offsets_hours: numbers });
  }}>


    <div className="grid gap-3 @md:grid-cols-2">
      {NUMBERS.filter(([, , , , feature]) => !feature || enabledFeatures.includes(feature)).map(([field, label, min, max]) => <Field key={field} label={label}>
        <input className="desk-input" type="number" required min={min} max={max} step="1" value={form[field]} disabled={save.isPending} onChange={(event) => setForm({ ...form, [field]: Number(event.target.value) })} />
      </Field>)}
      {enabledFeatures.includes("loans.renewals") ? <Field label={t`Renewal mode`}><select className="desk-input max-w-full" value={form.loan_renewal_mode} disabled={save.isPending} onChange={(event) => setForm({ ...form, loan_renewal_mode: event.target.value as LoanPolicy["loan_renewal_mode"] })}>
        <option value="off">{t`Off`}</option><option value="auto">{t`Automatic within policy`}</option>
      </select></Field> : null}
      {selfRenewal && form.account_self_renewal !== undefined ? <label className="flex min-h-11 items-center gap-3 text-sm @md:col-span-2">
        <input className="h-5 w-5 accent-accent" role="switch" type="checkbox" checked={form.account_self_renewal} disabled={save.isPending}
          onChange={(event) => setForm({ ...form, account_self_renewal: event.target.checked })} />
        <span className="grid gap-0.5"><span className="font-semibold text-ink">{t`Borrowers renew their own loans`}</span>
          <span className="text-muted">{t`People with an account (no membership) can renew from their borrowing page, within the renewal rules above. Restricted accounts still cannot.`}</span></span>
      </label> : null}
      <Field label={t`Reminder offsets in hours`} hint={t`Negative = before due; 0 = due; positive = overdue. Leave empty to disable borrower reminders.`}>
        <input className="desk-input" value={offsets} disabled={save.isPending} onChange={(event) => setOffsets(event.target.value)} />
      </Field>
    </div>
    <div><SettingsEditorActions dirty={JSON.stringify(form) !== JSON.stringify(query.data) || offsets !== (query.data?.loan_reminder_offsets_hours.join(", ") ?? "0")} onDiscard={() => { setForm(query.data ?? null); setOffsets(query.data?.loan_reminder_offsets_hours.join(", ") ?? "0"); setProblem(""); }} pending={save.isPending} disabled={save.isPending} /></div>
    {problem || save.error ? <p className="text-sm text-danger" role="alert">{problem || save.error?.message}</p> : null}
    {save.isSuccess ? <p className="text-sm text-muted" role="status">{t`Loan policy saved.`}</p> : null}
  </form></SettingsRow></SettingsQueryState>;
}
