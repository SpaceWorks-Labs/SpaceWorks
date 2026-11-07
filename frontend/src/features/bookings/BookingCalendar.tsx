import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { personalRecipientKey } from "../notifications/personalQueryKeys";

export function BookingCalendar({ slug }: { slug: string }) {
  const [url, setUrl] = useState("");
  const path = `/public/${encodeURIComponent(slug)}/my-bookings/calendar/`;
  const key = ["member", slug, "booking-calendar", personalRecipientKey()];
  const client = useQueryClient();
  const state = useQuery({ queryKey: key, queryFn: () => memberRequest<{ enabled: boolean }>(path) });
  const issue = useMutation({ mutationFn: () => memberRequest<{ feed_url: string }>(path, { method: "POST" }), onSuccess: (result) => { setUrl(result.feed_url); void client.invalidateQueries({ queryKey: key }); } });
  const revoke = useMutation({ mutationFn: () => memberRequest<void>(path, { method: "DELETE" }), onSuccess: () => { setUrl(""); void client.invalidateQueries({ queryKey: key }); } });
  // Release 2 L18: `bookings.calendar_feed` off answers 404; the card then disappears instead of erroring.
  if ((state.error as { status?: number } | null)?.status === 404) return null;
  return <div className="mt-3 rounded-lg border border-line p-3">
    <p className="text-sm text-muted">{t`Subscribe to your own bookings. Keep the calendar link private; rotating it disables the previous link.`}</p>
    <div className="mt-2 flex flex-wrap gap-2"><button type="button" className="desk-button-brand" disabled={state.isLoading || state.isError || issue.isPending || revoke.isPending} onClick={() => issue.mutate()}>{state.data?.enabled ? t`Rotate calendar link` : t`Create calendar link`}</button>{state.data?.enabled ? <button type="button" className="desk-button-ghost" disabled={issue.isPending || revoke.isPending} onClick={() => revoke.mutate()}>{t`Revoke calendar link`}</button> : null}</div>
    {url ? <label className="mt-2 grid gap-1 text-sm">{t`Private calendar URL`}<input className="desk-input w-full" readOnly value={url} onFocus={(event) => event.target.select()} /></label> : null}
    {state.error || issue.error || revoke.error ? <p role="alert" className="text-danger">{(state.error ?? issue.error ?? revoke.error)?.message}</p> : null}
  </div>;
}
