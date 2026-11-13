import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { EmptyState, ErrorText, Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";
import { actionErrorText } from "./ActionDialog";
import { limitHint, limitLabel } from "./limitCopy";
import { useLimitDefaults, useSaveLimitDefaults, type LimitDefaultRow, type LimitDefaults } from "./limitDefaultsApi";
import { fromInput, groupLimits, toInput, validInput, type UnifiedLimit } from "./limitsModel";
import { SearchField } from "../../../components/ui/SearchField";

const asLimit = (row: LimitDefaultRow): UnifiedLimit => ({
  key: row.key, label: row.label, area: row.group || "other", unit: row.unit, limit: row.default, used: null, percent: null,
  level: "ok", stored: row.default ?? undefined, editable: true,
});

function DefaultRow({ row, value, onChange, disabled }: { row: UnifiedLimit; value: string; onChange: (value: string) => void; disabled: boolean }) {
  const label = limitLabel(row.key, row.label);
  return <li className="grid gap-x-6 gap-y-2 border-b border-line py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto]">
    <div className="grid min-w-0 gap-1">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <p className="text-xs text-muted">{limitHint(row.key)}</p>
    </div>
    <div className="flex items-center gap-2">
      <input className="desk-input w-32 tabular-nums" inputMode="numeric" aria-label={t`Platform default for ${label}`}
        aria-invalid={!validInput(value) || undefined} placeholder={t`Unlimited`} value={value} disabled={disabled}
        onChange={event => onChange(event.target.value)} />
      {row.unit === "bytes" ? <span className="text-xs text-muted">MB</span> : null}
    </div>
  </li>;
}

function DefaultsEditor({ data }: { data: LimitDefaults }) {
  const save = useSaveLimitDefaults();
  const rows = useMemo(() => data.rows.map(asLimit), [data.rows]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const needle = search.trim().toLowerCase();
  const shown = rows.filter(row => !needle || limitLabel(row.key, row.label).toLowerCase().includes(needle) || row.key.includes(needle));
  const groups = groupLimits(shown, data.groups);
  const changed = rows.filter(row => drafts[row.key] !== undefined && drafts[row.key].trim() !== toInput(row, row.stored));
  const invalid = Object.values(drafts).some(value => !validInput(value));
  const submit = () => save.mutate(
    Object.fromEntries(changed.map(row => [row.key, drafts[row.key].trim() === "" ? null : fromInput(row, drafts[row.key])])),
    { onSuccess: () => { setDrafts({}); toast(t`Platform defaults saved.`); } });
  return <div className="grid gap-5">
    <Field label={t`Search limits`}><SearchField className="desk-input" value={search} placeholder={t`Name of a limit`}
      onChange={event => setSearch(event.target.value)} /></Field>
    {needle && !groups.length ? <EmptyState message={t`No limits match this search.`} /> : null}
    {groups.map(group => <section key={group.key} aria-labelledby={`limit-defaults-${group.key}`} className="grid gap-1">
      <h3 id={`limit-defaults-${group.key}`} className="title-section">{group.label}</h3>
      <ul className="grid">{group.rows.map(row => <DefaultRow key={row.key} row={row} disabled={save.isPending}
        value={drafts[row.key] ?? toInput(row, row.stored)} onChange={value => setDrafts(current => ({ ...current, [row.key]: value }))} />)}</ul>
    </section>)}
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary min-h-11" disabled={invalid || !changed.length || save.isPending} onClick={submit}>
        {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save defaults`}</button>
      {changed.length ? <button type="button" className="desk-button-ghost min-h-11" disabled={save.isPending}
        onClick={() => setDrafts({})}>{t`Discard changes`}</button> : null}
    </div>
  </div>;
}

/**
 * Platform default limits (decision 328a), grouped by module like the module switch screens. Blank means
 * Unlimited, which is every key's starting point. A space's own limit wins over its default; a hosted
 * space's plan wins too. A default never touches existing data: it only stops something NEW at 100 %.
 */
export function LimitDefaultsSection() {
  const query = useLimitDefaults();
  if (query.isLoading) return <LogoLoader size={48} className="min-h-24 py-3" />;
  if (query.isError || !query.data || !Array.isArray(query.data.rows)) {
    return <ErrorText resource={t`default limits`} onRetry={() => { void query.refetch(); }} />;
  }
  return <DefaultsEditor key={JSON.stringify(query.data.rows.map(row => row.default))} data={query.data} />;
}
