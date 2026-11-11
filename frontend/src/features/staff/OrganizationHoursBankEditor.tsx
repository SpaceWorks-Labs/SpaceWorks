import { t } from "@lingui/core/macro";
import { useEffect, useState, type FormEvent } from "react";

import { Field, PagePager } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { OrganizationHoursLedgerTable, minutesToHours } from "./OrganizationHoursLedgerTable";
import {
  useOrganizationHoursBank, useOrganizationHoursLedger, useOrganizationHoursWrites, type HoursPeriod,
} from "./organizationHoursApi";

const MAX_HOURS = 100000;
const toMinutes = (hours: string) => Math.round(Number(hours) * 60);
const validHours = (hours: string) => hours.trim() !== "" && Number.isFinite(Number(hours));

/**
 * Open item B13: the staff editor of an organization's hours bank at one space. Bookings made for the
 * organization use these hours first and only the remainder is charged. Staff set the allowance (and whether it
 * resets monthly or yearly), grant or adjust hours with a reason, and read the append-only ledger.
 */
export function OrganizationHoursBankEditor({ makerspaceId, organizationId }: { makerspaceId: number; organizationId: number }) {
  const bank = useOrganizationHoursBank(makerspaceId, organizationId);
  const [page, setPage] = useState(1);
  const ledger = useOrganizationHoursLedger(makerspaceId, organizationId, page);
  const { saveAllowance, adjust } = useOrganizationHoursWrites(makerspaceId, organizationId);
  const [hours, setHours] = useState("0");
  const [period, setPeriod] = useState<HoursPeriod>("none");
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (bank.data) { setHours(String(bank.data.allowance_minutes / 60)); setPeriod(bank.data.period); }
  }, [bank.data]);
  useEffect(() => setPage(1), [organizationId, makerspaceId]);
  if (bank.isPending) return <p role="status" className="text-sm text-muted">{t`Loading hours bank…`}</p>;
  if (bank.isError) return <p role="alert" className="text-sm text-danger">{t`The hours bank is unavailable for this organization.`}</p>;
  const data = bank.data;
  const allowanceReady = validHours(hours) && Number(hours) >= 0 && Number(hours) <= MAX_HOURS;
  const adjustReady = validHours(delta) && toMinutes(delta) !== 0 && reason.trim().length > 0;
  const saveSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (allowanceReady) saveAllowance.mutate({ allowance_minutes: toMinutes(hours), period });
  };
  const adjustSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!adjustReady) return;
    const minutes = toMinutes(delta);
    adjust.mutate({ entry: minutes > 0 ? "grant" : "adjust", minutes, reason: reason.trim() },
      { onSuccess: () => { setDelta(""); setReason(""); setPage(1); } });
  };
  const left = minutesToHours(data.remaining_minutes);
  const pool = minutesToHours(data.pool_minutes);
  return <section aria-labelledby="org-hours-title" className="mb-4 grid gap-3 rounded-lg border border-line p-3">
    <h4 id="org-hours-title" className="title-section">{t`Organization hours bank`}</h4>
    <p className="text-xs text-muted">{t`Bookings made for this organization use these hours first; only the rest is charged. Cancelling returns the hours.`}</p>
    <p role="status" className="text-sm">
      {data.configured ? <><span className="tabular-nums">{t`${left} h left of ${pool} h`}</span>
        {data.period_ends_at ? <span className="text-muted">{t` · resets ${formatDate(data.period_ends_at)}`}</span> : null}</>
        : t`No allowance set yet, so bookings for this organization use no included hours.`}
    </p>
    <form className="grid gap-3 sm:grid-cols-3" onSubmit={saveSubmit}>
      <Field label={t`Allowance (hours per period)`}>
        <input className="desk-input" type="number" inputMode="decimal" min={0} max={MAX_HOURS} step="any" value={hours}
          onChange={event => setHours(event.target.value)} /></Field>
      <Field label={t`Resets`}>
        <select className="desk-input" value={period} onChange={event => setPeriod(event.target.value as HoursPeriod)}>
          <option value="none">{t`Never (one pool)`}</option>
          <option value="monthly">{t`Every calendar month`}</option>
          <option value="yearly">{t`Every calendar year`}</option>
        </select></Field>
      <div className="flex items-end">
        <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!allowanceReady || saveAllowance.isPending}>
          {saveAllowance.isPending ? t`Saving…` : t`Save allowance`}</button></div>
      {saveAllowance.error ? <p role="alert" className="text-sm text-danger sm:col-span-3">{saveAllowance.error.message}</p> : null}
    </form>
    {data.configured ? <form className="grid gap-3 sm:grid-cols-3" onSubmit={adjustSubmit}>
      <Field label={t`Grant or adjust (hours, negative to remove)`}>
        <input className="desk-input" type="number" inputMode="decimal" step="any" value={delta}
          onChange={event => setDelta(event.target.value)} /></Field>
      <Field label={t`Reason`}>
        <input className="desk-input" maxLength={500} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <div className="flex items-end">
        <button type="submit" className="desk-button w-full sm:w-fit" disabled={!adjustReady || adjust.isPending}>
          {adjust.isPending ? t`Saving…` : t`Add to ledger`}</button></div>
      {adjust.error ? <p role="alert" className="text-sm text-danger sm:col-span-3">{adjust.error.message}</p> : null}
    </form> : null}
    <h5 className="text-sm font-semibold">{t`Ledger`}</h5>
    {ledger.isError ? <p role="alert" className="text-sm text-danger">{t`The ledger could not be loaded.`}</p> : null}
    {ledger.data ? <OrganizationHoursLedgerTable rows={ledger.data.results} showActor /> : null}
    {ledger.data ? <PagePager page={page} setPage={setPage} next={ledger.data.next} /> : null}
  </section>;
}
