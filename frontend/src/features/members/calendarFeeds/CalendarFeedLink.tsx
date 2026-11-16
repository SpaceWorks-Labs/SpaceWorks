import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog } from "../../../components/ui";
import type { FeedEndpoint } from "./calendarFeedsApi";
import { OwnerScoped, type FeedScope } from "./ownerScope";

type Props = { title: string; description: string; endpoint: FeedEndpoint };

/**
 * One private calendar link: create, rotate, revoke. The full URL is a bearer credential, shown
 * once in component state only (never in the query cache) and never retrievable again.
 */
export function CalendarFeedLink(props: Props) {
  return <OwnerScoped>{scope => <FeedLinkCard {...props} scope={scope} />}</OwnerScoped>;
}

function FeedLinkCard({ title, description, endpoint, scope }: Props & { scope: FeedScope }) {
  const client = useQueryClient();
  const [issuedUrl, setIssuedUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean | null>(null);
  const [asking, setAsking] = useState<"issue" | "revoke" | null>(null);
  const key = [...endpoint.key, ...scope.key];
  const feed = useQuery({ queryKey: key, queryFn: endpoint.state, retry: false });
  const issue = useMutation({
    mutationFn: async () => {
      const result = await endpoint.issue();
      if (scope.admitted()) setIssuedUrl(result.feed_url);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  const revoke = useMutation({
    mutationFn: endpoint.revoke,
    onSuccess: async () => { if (scope.admitted()) setIssuedUrl(null); await client.invalidateQueries({ queryKey: key }); },
  });
  const error = feed.error || issue.error || revoke.error;
  const enabled = Boolean(feed.data?.enabled);
  const hint = feed.data?.token_hint ?? "";
  const question = enabled
    ? t`This will replace your private calendar link. Anyone with the link can see ${description}. Continue?`
    : t`This will create a private calendar link. Anyone with the link can see ${description}. Continue?`;
  return <div className="rounded-md border border-line p-3 text-sm">
    <p className="font-semibold text-ink">{title}</p>
    <p className="text-xs text-muted">{t`Shows ${description}.`}</p>
    <div className="mt-2 flex flex-wrap gap-2">
      <button className="desk-button" type="button" disabled={issue.isPending || feed.isLoading} onClick={() => setAsking("issue")}>
        {enabled ? t`Rotate link` : t`Create link`}</button>
      {enabled ? <button className="desk-button-danger" type="button" disabled={revoke.isPending}
        onClick={() => setAsking("revoke")}>{t`Revoke link`}</button> : null}
    </div>
    {enabled && !issuedUrl ? <p className="mt-2 text-xs text-muted">{t`Active private link ending in ${hint}. The full link cannot be shown again.`}</p> : null}
    {issuedUrl ? <div className="mt-3 border-l-2 border-warn pl-3">
      <p className="font-semibold text-ink">{t`Copy this link now. It will not be shown again.`}</p>
      <input className="desk-input code-text mt-2 w-full" readOnly value={issuedUrl} aria-label={t`${title} subscription link`}
        onFocus={event => event.currentTarget.select()} />
      <button className="desk-button mt-2" type="button" onClick={() => {
        setCopied(null);
        // Insecure contexts have no clipboard; that is a failure to report, not a crash.
        Promise.resolve().then(() => navigator.clipboard.writeText(issuedUrl)).then(() => setCopied(true), () => setCopied(false));
      }}>{t`Copy link`}</button>
      <p className="mt-1 text-xs text-muted" role="status">{copied === true ? t`Link copied.` : copied === false ? t`Copy failed. Select the link and copy it manually.` : ""}</p>
      <p className="mt-2 text-xs text-danger">{t`Treat this URL like a password. Rotate it if it is shared by mistake.`}</p>
    </div> : null}
    <ConfirmDialog open={asking === "issue"} title={enabled ? t`Replace private link?` : t`Create private link?`} message={question}
      tone="danger" confirmLabel={enabled ? t`Yes, replace link` : t`Yes, create link`}
      onCancel={() => setAsking(null)} onConfirm={() => { setAsking(null); issue.mutate(); }} />
    <ConfirmDialog open={asking === "revoke"} title={t`Revoke private link?`} message={t`Revoke the private link for ${title}?`}
      tone="danger" confirmLabel={t`Yes, revoke link`}
      onCancel={() => setAsking(null)} onConfirm={() => { setAsking(null); revoke.mutate(); }} />
    {error ? <p className="mt-2 text-xs text-danger" role="alert">{error instanceof Error ? error.message : t`Calendar action failed.`}</p> : null}
  </div>;
}
