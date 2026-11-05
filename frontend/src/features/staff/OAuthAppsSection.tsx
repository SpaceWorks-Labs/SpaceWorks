// #196: a space's registered OAuth apps (app connections). The Space Manager, or the superadmin
// for any space, registers an app; people then connect it to their own account on the consent screen.
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, EmptyState, ErrorText, Field, ListRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { ApiClientSecretReveal } from "./ApiClientSecretReveal";
import { splitOrigins } from "./apiClientsApi";
import { useStaffGet } from "./StaffPanels";

type OAuthApp = { id: number; name: string; client_id: string; client_type: "confidential" | "public";
  redirect_uris: string[]; allowed_scopes: string[]; is_active: boolean };
const SCOPES = ["account:read", "account:write", "public:read", "public:write", "staff:read", "staff:write"];

export function OAuthAppsSection({ makerspaceId }: { makerspaceId: number }) {
  const queryClient = useQueryClient();
  const key = ["oauth-apps", makerspaceId];
  const apps = useStaffGet<OAuthApp[]>(key, `/admin/makerspace/${makerspaceId}/oauth-apps`, true);
  const [name, setName] = useState("");
  const [uris, setUris] = useState("");
  const [kind, setKind] = useState<OAuthApp["client_type"]>("confidential");
  const [scopes, setScopes] = useState<string[]>(["account:read"]);
  const [created, setCreated] = useState<{ client_id: string; client_secret: string } | null>(null);
  const [remove, setRemove] = useState<number | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });
  const create = useMutation({
    mutationFn: () => staffRequest<OAuthApp & { client_secret: string }>(`/admin/makerspace/${makerspaceId}/oauth-apps`, {
      method: "POST", body: JSON.stringify({ name, client_type: kind, redirect_uris: splitOrigins(uris), allowed_scopes: scopes }),
    }),
    onSuccess: (app) => { setCreated(app); setName(""); setUris(""); void refresh(); },
  });
  const update = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => staffRequest(`/admin/oauth-apps/${id}`, {
      method: "PATCH", body: JSON.stringify({ is_active: active }) }),
    onSuccess: () => { void refresh(); },
  });
  const destroy = useMutation({
    mutationFn: (id: number) => staffRequest<void>(`/admin/oauth-apps/${id}`, { method: "DELETE" }),
    onSuccess: () => { void refresh(); },
  });
  return <div className="grid gap-3">
    <Field label="App name"><input className="desk-input w-full" value={name} onChange={(event) => setName(event.target.value)} /></Field>
    <Field label="Redirect URIs (https, one per line)">
      <textarea className="desk-input min-h-20 w-full" value={uris} onChange={(event) => setUris(event.target.value)} /></Field>
    <Field label="App type">
      <select className="desk-input w-full" value={kind} onChange={(event) => setKind(event.target.value as OAuthApp["client_type"])}>
        <option value="confidential">Has a server (keeps a client secret)</option>
        <option value="public">Runs on a phone or in a browser (PKCE only)</option>
      </select></Field>
    <fieldset className="flex flex-wrap gap-3"><legend className="font-semibold text-ink">Scopes it may ask for</legend>
      {SCOPES.map((scope) => <label key={scope} className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-accent" checked={scopes.includes(scope)}
          onChange={() => setScopes((current) => current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope])} />
        {scope}</label>)}
    </fieldset>
    <button className="desk-button-primary" disabled={!name.trim() || !splitOrigins(uris).length || !scopes.length || create.isPending}
      onClick={() => create.mutate()}>{create.isPending ? "Registering…" : "Register app"}</button>
    {create.error ? <ErrorText message={create.error.message} /> : null}
    {created ? <div className="grid gap-1"><p className="text-sm">Client ID: <span className="tabular-nums [overflow-wrap:anywhere]">{created.client_id}</span></p>
      {created.client_secret ? <ApiClientSecretReveal secret={created.client_secret} onDismiss={() => setCreated(null)} /> : null}</div> : null}
    {(apps.data ?? []).map((app) => <ListRow key={app.id} title={app.name}
      meta={<span className="[overflow-wrap:anywhere]">{app.client_id} · {app.allowed_scopes.join(", ")} · {app.redirect_uris.join(", ")}</span>}
      right={<><StatusPill label={app.is_active ? "Active" : "Off"} tone={app.is_active ? "success" : "neutral"} />
        <button className="desk-button" disabled={update.isPending} onClick={() => update.mutate({ id: app.id, active: !app.is_active })}>
          {app.is_active ? "Switch off" : "Switch on"}</button>
        <button className="desk-button" onClick={() => setRemove(app.id)}>Delete</button></>} />)}
    {!apps.isLoading && !apps.data?.length ? <EmptyState message="No apps registered. People connect an app from its sign-in button." /> : null}
    <ConfirmDialog open={remove !== null} tone="danger" title="Delete this app?" confirmLabel="Delete" pending={destroy.isPending}
      message="Everyone who connected it loses the connection at once." onCancel={() => setRemove(null)}
      onConfirm={() => { if (remove !== null) destroy.mutate(remove); setRemove(null); }} />
  </div>;
}
