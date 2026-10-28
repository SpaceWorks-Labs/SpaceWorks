import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Callout, ErrorText, Field, StatusPill } from "../../components/ui";
import { closePiiAccess, getPiiAccess, openPiiAccess, piiAccessKey, type PiiAccessGrant, type PiiAccessStatus } from "../../lib/api/piiAccess";

const time = (value: string) => new Date(value).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

/**
 * Personal data in a space is masked for a platform superadmin until they open a
 * 30-minute window with a reason. The superadmin opens and closes it here; the space's
 * Space Manager sees the same windows read-only, so the access is never invisible.
 */
export function PiiAccessBanner({ makerspaceId, compact = false }: { makerspaceId: number; compact?: boolean }) {
  const queryClient = useQueryClient();
  const key = piiAccessKey(makerspaceId);
  const status = useQuery({ queryKey: key, queryFn: () => getPiiAccess(makerspaceId), refetchInterval: 60_000 });
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const settle = (data: PiiAccessStatus) => {
    queryClient.setQueryData(key, data);
    // Masked responses are cached per query; reload everything this space shows.
    void queryClient.invalidateQueries({ predicate: query => query.queryKey[0] !== key[0] });
  };
  const open = useMutation({ mutationFn: () => openPiiAccess(makerspaceId, reason.trim()),
    onSuccess: data => { setReason(""); setAsking(false); settle(data); } });
  const close = useMutation({ mutationFn: () => closePiiAccess(makerspaceId), onSuccess: settle });

  if (!status.data) return status.error ? <ErrorText message="Couldn't load PII access. Try again." /> : null;
  const data = status.data;
  const submit = (event: FormEvent) => { event.preventDefault(); if (reason.trim().length >= 10) open.mutate(); };

  if (!data.viewer_is_superadmin) {
    return <div className="grid gap-3" aria-live="polite">
      {data.space_grants.length ? <>
        <Callout size="banner" tone="warn" lead="A platform administrator can see personal data in this space right now."
          body="Each window lasts at most 30 minutes and is recorded in your audit log." />
        <ul className="grid gap-2">{data.space_grants.map(grant => <li key={grant.id} className="text-sm text-ink">
          {grant.opened_by}, until {time(grant.expires_at)}. Reason: {grant.reason}</li>)}</ul>
      </> : <p className="text-sm text-muted">No platform administrator is viewing personal data here right now.</p>}
      {!compact && data.recent.length ? <RecentWindows grants={data.recent} /> : null}
    </div>;
  }
  if (data.active) {
    return <div className="grid gap-3" aria-live="polite">
      <Callout size="banner" tone="warn" lead={`Personal data is visible to you until ${time(data.active.expires_at)}.`}
        body={`Reason: ${data.active.reason}. This space's managers can see this in their audit log.`}
        action={{ label: "Close now", onClick: () => close.mutate(), pending: close.isPending, pendingLabel: "Closing…" }} />
      {close.error ? <ErrorText message={close.error.message} /> : null}
    </div>;
  }
  return <div className="grid gap-3" aria-live="polite">
    <Callout size="banner" tone="warn" lead="Personal data in this space is masked for you."
      body="Open a 30-minute window to see names, emails and phone numbers. It needs a reason and is recorded in the space's audit log."
      action={asking ? undefined : { label: "Open PII access", onClick: () => setAsking(true) }} />
    {asking ? <form className="grid gap-3" onSubmit={submit}>
      <Field label="Reason" hint="10 to 300 characters. The space's managers can read it.">
        <textarea className="min-h-20 rounded-lg border border-line bg-panel p-3 text-sm text-ink" value={reason}
          minLength={10} maxLength={300} required onChange={event => setReason(event.target.value)} />
      </Field>
      <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="submit" disabled={open.isPending || reason.trim().length < 10}>
          {open.isPending ? "Opening…" : "Open for 30 minutes"}</button>
        <button className="desk-button" type="button" onClick={() => { setAsking(false); setReason(""); }}>Cancel</button>
      </div>
      {open.error ? <ErrorText message={open.error.message} /> : null}
    </form> : null}
  </div>;
}

function RecentWindows({ grants }: { grants: PiiAccessGrant[] }) {
  return <div className="grid gap-2">
    <p className="text-sm font-semibold text-ink">Recent platform access</p>
    <ul className="grid gap-2">
      {grants.map(grant => <li key={grant.id} className="flex flex-wrap items-center gap-2 text-sm text-ink">
        <span>{new Date(grant.opened_at).toLocaleString()} · {grant.opened_by}: {grant.reason}</span>
        <StatusPill label={grant.closed_at ? (grant.close_reason === "expired" ? "Expired" : "Closed") : "Open"}
          tone={grant.closed_at ? "neutral" : "warn"} />
      </li>)}
    </ul>
  </div>;
}
