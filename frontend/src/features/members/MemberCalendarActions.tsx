import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog } from "../../components/ui";
import { memberRequest, memberRequestBlob } from "../../lib/api";
import { OwnerScoped, type FeedScope } from "./calendarFeeds/ownerScope";
import { BoxArt } from "../../components/BoxSpinner";

type FeedState = {
  enabled: boolean;
  token_hint: string | null;
  created_at: string | null;
  rotated_at: string | null;
};
type IssuedFeed = { feed_url: string; token_hint: string; created_at: string };

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

type Props = { makerspaceId: number; makerspaceSlug: string };

export function MemberCalendarActions(props: Props) {
  return <OwnerScoped>{scope => <EventCalendarCard {...props} scope={scope} />}</OwnerScoped>;
}

function EventCalendarCard({ makerspaceId, makerspaceSlug, scope }: Props & { scope: FeedScope }) {
  const queryClient = useQueryClient();
  const [issuedUrl, setIssuedUrl] = useState<string | null>(null);
  const [asking, setAsking] = useState<"issue" | "revoke" | null>(null);
  const path = `/member/makerspaces/${makerspaceId}/event-calendar-feed/`;
  const key = ["member", makerspaceSlug, "event-calendar-feed", ...scope.key] as const;
  const feed = useQuery({ queryKey: key, queryFn: () => memberRequest<FeedState>(path) });
  const download = useMutation({
    mutationFn: async () => {
      const blob = await memberRequestBlob(`/member/makerspaces/${makerspaceId}/event-registrations/calendar.ics`);
      if (scope.admitted()) downloadBlob(blob, "my-events.ics");
    },
  });
  const issue = useMutation({
    mutationFn: async () => {
      const result = await memberRequest<IssuedFeed>(path, {
        method: "POST", body: JSON.stringify({ confirm_bearer_risk: true }),
      });
      // Keep the bearer URL only in component state. Returning void prevents TanStack's
      // mutation cache from retaining the credential after this one-time reveal.
      // A response landing after an owner switch belongs to the previous account: drop it.
      if (scope.admitted()) setIssuedUrl(result.feed_url);
    },
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const revoke = useMutation({
    mutationFn: () => memberRequest<void>(path, { method: "DELETE" }),
    onSuccess: async () => {
      if (scope.admitted()) setIssuedUrl(null);
      await queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const error = feed.error || download.error || issue.error || revoke.error;

  const replacing = Boolean(feed.data?.enabled);
  const question = replacing
    ? t`This will replace your private calendar link. Anyone with the link can see your event schedule. Continue?`
    : t`This will create a private calendar link. Anyone with the link can see your event schedule. Continue?`;

  return <div className="mt-3 rounded-md border border-line p-3 text-sm">
    <p className="font-semibold text-ink">{t`My event calendar`}</p>
    <div className="mt-2 flex flex-wrap gap-2">
      <button className="desk-button" type="button" disabled={download.isPending} onClick={() => download.mutate()}>
        {download.isPending ? <><BoxArt size={16} mono />{t`Preparing…`}</> : t`Download calendar`}
      </button>
      <button className="desk-button" type="button" disabled={issue.isPending || feed.isLoading} onClick={() => setAsking("issue")}>
        {feed.data?.enabled ? t`Rotate subscription link` : t`Create subscription link`}
      </button>
      {feed.data?.enabled ? <button
        className="desk-button-danger" type="button" disabled={revoke.isPending}
        onClick={() => setAsking("revoke")}
      >{t`Revoke link`}</button> : null}
    </div>
    {feed.data?.enabled && !issuedUrl ? <p className="mt-2 text-xs text-muted">
      {t`Active private link ending in `}<span className="code-text">{feed.data.token_hint}</span>. The full link is not persisted and cannot be revealed again.
    </p> : null}
    {issuedUrl ? <div className="mt-3 border-l-2 border-warn pl-3">
      <p className="font-semibold text-ink">{t`Copy this link now. It will not be shown again.`}</p>
      <input className="desk-input mt-2 w-full code-text" readOnly value={issuedUrl} aria-label={t`Private calendar subscription link`} onFocus={(event) => event.currentTarget.select()} />
      <button className="desk-button mt-2" type="button" onClick={() => navigator.clipboard.writeText(issuedUrl).catch(() => undefined)}>{t`Copy link`}</button>
      <p className="mt-2 text-xs text-danger">{t`Treat this URL like a password. Rotate it if it is shared accidentally.`}</p>
    </div> : null}
    <ConfirmDialog open={asking === "issue"} title={replacing ? t`Replace private link?` : t`Create private link?`} message={question}
      tone="danger" confirmLabel={replacing ? t`Yes, replace link` : t`Yes, create link`}
      onCancel={() => setAsking(null)} onConfirm={() => { setAsking(null); issue.mutate(); }} />
    <ConfirmDialog open={asking === "revoke"} title={t`Revoke private link?`} message={t`Revoke the current calendar subscription link?`}
      tone="danger" confirmLabel={t`Yes, revoke link`}
      onCancel={() => setAsking(null)} onConfirm={() => { setAsking(null); revoke.mutate(); }} />
    {error ? <p className="mt-2 text-xs text-danger" role="alert">{error instanceof Error ? error.message : t`Calendar action failed.`}</p> : null}
  </div>;
}
