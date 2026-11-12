import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { EmptyState, ErrorText, Field, Pagination } from "../../../components/ui";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import type { DialogKind } from "./cardActions";
import { HealthCardView } from "./HealthCardView";
import { PlanAssignDialog } from "./PlanAssignDialog";
import { PurgeDialog } from "./PurgeDialog";
import { CapabilityPurgeDrawer } from "../platformSpaceKeys/CapabilityPurgeDrawer";
import { SpaceKeysDrawer } from "../platformSpaceKeys/SpaceKeysDrawer";
import { ScheduleDialog } from "./ScheduleDialog";
import { SimpleSpaceDialog, type SimpleAction } from "./SimpleSpaceDialog";
import { SpaceDetailDrawer } from "./SpaceDetailDrawer";
import { healthKey, listSpaceHealth, PAGE_SIZE, STATE_LABELS, type HealthCard, type SpaceState } from "./spacesApi";
import { TransferOwnershipDialog } from "./TransferOwnershipDialog";
import { BulkPlanAssign } from "./BulkPlanAssign";
import { BulkLimitsApply } from "./BulkLimitsApply";
import { LogoLoader } from "../../../components/LogoLoader";

function SpaceDialog({ card, kind, onClose }: { card: HealthCard; kind: DialogKind; onClose: () => void }) {
  if (kind === "transfer") return <TransferOwnershipDialog card={card} onClose={onClose} />;
  if (kind === "schedule") return <ScheduleDialog card={card} onClose={onClose} />;
  if (kind === "purge") return <PurgeDialog card={card} onClose={onClose} />;
  if (kind === "plan") return <PlanAssignDialog card={card} onClose={onClose} />;
  if (kind === "keys") return <SpaceKeysDrawer card={card} onClose={onClose} />;
  if (kind === "capabilities") return <CapabilityPurgeDrawer card={card} onClose={onClose} />;
  return <SimpleSpaceDialog card={card} action={kind as SimpleAction} onClose={onClose} />;
}

/** Every space's health at a glance, with the lifecycle controls behind each card's Manage menu. */
export function HealthSection({ managedPlans }: { managedPlans: boolean }) {
  const [search, setSearch] = useState("");
  const [state, setState] = useState("");
  const [page, setPage] = useState(1);
  const term = useDebouncedValue(search.trim(), 300);
  const list = useQuery({ queryKey: [...healthKey, state, term, page], queryFn: () => listSpaceHealth({ state, search: term, page }),
    placeholderData: keepPreviousData });
  const [dialog, setDialog] = useState<{ card: HealthCard; kind: DialogKind } | null>(null);
  const [details, setDetails] = useState<HealthCard | null>(null);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem]">
      <Field label={t`Search spaces`}>
        <input className="desk-input" type="search" value={search} placeholder={t`Name, slug or code`}
          onChange={event => { setSearch(event.target.value); setPage(1); }} />
      </Field>
      <Field label={t`State`}>
        <select className="desk-input" value={state} onChange={event => { setState(event.target.value); setPage(1); }}>
          <option value="">{t`Every state`}</option>
          {(Object.entries(STATE_LABELS()) as [SpaceState, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </Field>
    </div>
    {rows.length ? <div className="grid gap-3">
      {managedPlans ? <BulkPlanAssign cards={rows} /> : null}
      {/* Decision 284: limits apply to every space, own or hosted, so the bulk editor is never gated on plans. */}
      <BulkLimitsApply spaces={rows} />
    </div> : null}
    {list.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" />
      : list.isError ? <ErrorText resource={t`space health`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={term || state ? t`No spaces match these filters.` : t`No spaces yet.`} />
      : <div className="grid gap-4 xl:grid-cols-2">{rows.map(card => <HealthCardView key={card.id} card={card} managedPlans={managedPlans}
        onOpen={kind => setDialog({ card, kind })} onDetails={() => setDetails(card)} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {dialog ? <SpaceDialog card={dialog.card} kind={dialog.kind} onClose={() => setDialog(null)} /> : null}
    {details ? <SpaceDetailDrawer card={details} onClose={() => setDetails(null)} /> : null}
  </div>;
}
