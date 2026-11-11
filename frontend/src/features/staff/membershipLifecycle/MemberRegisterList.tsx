import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState, type Key } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { DataTable, StatusPill, type DataTableColumn } from "../../../components/ui";
import { ListFilters } from "../../../components/layouts/ListFilters";
import { StructuredApiError, staffRequestBlob } from "../../../lib/api";
import { useUrlListState } from "../../../lib/useUrlListState";
import { SavedViewsMenu } from "../SavedViewsMenu";
import { STANDING_LABELS, lifecycleApi, lifecycleKeys, standingTone, type RegisterRow, type RowResult } from "../membershipLifecycleApi";
import { RegisterBulkBar, RegisterBulkResults, type BulkAbilities } from "./RegisterBulkBar";
import { RegisterFilters } from "./RegisterFilters";
import { REGISTER_FILTER_DEFAULTS, activeRegisterFilters, chipFromStanding, registerChips, registerFilterParams, registerQuery, rowResultLabel, type RegisterFilterValues } from "./registerModel";

const ROW_CAP = 2000;
const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`Couldn't load the register.`);
const day = (value: string | null) => (value ? new Date(value).toLocaleDateString(formatLocale()) : "—");

/**
 * The member register (X14, parity O-B2): one view of everyone with a membership here, narrowed by a
 * standing chip, a search (name, email or member number) and the shared filters, with saved views, the
 * CSV export, and bulk actions with a result for every row. Filters live in the address, so a view can be
 * shared or saved. A unit-scoped staff member only ever sees their unit (the server narrows every query).
 */
export function MemberRegisterList({ makerspaceId, initialStanding = "", features = [], canManageCards = false }: {
  makerspaceId: number; initialStanding?: string; features?: string[]; canManageCards?: boolean;
}) {
  const on = (key: string) => features.includes(`membership.${key}`);
  const list = useUrlListState({ ...REGISTER_FILTER_DEFAULTS, chip: chipFromStanding(initialStanding) }, "reg.");
  const values = list.values as RegisterFilterValues & Record<string, string>;
  const query = registerQuery(values);
  const register = useQuery({ queryKey: lifecycleKeys.registerFiltered(makerspaceId, query),
    queryFn: () => lifecycleApi.registerFiltered(makerspaceId, query), placeholderData: keepPreviousData });
  const [selected, setSelected] = useState<Key[]>([]);
  const [results, setResults] = useState<RowResult[] | null>(null);
  const exportCsv = useMutation({
    mutationFn: () => staffRequestBlob(`/admin/makerspace/${makerspaceId}/reports/member-register/export?format=csv`),
    onSuccess: (blob) => {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "member-register.csv";
      link.click();
      URL.revokeObjectURL(link.href);
    },
  });
  const can: BulkAbilities = { titles: on("titles"), units: on("units"), reminders: on("renewal_desk"), cards: canManageCards };
  const bulkOn = on("register_bulk") && Object.values(can).some(Boolean);
  const rows = register.data ?? [];
  const masked = rows.some((row) => row.pii_masked);
  const outcome = new Map((results ?? []).map((item) => [item.id, item]));
  const setFilter = (key: string, value: string) => { setSelected([]); list.setFilter(key, value); };
  const columns: DataTableColumn<RegisterRow>[] = [
    { key: "name", header: t`Member`, sortable: true, render: (row) => <span className="grid min-w-0">
      <span className="truncate font-semibold text-ink">{row.name || row.email || t`Member`}</span>
      {row.email && row.name ? <span className="truncate text-xs text-muted">{row.email}</span> : null}</span> },
    { key: "member_number", header: t`Number`, sortable: true, render: (row) => <span className="tabular-nums">{row.member_number || "—"}</span> },
    ...(on("units") ? [{ key: "unit", header: t`Unit`, render: (row: RegisterRow) => row.unit || "—" }] : []),
    { key: "plan", header: t`Plan`, sortable: true, render: (row) => row.plan || t`No plan` },
    { key: "status", header: t`Standing`, render: (row) => <StatusPill tone={standingTone(row.standing)} label={STANDING_LABELS[row.standing] ?? row.standing} /> },
    { key: "term_ends_at", header: t`Term ends`, sortable: true, render: (row) => <span className="tabular-nums">{day(row.term_ends_at)}</span> },
    { key: "joined_at", header: t`Joined`, sortable: true, render: (row) => <span className="tabular-nums">{day(row.joined_at)}</span> },
    ...(results ? [{ key: "result", header: t`Last action`, render: (row: RegisterRow) => {
      const item = outcome.get(row.membership_id);
      return item ? <StatusPill tone={item.ok ? "success" : "warn"} label={rowResultLabel(item.ok ? "" : item.code)} /> : "—";
    } }] : []),
  ];
  return <section aria-label={t`Member register`} className="grid min-w-0 gap-3">
    <ListFilters
      search={{ label: t`Search by name, email or member number`, value: values.q, onChange: (value) => setFilter("q", value) }}
      controls={<RegisterFilters makerspaceId={makerspaceId} values={values} onChange={setFilter} titlesOn={on("titles")} unitsOn={on("units")} />}
      activeCount={activeRegisterFilters(values)}
      views={<SavedViewsMenu makerspaceId={makerspaceId} entity="members" state={values} onRestore={list.restore} />} />
    <div role="group" aria-label={t`Standing`} className="flex flex-wrap gap-2">
      {[{ key: "", label: t`Everyone` }, ...registerChips(on("ask_changes"))].map((chip) => {
        const pressed = values.chip === chip.key;
        return <button key={chip.key || "all"} type="button" aria-pressed={pressed} onClick={() => setFilter("chip", chip.key)}
          className={`min-h-11 rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${pressed ? "border-accent bg-accent-soft text-accent-ink" : "border-line bg-panel text-ink hover:bg-hover"}`}>
          {chip.label}</button>;
      })}
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted" role="status">{register.isSuccess
        ? rows.length >= ROW_CAP ? t`Showing the first ${ROW_CAP} members. Narrow the filters, or export the full register.` : t`${rows.length} members`
        : ""}</p>
      <button className="desk-button" type="button" disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>
        {exportCsv.isPending ? t`Preparing…` : t`Export CSV`}</button>
    </div>
    {masked ? <p className="text-sm text-muted">{t`Names and emails are hidden. Open a personal-data access window to see them.`}</p> : null}
    {exportCsv.error ? <p role="alert" className="text-sm text-danger">{errorText(exportCsv.error)}</p> : null}
    {register.isError ? <p role="alert" className="text-sm text-danger">{errorText(register.error)}</p> : null}
    {bulkOn ? <RegisterBulkBar makerspaceId={makerspaceId} selected={selected.map(Number)} can={can} matchCount={rows.length} filter={registerFilterParams(values)} onClear={() => setSelected([])}
      onResults={(next) => { setResults(next); setSelected([]); }} /> : null}
    {results ? <RegisterBulkResults results={results} rows={rows} onDismiss={() => setResults(null)} /> : null}
    {register.isError ? null : <DataTable caption={t`Members`} columns={columns} data={rows} loading={register.isLoading} skeletonCols={6}
      getRowId={(row) => row.membership_id} {...(bulkOn ? { selectedIds: selected, onSelectionChange: setSelected } : {})}
      emptyTitle={values.chip || query ? t`Nobody matches these filters.` : t`No members yet.`}
      emptyDescription={values.chip || query ? t`Try another standing, or clear a filter.` : undefined} />}
  </section>;
}
