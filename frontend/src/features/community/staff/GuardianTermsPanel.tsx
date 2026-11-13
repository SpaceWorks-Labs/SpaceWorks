import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { guestErrorText } from "../../guestPasses/api";
import { communityKeys, communityStaffApi } from "../api";
import { LogoLoader } from "../../../components/LogoLoader";

/**
 * The guardian-consent text, versioned like a waiver. Publishing a new version keeps the old one
 * and asks guardians to sign again (manage_makerspace on the server; read for manage_members).
 */
export function GuardianTermsPanel({ makerspaceId, canPublish }: { makerspaceId: number; canPublish: boolean }) {
  const client = useQueryClient();
  const terms = useQuery({ queryKey: communityKeys.terms(makerspaceId), queryFn: () => communityStaffApi.terms(makerspaceId) });
  const [version, setVersion] = useState("");
  const [body, setBody] = useState("");
  const publish = useMutation({
    mutationFn: () => communityStaffApi.publishTerms(makerspaceId, { version: version.trim(), body: body.trim() }),
    onSuccess: () => { setVersion(""); setBody(""); void client.invalidateQueries({ queryKey: communityKeys.all(makerspaceId) }); },
  });
  const active = terms.data?.find((row) => row.is_active);
  return <section aria-labelledby="guardian-terms-title" className="grid gap-3 rounded-2xl border border-line p-4">
    <h3 id="guardian-terms-title" className="title-section">{t`Guardian consent text`}</h3>
    {terms.isLoading ? <LogoLoader label={t`Loading consent text…`} size={48} className="min-h-16 py-3" /> : null}
    {terms.isError ? <p role="alert" className="text-sm text-danger">{guestErrorText(terms.error)}</p> : null}
    {terms.isSuccess && !active ? <p className="text-sm text-warn-ink">{t`No consent text is published, so no guardian can sign yet.`}</p> : null}
    {active ? <div className="grid gap-2">
      <p className="flex flex-wrap items-center gap-2 text-sm"><StatusPill tone="success" label={t`Current`} />{t`Version ${active.version}, published ${formatDate(active.created_at)}`}</p>
      <p className="max-w-prose whitespace-pre-wrap break-words text-sm text-muted">{active.body}</p>
    </div> : null}
    {canPublish ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (version.trim() && body.trim()) publish.mutate(); }}>
      <Field label={t`New version name`} hint={t`For example 2026-11. Guardians will be asked to sign the new text.`}>
        <input className="desk-input" maxLength={64} value={version} onChange={(event) => setVersion(event.target.value)} /></Field>
      <Field label={t`Consent text`}><textarea className="desk-input min-h-32" maxLength={20000} value={body} onChange={(event) => setBody(event.target.value)} /></Field>
      <div><button type="submit" className="desk-button-primary min-h-11" disabled={!version.trim() || !body.trim() || publish.isPending}>{publish.isPending ? t`Publishing…` : t`Publish consent text`}</button></div>
      {publish.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(publish.error)}</p> : null}
    </form> : <p className="text-sm text-muted">{t`A Space Manager publishes new consent text.`}</p>}
  </section>;
}
