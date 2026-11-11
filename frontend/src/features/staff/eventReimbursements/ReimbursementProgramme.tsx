import { t } from "@lingui/core/macro";
import { formatMinorMoney } from "../../../lib/money";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { useUnsavedChanges } from "../../events/stagedForms/UnsavedChanges";
import { reimbursementAdminPath, useProgramme, useProgrammeCommand } from "./api";
import { PolicyFields } from "./PolicyFields";
import { MinorAmountInput } from "../../forms/MinorAmountInput";
import { CrewPoolPanel } from "./TravelAndCrewPool";
import type { ProgrammeDetail } from "./types";
import { ReasonSelect } from "./reasonCodes";
export function ReimbursementProgramme({ scope, onDirtyChange }: { scope: EventScope; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useProgramme(scope);
  if (!query.data) return <div><p role={query.error ? "alert" : "status"}>{query.error ? commandError(query.error) : t`Loading reimbursement programme…`}</p>
    {query.error ? <button type="button" className="desk-button" onClick={() => void query.refetch()}>{t`Retry`}</button> : null}</div>;
  return <div className="grid gap-6"><ProgrammeEditor key={query.data.version ?? 0} scope={scope} row={query.data} onDirtyChange={onDirtyChange} />
    <CrewPoolPanel scope={scope} /></div>;
}
function ProgrammeEditor({ scope, row, onDirtyChange }: { scope: EventScope; row: ProgrammeDetail; onDirtyChange?: (dirty: boolean) => void }) {
  const [currency, setCurrency] = useState(row.currency ?? "INR");
  const [initialTotal, setInitialTotal] = useState(Number.NaN);
  const [due, setDue] = useState("");
  const [settings, setSettings] = useState(row.settings);
  const [delta, setDelta] = useState(0);
  const [reason, setReason] = useState("");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const mutation = useProgrammeCommand(scope);
  useUnsavedChanges(dirty, onDirtyChange);
  const allowed = row.allowed_actions.includes(row.initialized ? "programme_edit" : "programme_initialize");
  return <FormPageLayout header={{ title: row.initialized ? t`Reimbursement policy and budget` : t`Set up reimbursement support` }} state={{ status: "ready" }}
    submit={{ label: row.initialized ? t`Save policy and budget` : t`Create programme and initial pool`, pending: mutation.isPending, disabled: !allowed,
      disabledReason: t`Finance permission and a verified session are required.`, onClick: () => {
        try {
          setError("");
          if (row.initialized && row.pool && settings && row.version && row.policy_revision) mutation.mutate({ path: `${reimbursementAdminPath(scope)}programme/`, method: "PATCH", body: {
            expected_version: row.version, policy_revision: row.policy_revision, pool_id: row.pool.id, expected_pool_version: row.pool.version,
            budget_delta_minor: delta, reason_code: reason, settings,
          } }, { onSuccess: () => setDirty(false) });
          else if (!row.initialized) mutation.mutate({ path: `${reimbursementAdminPath(scope)}programme/`, body: { expected_version: 0, currency,
            initial_total_minor: initialTotal, initial_settings: { enabled: false, claim_due_at: utcInstant(due) } } }, { onSuccess: () => setDirty(false) });
        } catch { setError(t`Enter a valid claim deadline.`); }
      } }} form={<div className="grid gap-5"><p>{t`Finance sets a finite pool. Award offers reserve funds; accepted caps remain fixed. This programme records reimbursements and amounts owed.`}</p>
      {row.pool ? <p>{t`Pool: total ${formatMinorMoney(row.pool.total_minor, row.pool.currency)}; available ${formatMinorMoney(row.pool.available_minor, row.pool.currency)}; reserved ${formatMinorMoney(row.pool.reserved_minor, row.pool.currency)}; committed ${formatMinorMoney(row.pool.committed_minor, row.pool.currency)}.`}</p> : null}
      <fieldset disabled={!allowed || mutation.isPending} className="grid min-w-0 gap-4"><legend className="sr-only">{t`Programme settings`}</legend>
        {!row.initialized ? <><p>{t`The programme starts disabled. Configure and enable it after setup.`}</p>
          <Field label={t`Pool currency`}><input className="desk-input" required pattern="[A-Z]{3}" maxLength={3} value={currency} onChange={event => { setCurrency(event.target.value.toUpperCase()); setDirty(true); }} /></Field>
          <Field label={t`Initial total (${currency})`}><MinorAmountInput required currency={currency} value={initialTotal} onChange={minor => { setInitialTotal(minor ?? Number.NaN); setDirty(true); }} /></Field>
          <Field label={t`Claim deadline (your local time)`}><input className="desk-input" type="datetime-local" required value={due} onChange={event => { setDue(event.target.value); setDirty(true); }} /></Field></> : settings ? <>
          <PolicyFields currency={row.pool?.currency ?? currency} value={settings} onChange={next => { setSettings(next); setDirty(true); }} />
          <Field label={t`Budget adjustment (${row.pool?.currency ?? currency})`} hint={t`Positive adds funds; negative (for example -25.00) removes uncommitted funds.`}><MinorAmountInput required allowNegative currency={row.pool?.currency ?? currency} value={delta} onChange={minor => { setDelta(minor ?? Number.NaN); setDirty(true); }} /></Field>
          <Field label={t`Reason for this change`}><ReasonSelect value={reason} onChange={code => { setReason(code); setDirty(true); }} /></Field></> : <p role="alert">{t`Policy settings are unavailable. Reload before editing.`}</p>}
      </fieldset>{dirty ? <p role="status">{t`You have unsaved policy changes.`}</p> : null}
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : mutation.isSuccess ? <p role="status">{t`Programme saved.`}</p> : null}
    </div>} />;
}
