import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { FeedEndpoint } from "./calendarFeedsApi";

/**
 * One private calendar link: create, rotate, revoke. The full URL is a bearer credential, shown
 * once in component state only (never in the query cache) and never retrievable again.
 */
export function CalendarFeedLink({ title, description, endpoint }: { title: string; description: string; endpoint: FeedEndpoint }) {
  const client = useQueryClient();
  const [issuedUrl, setIssuedUrl] = useState<string | null>(null);
  const feed = useQuery({ queryKey: endpoint.key, queryFn: endpoint.state, retry: false });
  const issue = useMutation({
    mutationFn: async () => { setIssuedUrl((await endpoint.issue()).feed_url); },
    onSuccess: () => client.invalidateQueries({ queryKey: endpoint.key }),
  });
  const revoke = useMutation({
    mutationFn: endpoint.revoke,
    onSuccess: async () => { setIssuedUrl(null); await client.invalidateQueries({ queryKey: endpoint.key }); },
  });
  const error = feed.error || issue.error || revoke.error;
  const enabled = Boolean(feed.data?.enabled);
  function confirmIssue() {
    if (window.confirm(t`This will ${enabled ? "replace" : "create"} a private calendar link. Anyone with the link can see ${description}. Continue?`)) {
      issue.mutate();
    }
  }
  return <div className="rounded-md border border-line p-3 text-sm">
    <p className="font-semibold text-ink">{title}</p>
    <p className="text-xs text-muted">{t`Shows ${description}.`}</p>
    <div className="mt-2 flex flex-wrap gap-2">
      <button className="desk-button" type="button" disabled={issue.isPending || feed.isLoading} onClick={confirmIssue}>
        {enabled ? t`Rotate link` : t`Create link`}</button>
      {enabled ? <button className="desk-button-danger" type="button" disabled={revoke.isPending}
        onClick={() => { if (window.confirm(t`Revoke the ${title.toLowerCase()} link?`)) revoke.mutate(); }}>{t`Revoke link`}</button> : null}
    </div>
    {enabled && !issuedUrl ? <p className="mt-2 text-xs text-muted">{t`Active private link ending in `}<span className="code-text">
      {feed.data?.token_hint}</span>. The full link cannot be shown again.</p> : null}
    {issuedUrl ? <div className="mt-3 border-l-2 border-warn pl-3">
      <p className="font-semibold text-ink">{t`Copy this link now. It will not be shown again.`}</p>
      <input className="desk-input code-text mt-2 w-full" readOnly value={issuedUrl} aria-label={t`${title} subscription link`}
        onFocus={event => event.currentTarget.select()} />
      <button className="desk-button mt-2" type="button" onClick={() => navigator.clipboard.writeText(issuedUrl).catch(() => undefined)}>
        {t`Copy link`}</button>
      <p className="mt-2 text-xs text-danger">{t`Treat this URL like a password. Rotate it if it is shared by mistake.`}</p>
    </div> : null}
    {error ? <p className="mt-2 text-xs text-danger" role="alert">{error instanceof Error ? error.message : t`Calendar action failed.`}</p> : null}
  </div>;
}
