import { formatDateTime } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { Trans } from "@lingui/react/macro";
import { EmptyState, ListRow, Pagination, StatusPill, RelativeTime } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clearAccessToken } from "../../lib/api";
import { accountKey, ownSessions, revokeSession, type AccountSession } from "./memberAccountApi";
import { LogoLoader } from "../../components/LogoLoader";

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
    {rows.isLoading ? <LogoLoader label={t`Loading sessions…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.error || revoke.error ? <p role="alert" className="text-sm text-danger">{(rows.error || revoke.error)?.message}</p> : null}
    {rows.data?.results.length === 0 ? <EmptyState message={t`No other devices are signed in.`} /> : null}
    <div className="grid gap-3">{rows.data?.results.map(session => <ListRow key={session.id} title={session.kind === "device" ? t`Native device` : t`Browser session`}
      identity={{ kind: "icon", icon: "User", tone: "info" }} meta={<>{t`Started ${formatDateTime(session.created_at)}`}{session.last_used_at ? <span className="block"><Trans>Last used <RelativeTime date={session.last_used_at} /></Trans></span> : null}{session.id.startsWith("web-legacy:") ? <span className="block">{t`This older session loses refresh access immediately; its current access token lasts until its original expiry.`}</span> : null}</>}
      right={<div className="flex flex-wrap items-center gap-3">{session.current ? <StatusPill label={t`This device`} tone="info" /> : null}<button type="button" className="desk-button" disabled={revoke.isPending} onClick={() => revoke.mutate(session)}>{session.current ? t`Revoke this session` : session.kind === "device" ? t`Revoke device` : t`Revoke session`}</button></div>} />)}</div>
    <Pagination page={page} totalPages={rows.data?.next ? page + 1 : page} onChange={setPage} />
  </section>;
}
