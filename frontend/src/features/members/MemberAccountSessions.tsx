import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, StatusPill, RelativeTime } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clearAccessToken } from "../../lib/api";
import { accountKey, ownSessions, revokeSession, type AccountSession } from "./memberAccountApi";

export function MemberAccountSessions({ makerspaceId, onSignedOut }: { makerspaceId: number; onSignedOut: () => void }) {
  const [page, setPage] = useState(1);
  const client = useQueryClient();
  const rows = useQuery({ queryKey: [...accountKey(makerspaceId), "sessions", page], queryFn: () => ownSessions(makerspaceId, page), retry: false });
  const revoke = useMutation({ mutationFn: (session: AccountSession) => revokeSession(makerspaceId, session.id), onSuccess: (_, session) => {
    if (session.current) { clearAccessToken(); onSignedOut(); void client.cancelQueries({ queryKey: ["member"] }).then(() => client.removeQueries({ queryKey: ["member"] })); }
    else void client.invalidateQueries({ queryKey: [...accountKey(makerspaceId), "sessions"] });
  } });
  // A sub-part of the account page's Security settings section, so its heading sits one level below it.
  return <section aria-labelledby="account-sessions-heading" className="grid min-w-0 gap-3"><h3 id="account-sessions-heading" className="title-section">{t`Sessions and devices`}</h3>
    {rows.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading sessions…`}</p> : null}
    {rows.error || revoke.error ? <p role="alert" className="text-sm text-danger">{(rows.error || revoke.error)?.message}</p> : null}
    {rows.data?.results.length === 0 ? <EmptyState message={t`No other devices are signed in.`} /> : null}
    <div className="grid gap-3">{rows.data?.results.map(session => <ListRow key={session.id} title={session.kind === "device" ? t`Native device` : t`Browser session`}
      identity={{ kind: "icon", icon: "User", tone: "info" }} meta={<>{t`Started ${new Date(session.created_at).toLocaleString(formatLocale())}`}{session.last_used_at ? <> {t` · Last used `}<RelativeTime date={session.last_used_at} /></> : null}{session.id.startsWith("web-legacy:") ? <span className="block">{t`This older session loses refresh access immediately; its current access token lasts until its original expiry.`}</span> : null}</>}
      right={<div className="flex flex-wrap items-center gap-3">{session.current ? <StatusPill label={t`This device`} tone="info" /> : null}<button type="button" className="desk-button" disabled={revoke.isPending} onClick={() => revoke.mutate(session)}>{t`Revoke `}{session.current ? t`this session` : session.kind === "device" ? "device" : "session"}</button></div>} />)}</div>
    <div className="flex flex-wrap gap-2"><button type="button" className="desk-button" disabled={!rows.data?.previous} onClick={() => setPage(page - 1)}>{t`Previous sessions`}</button><button type="button" className="desk-button" disabled={!rows.data?.next} onClick={() => setPage(page + 1)}>{t`Next sessions`}</button></div>
  </section>;
}
