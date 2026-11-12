import { LogoLoader } from "../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, EmptyState, ErrorText, ListRow, RelativeTime } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { LinkSignInProviders } from "./LinkSignInProviders";

export type SocialIdentity = { provider: string; created_at: string; updated_at: string };

const key = ["auth", "social-identities"] as const;
const NAMES: Record<string, string> = { google: t`Google`, apple: t`Apple`, github: t`GitHub` };
const name = (provider: string) => NAMES[provider] ?? provider.replace(/^oidc[:_-]?/, "").replace(/[-_]/g, " ");

/**
 * Sign-in providers linked to this person's account (`GET/DELETE auth/social/providers`).
 * Unlinking only stops that provider signing in; the server refuses removing the last way in.
 * Linking (`POST`) is offered for browser-configured providers not linked yet (LinkSignInProviders).
 */
export function LinkedSignInList() {
  const client = useQueryClient();
  const [removing, setRemoving] = useState<SocialIdentity>();
  const [notice, setNotice] = useState("");
  const query = useQuery({ queryKey: key, retry: false, queryFn: () => staffRequest<SocialIdentity[]>("/auth/social/providers") });
  const unlink = useMutation({
    mutationFn: (provider: string) => staffRequest<void>(`/auth/social/providers/${encodeURIComponent(provider)}`, { method: "DELETE" }),
    onSuccess: (_data, provider) => { setRemoving(undefined); setNotice(t`${name(provider)} is no longer linked.`); void client.invalidateQueries({ queryKey: key }); },
  });
  if (query.isLoading) return <LogoLoader label={t`Loading linked accounts…`} size={48} className="min-h-16 py-3" />;
  if (query.error) return <ErrorText message={authErrorMessage(query.error, "Couldn't load your linked accounts. Try again.")} onRetry={() => void query.refetch()} />;
  const rows = query.data ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`Accounts you can sign in with besides your email. Unlink any you no longer use.`}</p>
    {rows.length ? <ul className="grid gap-3">{rows.map(row => <li key={row.provider}><ListRow title={name(row.provider)}
      identity={{ kind: "icon", icon: "KeyRound", tone: "neutral" }}
      meta={<>{t`Linked `}<RelativeTime date={row.created_at} /></>}
      right={<button type="button" className="desk-button min-h-11" disabled={unlink.isPending} aria-label={t`Unlink ${name(row.provider)}`}
        onClick={() => setRemoving(row)}>{t`Unlink`}</button>} /></li>)}</ul>
      : <EmptyState message={t`No sign-in accounts are linked.`} />}
    <LinkSignInProviders linked={rows.map(row => row.provider)} onLinked={row => {
      setNotice(t`${name(row.provider)} is now linked.`); void client.invalidateQueries({ queryKey: key }); }} />
    {notice ? <p role="status" className="text-sm">{notice}</p> : null}
    {unlink.error ? <ErrorText message={authErrorMessage(unlink.error, "Couldn't unlink that account. Try again.")} /> : null}
    {removing ? <ConfirmDialog open title={t`Unlink ${name(removing.provider)}?`} tone="danger" confirmLabel={t`Unlink`}
      message={t`You won't be able to sign in with ${name(removing.provider)} until you link it again.`}
      onCancel={() => setRemoving(undefined)} onConfirm={() => unlink.mutate(removing.provider)} /> : null}
  </div>;
}
