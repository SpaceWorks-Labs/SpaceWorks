import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { PAGE_SIZE } from "./parityRequest";
import { SsoProviderForm } from "./SsoProviderForm";
import { useOidcProviders, useUpdateOidcProvider, type OidcProvider } from "./ssoApi";

function ToggleDialog({ provider, onClose }: { provider: OidcProvider; onClose: () => void }) {
  const update = useUpdateOidcProvider(provider.id);
  const turningOff = provider.is_enabled;
  return <ActionDialog title={turningOff ? "Turn off this provider" : "Turn on this provider"}
    confirmLabel={turningOff ? "Turn off" : "Turn on"} tone={turningOff ? "danger" : "default"}
    pending={update.isPending} error={update.error} onCancel={onClose}
    message={turningOff
      ? `Nobody can sign in with ${provider.display_name} until it is turned on again. Linked sign-ins are kept.`
      : `People can sign in with ${provider.display_name} again, including everyone already linked to it.`}
    onSubmit={() => update.mutate({ is_enabled: !turningOff },
      { onSuccess: () => { toast(turningOff ? "Provider turned off." : "Provider turned on."); onClose(); } })} />;
}

/** OpenID Connect providers for the whole deployment. They can be turned off but never deleted. */
export function SsoSection() {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [toggling, setToggling] = useState<OidcProvider | null>(null);
  const list = useOidcProviders(page);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">
      Providers cannot be deleted, because people's linked sign-ins depend on them. Turn one off instead.
    </p>
    <CollapsibleSection title="New provider" open={adding} onToggle={() => setAdding(!adding)}><SsoProviderForm /></CollapsibleSection>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource="sign-on providers" onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message="No single sign-on providers yet." />
      : <div className="grid gap-3">{rows.map(provider => <ListRow key={provider.id} title={provider.display_name}
        meta={<>{provider.slug} · {provider.issuer} · client {provider.client_id}
          {provider.allow_auto_link ? " · links verified emails" : " · never links by email"}
          {" · changed "}<RelativeTime date={provider.updated_at} exact /></>}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={provider.is_enabled ? "On" : "Off"} tone={provider.is_enabled ? "success" : "neutral"} />
          <button type="button" className={provider.is_enabled ? "desk-button-danger-outline" : "desk-button"}
            aria-label={`${provider.is_enabled ? "Turn off" : "Turn on"} ${provider.display_name}`}
            onClick={() => setToggling(provider)}>{provider.is_enabled ? "Turn off…" : "Turn on…"}</button>
        </div>} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {toggling ? <ToggleDialog provider={toggling} onClose={() => setToggling(null)} /> : null}
  </div>;
}
