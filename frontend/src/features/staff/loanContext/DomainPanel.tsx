import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Choices, Participants } from "./Choices";
import { deleteContext, getContext, putContext, type Context, type Domain } from "./api";

export function DomainPanel({ tenant, request, domain, scope }: { tenant: number; request: number; domain: Domain; scope: string }) {
  const client = useQueryClient();
  const [intended, setIntended] = useState<number | undefined>();
  const [target, setTarget] = useState<number | undefined>();
  const [participant, setParticipant] = useState<number | null | undefined>(undefined);
  const [base, setBase] = useState<Context | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [needsReview, setNeedsReview] = useState(false);
  const [pending, setPending] = useState(false);
  const [denied, setDenied] = useState(false);
  const [message, setMessage] = useState("");
  const key = ["loan-context", scope, domain, intended ?? "discovery"] as const;
  const query = useQuery({ queryKey: key, queryFn: () => getContext(tenant, request, domain, intended), enabled: !denied, retry: false });
  const error = query.error as { status?: number; code?: string } | null;
  const blocked = query.isError && (Boolean(query.data) || error?.status === 403
    || ["module_disabled", "feature_disabled", "capability_disabled"].includes(error?.code ?? ""));
  useEffect(() => {
    if (!blocked) return;
    setDenied(true); setBase(null); setTarget(undefined); setParticipant(undefined);
    setIntended(undefined); setChoosing(false); setNeedsReview(false); setMessage("");
    client.removeQueries({ queryKey: ["loan-context", scope, domain] });
    client.removeQueries({ queryKey: ["loan-context-choices", scope] });
    client.removeQueries({ queryKey: ["loan-context-participants", scope] });
  }, [blocked, client, domain, scope]);
  const current = !query.isError ? query.data : undefined;
  const selected = current?.active ? domain === "event" ? current.event_id : current.booking_id : intended;
  const editAllowed = Boolean(current?.can_write);
  const currentMatchesBase = Boolean(base && current && base.generation === current.generation && base.revision === current.revision);
  const choose = (id: number) => {
    setTarget(id); setChoosing(false); setMessage("");
    if (!current?.active) { setBase(null); setIntended(id); }
    else { setBase(current); setParticipant(id === selected ? current.participant_registration_id ?? null : undefined); }
  };
  const review = () => { if (current) { setBase(current); setNeedsReview(false); setMessage(""); } };
  const mutate = async (remove: boolean) => {
    if (!base || !currentMatchesBase || !editAllowed || needsReview || pending) return;
    const id = remove ? selected : target;
    if (!remove && domain === "event" && participant === undefined) return;
    if (!id || !Number.isSafeInteger(id)) return;
    setPending(true); setMessage("");
    try {
      const next = remove ? await deleteContext(tenant, request, domain, id, base) : await putContext(tenant, request, domain, id, participant ?? null, base);
      client.setQueryData(key, next); setBase(null); setTarget(undefined); setNeedsReview(false);
      setMessage(remove ? t`Context removed.` : t`Context saved.`);
    } catch (caught) {
      const failure = caught as { status?: number; code?: string; message?: string };
      if (failure?.status === 401 || failure?.status === 403 || failure?.status === 404
          || ["module_disabled", "feature_disabled", "capability_disabled"].includes(failure?.code ?? "")) {
        // A known loss of access must conceal the entire editor before any reread.
        setDenied(true); setBase(null); setTarget(undefined); setParticipant(undefined);
        setIntended(undefined); setChoosing(false); setNeedsReview(false); setMessage("");
        client.removeQueries({ queryKey: ["loan-context", scope, domain] });
        client.removeQueries({ queryKey: ["loan-context-choices", scope] });
        client.removeQueries({ queryKey: ["loan-context-participants", scope] });
      } else if (failure?.status === 400) {
        setMessage(failure.message || t`Check the selected context and try again.`);
      } else {
        // Conflict, busy lock and unknown transport outcome require a fresh comparison.
        setNeedsReview(true); setMessage(t`The context may have changed. Review the latest state before trying again.`);
        await query.refetch();
      }
    } finally { setPending(false); }
  };
  if (denied) return <section className="grid gap-3 rounded-xl border border-line p-4" aria-label={domain === "event" ? t`Event context` : t`Booking context`}>
    <h3 className="title-section">{domain === "event" ? t`Event context` : t`Booking context`}</h3>
    <p role="status">{t`Context is unavailable for this access.`}</p>
  </section>;
  return <section className="grid gap-3 rounded-xl border border-line p-4" aria-label={domain === "event" ? t`Event context` : t`Booking context`}>
    <h3 className="title-section">{domain === "event" ? t`Event context` : t`Booking context`}</h3>
    {query.isPending ? <p role="status">{t`Loading context…`}</p> : query.isError ? <p role="status">{t`Context is unavailable for this access.`}</p> : current?.active ? <>
      {selected !== undefined ? <p>{domain === "event" ? t`Event #${selected}` : t`Booking #${selected}`}</p> : null}
      {domain === "event" && current.may_view_participant === false ? <p>{t`Participant details are unavailable for this access.`}</p> : null}
      {domain === "event" && !current.can_write ? <p>{t`Changes require the appropriate request and event registration permissions and an editable request.`}</p> : null}
      {domain === "event" && current.may_view_participant && current.participant_registration_id ? <p>{t`Participant #${current.participant_registration_id}`}</p> : null}
    </> : <p>{t`No linked context.`}</p>}
    {target && base && current ? <p>{domain === "event" ? t`Proposed event #${target}` : t`Proposed booking #${target}`}</p> : null}
    {message ? <p role="status">{message}</p> : null}
    {needsReview && current ? <button className="desk-button" type="button" onClick={review}>{t`Review latest state`}</button> : null}
    {!blocked && (!current?.active || editAllowed) && !pending ? <button className="desk-button w-fit" type="button" aria-expanded={choosing} onClick={() => setChoosing(!choosing)}>{t`Choose a different resource`}</button> : null}
    {choosing && !blocked ? <Choices tenant={tenant} domain={domain} scope={scope} onSelect={choose} /> : null}
    {target && current && !current.active && intended === target && !base && current.can_write ? <button className="desk-button" type="button" onClick={() => { setBase(current); setParticipant(undefined); }}>{t`Prepare link`}</button> : null}
    {target && base && editAllowed && domain === "event" ? <Participants key={`${scope}:${target}`} eventId={target} scope={scope} value={participant} onChange={setParticipant} /> : null}
    {target && base && editAllowed ? <button className="desk-button-brand" type="button" disabled={pending || needsReview || !currentMatchesBase || (domain === "event" && participant === undefined)} onClick={() => void mutate(false)}>{t`Save context`}</button> : null}
    {current?.active && editAllowed ? <button className="desk-button" type="button" disabled={pending || needsReview || !currentMatchesBase} onClick={() => void mutate(true)}>{t`Remove context`}</button> : null}
    {current?.active && editAllowed && !base ? <button className="desk-button" type="button" onClick={() => { setBase(current); setTarget(selected); setParticipant(current.participant_registration_id ?? null); }}>{t`Edit or remove`}</button> : null}
  </section>;
}
