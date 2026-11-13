import { t } from "@lingui/core/macro";
import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, StatusPill } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { actionErrorText } from "../../platformSpaces/ActionDialog";
import { PAGE_SIZE } from "../../platformParity/parityRequest";
import { TypedConfirmDialog } from "../../platformSpaceKeys/TypedConfirmDialog";
import { OffsiteDestinationForm } from "./OffsiteDestinationForm";
import { OffsiteUploads } from "./OffsiteUploads";
import { useDestinations, useProbeDestination, usePushNow, useRetireDestination, type Destination } from "./offsiteApi";
import { LogoLoader } from "../../../../components/LogoLoader";
import { BoxArt } from "../../../../components/BoxSpinner";

function RetireDialog({ destination, onClose }: { destination: Destination; onClose: () => void }) {
  const retire = useRetireDestination();
  return <TypedConfirmDialog title={t`Retire ${destination.name}`} confirmLabel={t`Retire destination`} expected={destination.name}
    what={t`destination name`} pending={retire.isPending} error={retire.error} onCancel={onClose}
    message={t`Pushing stops and the stored keys are wiped. Copies already in the bucket stay there; the journal is kept. This cannot be undone: register a new destination to resume.`}
    onConfirm={() => retire.mutate(destination.id, { onSuccess: () => { toast(t`Destination retired.`); onClose(); } })} />;
}

function DestinationRow({ destination, onRetire }: { destination: Destination; onRetire: () => void }) {
  const [panel, setPanel] = useState<"edit" | "uploads" | null>(null);
  const probe = useProbeDestination();
  const retired = Boolean(destination.retired_at);
  const where = [destination.endpoint_url || "AWS S3", destination.bucket + (destination.prefix ? `/${destination.prefix}` : "")].join(" · ");
  const test = () => probe.mutate(destination.id, { onSuccess: result => toast(result.ok ? t`Write, read-back and delete all worked.` : t`Test failed: ${result.error_code}`) });
  return <div className="grid gap-2 rounded-xl border border-line bg-panel p-3">
    <ListRow title={destination.name}
      meta={<>{where}{t` · keeps ${destination.retention_days} days`}
        {destination.last_success_at ? <>{t` · last copy `}<RelativeTime date={destination.last_success_at} exact /></> : t` · no copy yet`}</>}
      right={<div className="flex flex-wrap items-center gap-2">
        <StatusPill label={retired ? t`Retired` : destination.enabled ? t`Pushing` : t`Paused`} tone={retired ? "neutral" : destination.enabled ? "success" : "warn"} />
        {destination.last_error_code && !retired ? <StatusPill label={t`Error: ${destination.last_error_code}`} tone="danger" /> : null}
      </div>} />
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button" aria-expanded={panel === "uploads"} onClick={() => setPanel(panel === "uploads" ? null : "uploads")}>{t`Copies`}</button>
      {retired ? null : <>
        <button type="button" className="desk-button" disabled={probe.isPending} onClick={test}>{probe.isPending ? <><BoxArt size={16} mono />{t`Testing…`}</> : t`Test`}</button>
        <button type="button" className="desk-button" aria-expanded={panel === "edit"} onClick={() => setPanel(panel === "edit" ? null : "edit")}>{t`Edit`}</button>
        <button type="button" className="desk-button-danger-outline" onClick={onRetire}>{t`Retire…`}<span className="sr-only"> {destination.name}</span></button>
      </>}
    </div>
    {probe.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(probe.error)}</p> : null}
    {panel === "edit" ? <OffsiteDestinationForm destination={destination} onDone={() => setPanel(null)} /> : null}
    {panel === "uploads" ? <OffsiteUploads destination={destination} /> : null}
  </div>;
}

/** Offsite copies of every encrypted backup to S3-compatible buckets (deployment-wide; /control/ had it only). */
export function OffsiteDestinationsSection() {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [retiring, setRetiring] = useState<Destination | null>(null);
  const list = useDestinations(page);
  const push = usePushNow();
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`Backups are already encrypted to the platform key; each destination keeps a second copy off this server. Keys are stored encrypted and never shown again.`}</p>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button" disabled={push.isPending || !rows.some(row => row.enabled && !row.retired_at)}
        onClick={() => push.mutate(undefined, { onSuccess: () => toast(t`Offsite push started.`) })}>{push.isPending ? <><BoxArt size={16} mono />{t`Starting…`}</> : t`Push now`}</button>
      {push.error ? <span role="alert" className="text-sm text-danger">{actionErrorText(push.error)}</span> : null}
    </div>
    <CollapsibleSection title={t`New destination`} open={adding} onToggle={() => setAdding(!adding)}>
      <OffsiteDestinationForm key={String(adding)} onDone={() => setAdding(false)} />
    </CollapsibleSection>
    {list.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" />
      : list.isError ? <ErrorText resource={t`offsite destinations`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No offsite destination yet. Add one so a lost server does not take its backups with it.`} />
      : <div className="grid gap-3">{rows.map(row => <DestinationRow key={row.id} destination={row} onRetire={() => setRetiring(row)} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {retiring ? <RetireDialog destination={retiring} onClose={() => setRetiring(null)} /> : null}
  </div>;
}
