// /account/api-access (#196): my personal access tokens and the apps I connected.
// Creating a token asks for a fresh sign-in check (the API client prompts for it).
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SettingsLayout } from "../../../components/layouts";
import { ConfirmDialog, EmptyState, ErrorBlock, ErrorText, Field, ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { MemberAuthPanel } from "../MemberAuthPanel";
import { ApiClientSecretReveal } from "../../staff/ApiClientSecretReveal";
import {
  accessTokensKey, connectedAppsKey, createAccessToken, disconnectApp, getPersonScopes, listAccessTokens,
  listConnectedApps, personScopesKey, revokeAccessToken,
} from "./personalApiAccessApi";
import { BoxArt } from "../../../components/BoxSpinner";

export function PersonalApiAccessPage() {
  const queryClient = useQueryClient();
  const tokens = useQuery({ queryKey: accessTokensKey, queryFn: listAccessTokens, retry: false });
  const apps = useQuery({ queryKey: connectedAppsKey, queryFn: listConnectedApps, retry: false });
  const catalog = useQuery({ queryKey: personScopesKey, queryFn: getPersonScopes, retry: false });
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [space, setSpace] = useState<string>("");
  const [days, setDays] = useState(90);
  const [secret, setSecret] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "token" | "app"; id: number } | null>(null);
  const create = useMutation({
    mutationFn: () => createAccessToken({ name, scopes, makerspace: space ? Number(space) : null, expires_in_days: days }),
    onSuccess: (created) => {
      setSecret(created.token); setName(""); setScopes([]); setSpace("");
      void queryClient.invalidateQueries({ queryKey: accessTokensKey });
    },
  });
  const revoke = useMutation({
    mutationFn: (target: { kind: "token" | "app"; id: number }) => target.kind === "token"
      ? revokeAccessToken(target.id) : disconnectApp(target.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accessTokensKey });
      void queryClient.invalidateQueries({ queryKey: connectedAppsKey });
    },
  });
  if (tokens.error instanceof StructuredApiError && tokens.error.status === 401) {
    return <MemberAuthPanel onAuthenticated={() => { void tokens.refetch(); }} />;
  }
  const options = catalog.data?.scopes ?? [];
  const needsSpace = scopes.some((value) => options.find((option) => option.value === value)?.needs_space);
  const toggle = (value: string) => setScopes((current) => current.includes(value)
    ? current.filter((item) => item !== value) : [...current, value]);
  const liveTokens = (tokens.data ?? []).filter((token) => !token.revoked_at);
  return <>
    <SettingsLayout standalone header={{ title: t`API access`, subtitle: t`Tokens and apps that act as you. They can never do more than you can.` }}
      state={{ status: tokens.isLoading ? "loading" : "ready" }} sections={[
        { id: "new-token", title: t`New personal access token`, rows: <div className="grid gap-3">
          <Field label={t`Name`}><input className="desk-input w-full" value={name} onChange={(event) => setName(event.target.value)} /></Field>
          <fieldset className="grid gap-2"><legend className="font-semibold text-ink">{t`What can it do?`}</legend>
            {options.map((option) => <label key={option.value} className="flex cursor-pointer items-start gap-3">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-accent" checked={scopes.includes(option.value)}
                onChange={() => toggle(option.value)} />
              <span className="grid"><span className="font-semibold text-ink">{option.label}</span>
                <span className="text-xs text-muted">{option.description}</span></span>
            </label>)}
          </fieldset>
          {needsSpace ? <Field label={t`Space (staff scopes apply to one space)`}>
            <select className="desk-input w-full" value={space} onChange={(event) => setSpace(event.target.value)}>
              <option value="">{t`Choose a space`}</option>
              {(catalog.data?.staff_spaces ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select></Field> : null}
          <Field label={t`Expires after (days, up to 365)`}>
            <input type="number" min={1} max={365} className="desk-input w-32" value={days}
              onChange={(event) => setDays(Math.min(365, Math.max(1, Number(event.target.value) || 90)))} /></Field>
          <button className="desk-button-primary" disabled={!name.trim() || !scopes.length || (needsSpace && !space) || create.isPending}
            onClick={() => create.mutate()}>{create.isPending ? <><BoxArt size={16} mono />{t`Creating…`}</> : t`Create token`}</button>
          {create.error ? <ErrorText message={create.error.message} /> : null}
          {secret ? <ApiClientSecretReveal secret={secret} onDismiss={() => setSecret(null)} /> : null}
        </div> },
        { id: "tokens", title: t`My tokens`, rows: <div className="grid gap-2">
          {tokens.error ? <ErrorBlock error={tokens.error} onRetry={() => { void tokens.refetch(); }} /> : null}
          {liveTokens.map((token) => <ListRow key={token.id} title={token.name}
            meta={<>{t`${token.scopes.join(", ")} · expires `}<RelativeTime inline date={token.expires_at} /> · {token.last_used_at
              ? <>{t`last used `}<RelativeTime date={token.last_used_at} /></> : t`never used`}</>}
            right={<button className="desk-button" onClick={() => setConfirm({ kind: "token", id: token.id })}>{t`Revoke`}</button>} />)}
          {!tokens.isLoading && !liveTokens.length ? <EmptyState message={t`No tokens. A token is shown once, right after you create it.`} /> : null}
        </div> },
        { id: "apps", title: t`Connected apps`, rows: <div className="grid gap-2">
          {apps.error ? <ErrorBlock error={apps.error} onRetry={() => { void apps.refetch(); }} /> : null}
          {(apps.data ?? []).map((app) => <ListRow key={app.application_id} title={app.app_name}
            meta={<>{t`${app.space_name} · ${app.scopes.join(", ")} · connected `}<RelativeTime date={app.granted_at} /></>}
            right={<><StatusPill label={t`Connected`} tone="success" />
              <button className="desk-button" onClick={() => setConfirm({ kind: "app", id: app.application_id })}>{t`Disconnect`}</button></>} />)}
          {!apps.isLoading && !apps.data?.length ? <EmptyState message={t`No apps are connected to your account.`} /> : null}
        </div> },
      ]} />
    <ConfirmDialog open={confirm !== null} tone="danger" pending={revoke.isPending}
      title={confirm?.kind === "app" ? t`Disconnect this app?` : t`Revoke this token?`}
      message={confirm?.kind === "app" ? t`The app loses access at once and must ask you again.` : t`Anything using it stops working at once.`}
      confirmLabel={confirm?.kind === "app" ? t`Disconnect` : t`Revoke`} onCancel={() => setConfirm(null)}
      onConfirm={() => { if (confirm) revoke.mutate(confirm); setConfirm(null); }} />
  </>;
}
