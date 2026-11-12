import { t } from "@lingui/core/macro";
import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest, StructuredApiError, tenantMemberRequest } from "../../lib/api";
import type { EventEligibility } from "./OrganizationEventAdmission";
import { BoxArt } from "../../components/BoxSpinner";

/** Renew only the owned registration's consent; admission and saved answers stay intact. */
export function EventConsentRepairForm({ makerspaceSlug, publicToken, waiver, onRepaired, partner }: {
  makerspaceSlug: string; publicToken: string;
  waiver: NonNullable<EventEligibility["host_waiver"]>; onRepaired: () => void;
  partner?: { makerspaceId: number; eventId: number; slug: string };
}) {
  const client = useQueryClient();
  const [accepted, setAccepted] = useState(false);
  const [validation, setValidation] = useState("");
  useEffect(() => { setAccepted(false); setValidation(""); }, [waiver.id, waiver.version]);
  const repair = useMutation({
    mutationFn: () => {
      const options = { method: "POST", body: JSON.stringify({ host_waiver_id: waiver.id,
        host_waiver_version: waiver.version, host_waiver_accepted: accepted }) };
      return partner ? staffRequest(
        `/member/makerspaces/${partner.makerspaceId}/collaborative-events/${partner.eventId}/register/`, options,
      ) : tenantMemberRequest(makerspaceSlug,
        `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(publicToken)}/register/`, options);
    },
    onError: async error => {
      if (error instanceof StructuredApiError && error.code === "host_waiver_required") {
        setAccepted(false);
        await client.invalidateQueries({ queryKey: ["event-organization-eligibility", makerspaceSlug, publicToken] });
        if (partner) await client.invalidateQueries({ queryKey: ["member", partner.slug, "partner-events"] });
      }
    },
    onSuccess: async () => {
      onRepaired();
      await Promise.all([
        client.invalidateQueries({ queryKey: ["event-organization-eligibility", makerspaceSlug, publicToken] }),
        client.invalidateQueries({ queryKey: ["member", partner?.slug ?? makerspaceSlug, "activity"] }),
        ...(partner ? [client.invalidateQueries({ queryKey: ["member", partner.slug, "partner-events"] })] : []),
      ]);
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!accepted) { setValidation("Accept the current host waiver."); return; }
    setValidation("");
    if (!repair.isPending) repair.mutate();
  };
  return <form className="grid gap-4" onSubmit={submit}>
    <div><h3 className="title-section">{t`Renew registration consent`}</h3>
      <p className="mt-1 text-sm text-muted">{t`Your existing registration keeps its place and saved answers.`}</p></div>
    <fieldset className="grid gap-2 rounded-xl border border-line bg-panel p-3"><legend className="px-1 text-sm font-semibold">{t`Host waiver`}</legend>
      <p className="whitespace-pre-wrap text-sm leading-6">{waiver.body}</p>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={accepted}
        disabled={repair.isPending} onChange={e => setAccepted(e.target.checked)} />
        {t`I accept this host waiver (version ${waiver.version}).`}</label>
      {validation ? <p role="alert" className="text-sm text-danger">{validation}</p> : null}
    </fieldset>
    {repair.error ? <p role="alert" className="text-sm text-danger">{repair.error instanceof StructuredApiError
      ? repair.error.detail ?? repair.error.message : t`Unable to renew consent. Please try again.`}</p> : null}
    <button className="desk-button-brand w-full sm:w-auto sm:justify-self-start" type="submit" disabled={repair.isPending}>
      {repair.isPending ? <><BoxArt size={16} mono />{t`Saving consent...`}</> : t`Save consent`}
    </button>
  </form>;
}
