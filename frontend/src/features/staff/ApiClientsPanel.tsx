import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiClientCreateCard } from "./ApiClientCreateCard";
import { ApiClientListCard } from "./ApiClientListCard";
import {
  apiClientsQueryKey,
  apiClientScopesQueryKey,
  apiKeyRequestsQueryKey,
  apiSettingsQueryKey,
  createApiClient,
  deleteApiClient,
  requestApiKey,
  rotateApiClient,
  splitOrigins,
  type ApiClient,
  type ApiClientCreateResponse,
  type ApiKeyRequest,
  type ApiSettings,
  type ApiClientScopeCatalog,
  updateApiClientScopes,
} from "./apiClientsApi";
import { ApiClientsAccessSummary } from "./ApiClientsAccessSummary";
import { SettingsLayout } from "../../components/layouts";
import { Modal } from "../../components/ui";
import { ApiClientSecretReveal } from "./ApiClientSecretReveal";
import { type Makerspace, useStaffGet } from "./StaffPanels";

export function ApiClientsPanel({
  makerspace,
  isSuperadmin,
  canManageMakerspace,
}: {
  makerspace: Makerspace;
  isSuperadmin: boolean;
  canManageMakerspace: boolean;
}) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [reason, setReason] = useState("");
  const [origins, setOrigins] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [oneTimeSecret, setOneTimeSecret] = useState<ApiClientCreateResponse | null>(null);
  // A rotated secret opens over the list, next to the action, rather than in the create
  // section above it where a show-once secret could appear off-screen.
  const [rotatedSecret, setRotatedSecret] = useState<ApiClientCreateResponse | null>(null);
  const requests = useStaffGet<{ results: ApiKeyRequest[] }>(
    apiKeyRequestsQueryKey(makerspace.id),
    `/admin/api-key-requests?makerspace=${makerspace.id}`,
    !canManageMakerspace,
  );
  const apiClients = useStaffGet<{ results: ApiClient[] }>(
    apiClientsQueryKey(makerspace.id),
    `/admin/makerspace/${makerspace.id}/api-clients`,
    canManageMakerspace,
  );
  const scopeOptions = useStaffGet<ApiClientScopeCatalog>(
    apiClientScopesQueryKey(makerspace.id),
    `/admin/makerspace/${makerspace.id}/api-client-scopes`,
    canManageMakerspace,
  );
  const settings = useStaffGet<ApiSettings>(
    apiSettingsQueryKey(makerspace.id),
    `/admin/makerspace/${makerspace.id}/api-settings`,
    isSuperadmin,
  );
  const catalog = scopeOptions.data?.results ?? [];
  const selectableCreateScopes = scopes.filter((scope) => (
    catalog.some((option) => option.value === scope && option.grantable)
  ));
  const requestKey = useMutation({
    mutationFn: () => requestApiKey(makerspace.id, label, reason, splitOrigins(origins)),
    onSuccess: () => {
      setLabel("");
      setReason("");
      setOrigins("");
      setSubmitted(true);
      queryClient.invalidateQueries({ queryKey: apiKeyRequestsQueryKey(makerspace.id) });
    },
  });
  const createClient = useMutation({
    mutationFn: () => createApiClient(
      makerspace.id,
      label,
      splitOrigins(origins),
      selectableCreateScopes,
    ),
    onSuccess: (created) => {
      setLabel("");
      setOrigins("");
      setScopes([]);
      setOneTimeSecret(created);
      queryClient.invalidateQueries({ queryKey: apiClientsQueryKey(makerspace.id) });
    },
  });
  const deleteClient = useMutation({
    mutationFn: deleteApiClient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiClientsQueryKey(makerspace.id) });
    },
  });
  const rotateClient = useMutation({
    mutationFn: rotateApiClient,
    onSuccess: (rotated) => {
      setRotatedSecret(rotated);
      queryClient.invalidateQueries({ queryKey: apiClientsQueryKey(makerspace.id) });
    },
  });
  const updateScopes = useMutation({
    mutationFn: ({ clientId, nextScopes }: { clientId: number; nextScopes: string[] }) => (
      updateApiClientScopes(clientId, nextScopes)
    ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: apiClientsQueryKey(makerspace.id) });
    },
  });
  const handleLabelChange = (value: string) => {
    setLabel(value);
    if (!canManageMakerspace) setSubmitted(false);
  };
  const handleReasonChange = (value: string) => {
    setReason(value);
    setSubmitted(false);
  };
  const handleOriginsChange = (value: string) => {
    setOrigins(value);
    if (!canManageMakerspace) setSubmitted(false);
  };
  return (<>
    <Modal open={Boolean(rotatedSecret)} onClose={() => setRotatedSecret(null)} title="New client secret">
      {rotatedSecret ? <ApiClientSecretReveal secret={rotatedSecret.client_secret} onDismiss={() => setRotatedSecret(null)} /> : null}
    </Modal>
    <SettingsLayout header={{ title: "API access", subtitle: `Let your own tools work with ${makerspace.name}, without sharing anyone’s login.` }}
      state={{ status: "ready" }} sections={[{ id: "new-client", title: canManageMakerspace ? "New API client" : "Request API access", rows: (<>
          <ApiClientCreateCard
            canManageMakerspace={canManageMakerspace}
            label={label}
            reason={reason}
            origins={origins}
            submitted={submitted}
            oneTimeSecret={oneTimeSecret}
            isPending={canManageMakerspace ? createClient.isPending : requestKey.isPending}
            error={canManageMakerspace ? createClient.error : requestKey.error}
            scopeOptions={catalog}
            scopes={selectableCreateScopes}
            scopesLoading={scopeOptions.isLoading}
            scopesError={scopeOptions.error}
            onRetryScopes={() => { void scopeOptions.refetch(); }}
            onLabelChange={handleLabelChange}
            onReasonChange={handleReasonChange}
            onOriginsChange={handleOriginsChange}
            onScopesChange={setScopes}
            onSubmit={() => canManageMakerspace ? createClient.mutate() : requestKey.mutate()}
            onDismissSecret={() => setOneTimeSecret(null)}
          />
          </>) }, { id: "clients", title: canManageMakerspace ? "Clients" : "Your requests", rows: (<>
          <ApiClientListCard
            canManageMakerspace={canManageMakerspace}
            clients={apiClients.data?.results}
            clientsLoading={apiClients.isLoading}
            clientsError={apiClients.error}
            onRetry={() => { void (canManageMakerspace ? apiClients.refetch() : requests.refetch()); }}
            requests={requests.data?.results}
            requestsLoading={requests.isLoading}
            requestsError={requests.error}
            deletePending={deleteClient.isPending}
            deleteError={deleteClient.error}
            rotatePending={rotateClient.isPending}
            rotateError={rotateClient.error}
            scopeOptions={catalog}
            scopesLoading={scopeOptions.isLoading}
            scopesError={scopeOptions.error}
            onRetryScopes={() => { void scopeOptions.refetch(); }}
            scopeUpdatePending={updateScopes.isPending}
            scopeUpdateError={updateScopes.error}
            onDelete={(clientId) => deleteClient.mutate(clientId)}
            onRotate={(clientId) => rotateClient.mutate(clientId)}
            onScopesUpdate={(clientId, nextScopes) => updateScopes.mutate({ clientId, nextScopes })}
          />
          </>) }, { id: "developer-reference", title: "Developer reference", rows: <ApiClientsAccessSummary makerspace={makerspace} isSuperadmin={isSuperadmin} settings={settings.data} loading={isSuperadmin && settings.isLoading} error={isSuperadmin ? settings.error : null} onRetry={() => { void settings.refetch(); }} /> }]} />
  </>);
}
