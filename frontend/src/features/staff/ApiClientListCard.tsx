import { useEffect, useMemo, useState } from "react";
import { DetailLayout } from "../../components/layouts";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { Callout, ConfirmDialog, EmptyState, ErrorBlock, ListRow, OverflowMenu, RelativeTime, StatusPill } from "../../components/ui";
import { ApiClientScopePicker } from "./ApiClientScopePicker";
import {
  scopeOptionsForClient,
  type ApiClient,
  type ApiClientScopeOption,
  type ApiKeyRequest,
} from "./apiClientsApi";
type Props = {
  canManageMakerspace: boolean;
  clients: ApiClient[] | undefined;
  clientsLoading: boolean;
  clientsError: Error | null;
  onRetry?: () => void;
  requests: ApiKeyRequest[] | undefined;
  requestsLoading?: boolean;
  requestsError?: Error | null;
  deletePending: boolean;
  deleteError: Error | null;
  rotatePending: boolean;
  rotateError: Error | null;
  scopeOptions: ApiClientScopeOption[];
  scopesLoading: boolean;
  scopesError: Error | null;
  onRetryScopes?: () => void;
  scopeUpdatePending: boolean;
  scopeUpdateError: Error | null;
  onDelete: (clientId: number) => void;
  onRotate: (clientId: number) => void;
  onScopesUpdate: (clientId: number, scopes: string[]) => void;
};

export function ApiClientListCard({
  canManageMakerspace,
  clients,
  clientsLoading,
  clientsError,
  onRetry,
  requests,
  requestsLoading,
  requestsError,
  deletePending,
  deleteError,
  rotatePending,
  rotateError,
  scopeOptions,
  scopesLoading,
  scopesError,
  onRetryScopes,
  scopeUpdatePending,
  scopeUpdateError,
  onDelete,
  onRotate,
  onScopesUpdate,
}: Props) {
  const errors = [scopesError, scopeUpdateError, deleteError, rotateError].filter(Boolean);
  return <div className="grid gap-3">
    {canManageMakerspace ? <>
      <QueryContent state={{ status: clientsLoading ? "loading" : clientsError ? "error" : "ready", error: "Couldn't load API clients. Try again.", onRetry }}>
      {clients?.map(client => <ApiClientRow key={client.id} client={client} scopeOptions={scopeOptions}
        scopesLoading={scopesLoading} updatePending={scopeUpdatePending} deletePending={deletePending}
        rotatePending={rotatePending} updateError={scopeUpdateError} scopesError={scopesError} onRetryScopes={onRetryScopes} onDelete={onDelete} onRotate={onRotate} onScopesUpdate={onScopesUpdate} />)}
      {!clientsLoading && clients?.length === 0 ? <EmptyState message="No clients yet. The secret appears once, right after you create one." /> : null}
      </QueryContent>
      {errors.map((error, index) => <ErrorBlock key={index} error={error!} />)}
    </> : <>
      <QueryContent state={{ status: requestsLoading ? "loading" : requestsError ? "error" : "ready", error: "Couldn't load API access requests. Try again.", onRetry }}>
      {requests?.map(request => <ListRow key={request.id} title={request.label}
        meta={<><RelativeTime date={request.created_at} />{request.resolution_note ? ` · ${request.resolution_note}` : ""}</>}
        right={<StatusPill label={request.status} />} />)}
      {requests?.length === 0 ? <EmptyState message="No API access requests yet. Send a request to connect your tools." /> : null}
      </QueryContent>
    </>}
  </div>;
}

