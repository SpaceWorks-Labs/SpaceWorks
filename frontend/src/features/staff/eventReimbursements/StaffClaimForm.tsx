import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Field, SegmentedControl } from "../../../components/ui";
import { staffRequest, StructuredApiError } from "../../../lib/api";
import { formatMinorMoney } from "../../../lib/money";
import { travelCategoryLabel } from "../../events/reimbursements/labels";
import { commandError, usePrivateCommand, type EventScope } from "../../events/stagedForms/privateQueries";
import { MinorAmountInput } from "../../forms/MinorAmountInput";
import { reimbursementAdminKey, reimbursementAdminPath, useProgramme } from "./api";
import { BoxArt } from "../../../components/BoxSpinner";
import { SearchField } from "../../../components/ui/SearchField";

/** POST …/reimbursements/staff-claims/ (parity C17); `operation_id` and the Idempotency-Key come from the shared command hook. */
type StaffClaimCommand = { expected_version: 0; beneficiary_registration_id?: number; category: string;
  amount_minor: number; currency: string; note?: string };
type Registration = { id: number; name?: string; status?: string };
const LIVE = new Set(["registered", "attended"]);

export function staffClaimError(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.code === "budget_exhausted") return t`The event's reimbursement pool cannot cover this amount. Lower it, or add budget first.`;
    if (error.code === "staff_claim_registration_required") return t`That person needs a live registration on this event before a claim can be filed for them.`;
    if (error.code === "reimbursement_request_exists") return t`This person already has a support request on this event. Review that request instead.`;
    if (error.code === "reimbursement_unavailable") return t`Travel support is not open on this event.`;
    if (error.code === "pool_currency_mismatch") return t`Claims must be in the pool's currency.`;
  }
  return commandError(error);
}

/**
 * Staff file an expense claim for themselves or on behalf of a speaker or volunteer (switch `events.staff_claims`).
 * It becomes an ordinary request funded from the event's pool, so the pool is the cap and review works as usual.
 */
export function StaffClaimForm({ scope, onFiled }: { scope: EventScope; onFiled: () => void }) {
  const programme = useProgramme(scope);
  const command = usePrivateCommand<StaffClaimCommand>(reimbursementAdminKey(scope), true);
  const [who, setWho] = useState<"self" | "other">("self");
  const [search, setSearch] = useState("");
  const [beneficiary, setBeneficiary] = useState("");
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const registrations = useQuery({ enabled: who === "other", retry: false,
    queryKey: ["staff-claim-registrations", scope.eventId, search],
    queryFn: () => staffRequest<{ results: Registration[] }>(`/admin/events/${scope.eventId}/registrations/?${new URLSearchParams({ page: "1", ...(search.trim() ? { q: search.trim() } : {}) })}`) });
  const currency = programme.data?.currency ?? "";
  const categories = programme.data?.settings?.allowed_categories ?? [];
  if (programme.isPending) return <LogoLoader label={t`Loading the reimbursement programme…`} />;
  if (!programme.data?.initialized) return <p className="text-sm text-muted">{t`Set up the reimbursement programme and its budget before filing claims.`}</p>;
  const people = (registrations.data?.results ?? []).filter(row => !row.status || LIVE.has(row.status));
  // Staff claims draw on the crew pool when the event has one, else the participants' pool (server rule).
  const pool = programme.data.pools?.find(item => item.audience === "crew") ?? programme.data.pool;
  const ready = Boolean(category && amount && amount > 0 && (who === "self" || beneficiary));
  return <form className="grid gap-4 rounded-2xl border border-line bg-panel p-5" aria-label={t`File an expense claim`}
    onSubmit={event => { event.preventDefault(); if (!ready || amount === null) return;
      command.mutate({ path: `${reimbursementAdminPath(scope)}staff-claims/`, body: { expected_version: 0, category, amount_minor: amount, currency,
        ...(who === "other" ? { beneficiary_registration_id: Number(beneficiary) } : {}), ...(note.trim() ? { note: note.trim() } : {}) } },
        { onSuccess: onFiled }); }}>
    <div className="grid gap-1"><h2 className="title-section">{t`File an expense claim`}</h2>
      <p className="text-sm text-muted">{t`Paid from this event's reimbursement pool, then reviewed like any other request.`}
        {pool ? ` ${t`Available now: ${formatMinorMoney(pool.available_minor, currency)}.`}` : ""}</p></div>
    <fieldset disabled={command.isPending} className="grid gap-4"><legend className="sr-only">{t`Claim details`}</legend>
      <SegmentedControl label={t`Claim for`} value={who} onChange={value => { setWho(value as typeof who); setBeneficiary(""); }}
        options={[{ value: "self", label: t`Myself` }, { value: "other", label: t`A speaker or volunteer` }]} />
      {who === "self" ? <p className="text-sm text-muted">{t`You need your own registration on this event.`}</p> : <>
        <Field label={t`Find the person`}><SearchField className="desk-input" value={search} onChange={event => setSearch(event.target.value)} placeholder={t`Name or email`} /></Field>
        <Field label={t`Person`} error={registrations.isError ? t`Registrations could not be loaded for your access.` : undefined}>
          <select className="desk-input" required value={beneficiary} onChange={event => setBeneficiary(event.target.value)}>
            <option value="">{registrations.isLoading ? t`Loading…` : people.length ? t`Choose a registered person` : t`No registered person matches`}</option>
            {people.map(row => <option key={row.id} value={row.id}>{row.name || t`Registration #${row.id}`}</option>)}
          </select></Field></>}
      <Field label={t`Category`}><select className="desk-input" required value={category} onChange={event => setCategory(event.target.value)}>
        <option value="">{t`Choose a category`}</option>
        {categories.map(value => <option key={value} value={value}>{travelCategoryLabel(value)}</option>)}</select></Field>
      <Field label={t`Amount (${currency.toUpperCase()})`}><MinorAmountInput className="desk-input" required currency={currency} value={amount} onChange={setAmount} /></Field>
      <Field label={t`Note for the reviewer (optional)`}><textarea className="desk-input min-h-20" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></Field>
      <button type="submit" className="desk-button-primary justify-self-start" disabled={!ready}>{command.isPending ? <><BoxArt size={16} mono />{t`Filing…`}</> : t`File claim`}</button>
    </fieldset>
    {command.error ? <p role="alert" className="text-sm text-danger">{staffClaimError(command.error)}</p> : null}
  </form>;
}
