import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText, operationId } from "../../guestPasses/api";
import { communityKeys, communityMemberApi, type Dependent, type GuardianTerms } from "../api";

/**
 * Guardian consent e-signature (decision 223 k): for each minor who names THIS account as guardian,
 * read the current text, tick to accept and type your full name. Renders nothing for anyone who is
 * nobody's guardian, or when the feature is off.
 */
export function GuardianConsentPanel({ makerspaceId }: { makerspaceId: number }) {
  const page = useQuery({ queryKey: communityKeys.guardian(makerspaceId), queryFn: () => communityMemberApi.guardian(makerspaceId), retry: false });
  if (page.isLoading) return <p role="status" className="text-sm text-muted">{t`Loading guardian consent…`}</p>;
  if (page.isError || !page.data?.dependents.length) return null;
  return <section aria-labelledby="guardian-consent-title" className="desk-panel grid gap-4 p-5">
    <div><h2 id="guardian-consent-title" className="title-panel">{t`Guardian consent`}</h2>
      <p className="mt-1 text-sm text-muted">{t`You are named as the parent or guardian of the people below. They can take part once your consent is current.`}</p></div>
    {page.data.terms ? null : <p className="text-sm text-warn-ink">{t`The space hasn't published its consent text yet, so there is nothing to sign. Ask space staff.`}</p>}
    <ul className="grid gap-4">
      {page.data.dependents.map((dependent) => <DependentCard key={dependent.profile_id} makerspaceId={makerspaceId} dependent={dependent} terms={page.data.terms} />)}
    </ul>
  </section>;
}

function DependentCard({ makerspaceId, dependent, terms }: { makerspaceId: number; dependent: Dependent; terms: GuardianTerms | null }) {
  const client = useQueryClient();
  const [signing, setSigning] = useState(false);
  const [name, setName] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [key] = useState(operationId);
  const refresh = () => client.invalidateQueries({ queryKey: communityKeys.guardian(makerspaceId) });
  const sign = useMutation({
    mutationFn: () => communityMemberApi.sign(makerspaceId, dependent.profile_id, { signed_name: name.trim(), accepted: true, operation_id: key }),
    onSuccess: () => { setSigning(false); setName(""); setAccepted(false); void refresh(); },
  });
  const revoke = useMutation({ mutationFn: () => communityMemberApi.revoke(makerspaceId, dependent.profile_id), onSuccess: refresh });
  const valid = dependent.consent_state === "valid";
  return <li className="grid gap-3 rounded-2xl border border-line p-4">
    <div className="flex flex-wrap items-center gap-2">
      <p className="title-section">{dependent.dependent_name}</p>
      <StatusPill tone={valid ? "success" : "warn"} label={valid && dependent.consent_valid_until ? t`Consent until ${formatDate(dependent.consent_valid_until)}` : valid ? t`Consent on file` : t`Consent needed`} />
    </div>
    <div className="flex flex-wrap gap-2">
      {terms ? <button type="button" className={valid ? "desk-button min-h-11" : "desk-button-brand min-h-11"} aria-expanded={signing} onClick={() => setSigning((value) => !value)}>
        {valid ? t`Sign again` : t`Read and sign`}</button> : null}
      {valid ? <button type="button" className="desk-button-ghost min-h-11" disabled={revoke.isPending} onClick={() => revoke.mutate()}>{t`Withdraw consent`}</button> : null}
    </div>
    {signing && terms ? <form className="grid gap-3" aria-label={t`Sign consent for ${dependent.dependent_name}`} onSubmit={(event) => { event.preventDefault(); if (accepted && name.trim()) sign.mutate(); }}>
      <p className="text-xs font-semibold uppercase text-muted">{t`Consent text, version ${terms.version}`}</p>
      <div className="max-h-72 overflow-y-auto whitespace-pre-wrap break-words rounded-control border border-line p-3 text-sm text-ink" tabIndex={0}>{terms.body}</div>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
        {t`I have read this and give my consent as ${dependent.dependent_name}'s parent or guardian`}</label>
      <Field label={t`Type your full name to sign`}><input className="desk-input" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} /></Field>
      <div><button type="submit" className="desk-button-brand min-h-11" disabled={!accepted || !name.trim() || sign.isPending}>{sign.isPending ? t`Signing…` : t`Sign consent`}</button></div>
    </form> : null}
    {sign.error || revoke.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(sign.error ?? revoke.error)}</p> : null}
    {dependent.consents.length ? <details className="text-sm"><summary className="cursor-pointer text-muted">{t`Consent history`}</summary>
      <ul className="mt-2 grid gap-1 text-muted">{dependent.consents.map((consent) => <li key={consent.id}>
        {t`Version ${consent.terms_version}, signed ${formatDate(consent.signed_at)}`}{consent.revoked_at ? ` · ${t`withdrawn ${formatDate(consent.revoked_at)}`}` : ` · ${t`valid until ${formatDate(consent.valid_until)}`}`}
      </li>)}</ul></details> : null}
  </li>;
}
