import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, EmptyState, ErrorText, PagePager, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { formatDateTime } from "../../../lib/format";
import type { Paginated } from "../eventsApiTypes";
import { eventErrorText } from "../eventUi";

type SeriesInvite = { id: number; expires_at: string | null; revoked_at: string | null; created_at: string };
const MAX_BATCH = 200;
const EMAIL = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

/** Split pasted text into addresses: commas, semicolons, spaces or new lines all separate them. */
export function parseEmails(text: string) {
  const parts = text.split(/[\s,;]+/).map(part => part.trim().toLowerCase()).filter(Boolean);
  const unique = [...new Set(parts)];
  return { valid: unique.filter(part => EMAIL.test(part)), invalid: unique.filter(part => !EMAIL.test(part)) };
}

/**
 * The series allowlist (parity E-F3, B12): an address on it may register for every occurrence of an invite-only
 * series. Entries keep a digest of the address only, so the list shows when each was added, never the email.
 */
export function SeriesInvitesPanel({ seriesId, disabled = false }: { seriesId: number; disabled?: boolean }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [text, setText] = useState("");
  const [expires, setExpires] = useState("");
  const [result, setResult] = useState("");
  const key = ["event-series-invites", seriesId];
  const rows = useQuery({ queryKey: [...key, page], retry: false,
    queryFn: () => staffRequest<Paginated<SeriesInvite>>(`/admin/event-series/${seriesId}/invites/?page=${page}`) });
  const add = useMutation({
    mutationFn: (emails: string[]) => staffRequest<{ created: SeriesInvite[]; skipped: number }>(`/admin/event-series/${seriesId}/invites/`,
      { method: "POST", body: JSON.stringify({ emails, ...(expires ? { expires_at: new Date(expires).toISOString() } : {}) }) }),
    onSuccess: data => {
      setText("");
      setResult(`${plural(data.created.length, { one: "# address added.", other: "# addresses added." })}${data.skipped ? ` ${plural(data.skipped, { one: "# was already on the list.", other: "# were already on the list." })}` : ""}`);
      void client.invalidateQueries({ queryKey: key });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => staffRequest<SeriesInvite>(`/admin/event-series-invites/${id}/revoke/`, { method: "POST", body: "{}" }),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  const parsed = parseEmails(text);
  const tooMany = parsed.valid.length > MAX_BATCH;
  return <section className="grid gap-4" aria-labelledby={`series-invites-${seriesId}`}>
    <div><h3 id={`series-invites-${seriesId}`} className="title-section">{t`Invited people`}</h3>
      <p className="mt-1 max-w-[65ch] text-sm text-muted">{t`People on this list can sign up for every date in the series while sign-up is by invitation. Addresses are stored only as a fingerprint, so they are not shown again.`}</p></div>
    <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault(); setResult(""); if (parsed.valid.length && !tooMany) add.mutate(parsed.valid); }}>
      <label className="grid gap-1 text-sm font-semibold">{t`Email addresses`}
        <textarea className="desk-input min-h-28 font-normal" value={text} disabled={disabled} onChange={event => setText(event.target.value)}
          placeholder={t`One per line, or separated by commas`} /></label>
      <label className="grid gap-1 text-sm font-semibold sm:max-w-xs">{t`Invitation ends (optional)`}
        <input className="desk-input font-normal" type="datetime-local" value={expires} disabled={disabled} onChange={event => setExpires(event.target.value)} /></label>
      <p className="text-sm text-muted" aria-live="polite">{parsed.valid.length ? plural(parsed.valid.length, { one: "# address ready to add.", other: "# addresses ready to add." }) : t`Paste the addresses to invite.`}
        {parsed.invalid.length ? ` ${t`Not an address: ${parsed.invalid.slice(0, 3).join(", ")}`}` : ""}</p>
      {tooMany ? <p role="alert" className="text-sm text-danger">{t`Add at most ${MAX_BATCH} addresses at a time.`}</p> : null}
      <button type="submit" className="desk-button-primary justify-self-start" disabled={disabled || add.isPending || !parsed.valid.length || tooMany}>{add.isPending ? t`Adding…` : t`Add to the list`}</button>
      {result ? <p role="status" className="text-sm text-success-ink">{result}</p> : null}
      {add.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(add.error)}</p> : null}
    </form></Card>
    {rows.error ? <ErrorText message={eventErrorText(rows.error)} onRetry={() => { void rows.refetch(); }} /> : null}
    {rows.data && !rows.data.results.length ? <EmptyState message={t`Nobody is on the list yet.`} /> : null}
    {rows.data?.results.length ? <ul className="grid gap-2" aria-label={t`Allowlist entries`}>{rows.data.results.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-panel p-3">
      <div className="min-w-0 text-sm"><p className="font-semibold text-ink">{t`Entry ${row.id}`}</p>
        <p className="tabular-nums text-muted">{t`Added ${formatDateTime(row.created_at)}`}{row.expires_at ? ` · ${t`ends ${formatDateTime(row.expires_at)}`}` : ""}</p></div>
      {row.revoked_at ? <StatusPill label={t`Removed`} /> : <button type="button" className="desk-button-danger-outline" disabled={disabled || revoke.isPending}
        onClick={() => revoke.mutate(row.id)}>{t`Remove entry ${row.id}`}</button>}
    </li>)}</ul> : null}
    {revoke.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(revoke.error)}</p> : null}
    <PagePager page={page} setPage={setPage} next={rows.data?.next} />
  </section>;
}