function ApiClientRow({ client, scopeOptions, scopesLoading, updatePending, updateError, scopesError, onRetryScopes, deletePending, rotatePending, onDelete, onRotate, onScopesUpdate }: {
  client: ApiClient;
  scopeOptions: ApiClientScopeOption[];
  scopesLoading: boolean;
  updatePending: boolean;
  updateError: Error | null;
  scopesError: Error | null;
  onRetryScopes?: () => void;
  deletePending: boolean;
  rotatePending: boolean;
  onDelete: (clientId: number) => void;
  onRotate: (clientId: number) => void;
  onScopesUpdate: (clientId: number, scopes: string[]) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState<"rotate" | "delete" | null>(null);
  const [selected, setSelected] = useState<string[]>(client.scopes);
  useEffect(() => setSelected(client.scopes), [client.scopes]);
  const clientScopeOptions = useMemo(
    () => scopeOptionsForClient(scopeOptions, client.client_type),
    [client.client_type, scopeOptions],
  );
  const grantable = useMemo(
    () => selected.filter((scope) => clientScopeOptions.some(
      (option) => option.value === scope && option.grantable,
    )),
    [clientScopeOptions, selected],
  );
  const hasLegacy = client.scopes.includes("legacy:v1");
  const changed = grantable.join("\0") !== client.scopes.join("\0");
  return <>
    <ListRow title={client.label} identity={{ kind: "icon", icon: "Settings", tone: "accent" }}
      meta={<span className="grid gap-1"><span className="break-all tabular-nums">{client.client_id}</span>
        <span>{client.allowed_origins.length ? client.allowed_origins.join(", ") : "No browser origins configured."}</span>
        <span>Created <RelativeTime date={client.created_at} /> · {client.last_seen_at ? <>Last used <RelativeTime date={client.last_seen_at} /></> : "Never used"}</span></span>}
      right={<div className="flex flex-wrap items-center gap-2"><StatusPill label={client.is_active ? "Active" : "Inactive"} tone={client.is_active ? "success" : "neutral"} />
        <StatusPill label={`${client.scopes.length} scopes`} />
        {hasLegacy ? <StatusPill label="Legacy v1" tone="warn" /> : null}
        <button className="desk-button" onClick={() => setEditing(true)}>Edit scopes</button>
        <OverflowMenu label={`Actions for ${client.label}`} actions={[
          { label: "Rotate secret", onClick: () => setConfirm("rotate"), disabled: rotatePending, confirms: true },
          { label: "Delete", onClick: () => setConfirm("delete"), disabled: deletePending, tone: "danger", confirms: true },
        ]} /></div>} />
    {editing ? <DetailLayout presentation="drawer" open onClose={() => { setSelected(client.scopes); setEditing(false); }} title={`Scopes for ${client.label}`}
      state={{ status: scopesLoading ? "loading" : scopesError ? "error" : "ready", error: "Couldn't load API scopes. Try again.", onRetry: onRetryScopes }}
      footer={{ secondary: [{ label: "Discard", onClick: () => { setSelected(client.scopes); setEditing(false); } }],
        primary: { label: "Save scopes", pending: updatePending, disabled: !grantable.length || !changed,
          onClick: () => onScopesUpdate(client.id, grantable) } }}
      main={<div className="grid gap-4">{hasLegacy ? <Callout size="card" tone="warn" lead="Legacy v1 access" body="Select explicit replacement scopes and save. Viewing this client never changes its access." /> : null}
        <ApiClientScopePicker options={clientScopeOptions} selected={selected} onChange={setSelected} disabled={updatePending} />
        {updateError || scopesError ? <ErrorBlock error={(updateError ?? scopesError)!} /> : null}</div>} /> : null}
    <ConfirmDialog open={confirm !== null} title={confirm === "delete" ? "Delete API client?" : "Rotate client secret?"}
      message={confirm === "delete" ? "Tools using this client will lose access." : "The current secret will stop working. Copy the replacement after rotating."}
      confirmLabel={confirm === "delete" ? "Delete" : "Rotate secret"} tone={confirm === "delete" ? "danger" : "default"}
      pending={deletePending || rotatePending} onCancel={() => setConfirm(null)}
      onConfirm={() => { if (confirm === "delete") onDelete(client.id); else onRotate(client.id); setConfirm(null); }} />
  </>;
}
