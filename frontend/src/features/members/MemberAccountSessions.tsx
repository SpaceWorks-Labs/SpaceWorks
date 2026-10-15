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
  return <section className="desk-panel p-5"><h2 className="title-panel">Sessions and devices</h2>
    {rows.isLoading ? <p role="status">Loading sessions…</p> : null}
    {rows.error || revoke.error ? <p role="alert" className="text-danger">{(rows.error || revoke.error)?.message}</p> : null}
    {rows.data?.results.length === 0 ? <EmptyState message="No other devices are signed in." /> : null}
    <div className="mt-3 grid gap-3">{rows.data?.results.map(session => <ListRow key={session.id} title={session.kind === "device" ? "Native device" : "Browser session"}
      identity={{ kind: "icon", icon: "User", tone: "info" }} meta={<>Started {new Date(session.created_at).toLocaleString()}{session.last_used_at ? <> · Last used <RelativeTime date={session.last_used_at} /></> : null}{session.id.startsWith("web-legacy:") ? <span className="block">This older session loses refresh access immediately; its current access token lasts until its original expiry.</span> : null}</>}
      right={<div className="flex flex-wrap items-center gap-3">{session.current ? <StatusPill label="This device" tone="info" /> : null}<button className="desk-button" disabled={revoke.isPending} onClick={() => revoke.mutate(session)}>Revoke {session.current ? "this session" : session.kind === "device" ? "device" : "session"}</button></div>} />)}</div>
    <div className="flex gap-2 mt-3"><button className="desk-button" disabled={!rows.data?.previous} onClick={() => setPage(page - 1)}>Previous sessions</button><button className="desk-button" disabled={!rows.data?.next} onClick={() => setPage(page + 1)}>Next sessions</button></div>
  </section>;
}
