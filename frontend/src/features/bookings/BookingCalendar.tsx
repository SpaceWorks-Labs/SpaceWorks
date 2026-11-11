import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { onSessionCleared, type SessionContext } from "../../lib/api/sessionContext";
import { useIntakeScope } from "../inventory/useIntakeScope";

export function BookingCalendar({ slug }: { slug: string }) {
  const { context, owner } = useIntakeScope();
  const [revision, setRevision] = useState(0);
  useEffect(() => onSessionCleared(changed => {
    if (changed === context && getSessionOwner(context) !== owner) setRevision(value => value + 1);
  }), [context, owner]);
  if (!owner) return null;
  return <CalendarScope key={JSON.stringify([context, owner, slug, revision])} slug={slug} context={context} owner={owner} />;
}

function CalendarScope({ slug, context, owner }: { slug: string; context: SessionContext; owner: string }) {
  const [url, setUrl] = useState("");
  const [retired, setRetired] = useState(false);
  const retiredRef = useRef(false);
  const mounted = useRef(false);
  const path = `/public/${encodeURIComponent(slug)}/my-bookings/calendar/`;
  const key = ["member", slug, "booking-calendar", context, owner];
  const client = useQueryClient();
  const admitted = () => !retiredRef.current && getSessionOwner(context) === owner;
  useEffect(() => {
    mounted.current = true;
    const unsubscribe = onSessionCleared(changed => {
      if (changed === context && getSessionOwner(context) !== owner) {
        retiredRef.current = true;
        setRetired(true);
      }
    });
    return () => { mounted.current = false; unsubscribe(); };
  }, [context, owner]);
  const state = useQuery({ queryKey: key, queryFn: () => memberRequest<{ enabled: boolean }>(path), enabled: !retired && admitted(), retry: false });
  const issue = useMutation({ mutationFn: () => {
    if (!admitted()) throw new Error(t`Sign in again to manage your calendar.`);
    return memberRequest<{ feed_url: string }>(path, { method: "POST" });
  }, onSuccess: result => {
    if (!mounted.current || !admitted()) return;
    setUrl(result.feed_url); void client.invalidateQueries({ queryKey: key });
  } });
  const revoke = useMutation({ mutationFn: () => {
    if (!admitted()) throw new Error(t`Sign in again to manage your calendar.`);
    return memberRequest<void>(path, { method: "DELETE" });
  }, onSuccess: () => {
    if (!mounted.current || !admitted()) return;
    setUrl(""); void client.invalidateQueries({ queryKey: key });
  } });
  const denied = [state.error, issue.error, revoke.error].some(error => [401, 403, 404].includes((error as { status?: number } | null)?.status ?? 0));
  if (retired || !admitted() || denied) return null;
  return <div className="mt-3 rounded-lg border border-line p-3">
    <p className="text-sm text-muted">{t`Subscribe to your own bookings. Keep the calendar link private; rotating it disables the previous link.`}</p>
    <div className="mt-2 flex flex-wrap gap-2"><button type="button" className="desk-button-brand" disabled={state.isLoading || state.isError || issue.isPending || revoke.isPending} onClick={() => issue.mutate()}>{state.data?.enabled ? t`Rotate calendar link` : t`Create calendar link`}</button>{state.data?.enabled ? <button type="button" className="desk-button-ghost" disabled={issue.isPending || revoke.isPending} onClick={() => revoke.mutate()}>{t`Revoke calendar link`}</button> : null}</div>
    {url ? <label className="mt-2 grid gap-1 text-sm">{t`Private calendar URL`}<input className="desk-input w-full" readOnly value={url} onFocus={(event) => event.target.select()} /></label> : null}
    {state.error || issue.error || revoke.error ? <p role="alert" className="text-danger">{(state.error ?? issue.error ?? revoke.error)?.message}</p> : null}
  </div>;
}
