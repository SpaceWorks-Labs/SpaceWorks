import { plural, t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { Field } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api/errors";
import { actionErrorText } from "./ActionDialog";
import { limitLabel } from "./limitCopy";
import { fromInput, groupLimits, unifyLimits, validInput } from "./limitsModel";
import { useBulkSpaceLimits, useSpaceLimits } from "./limitsApi";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

const LIMIT = 50;
type Space = { id: number; name: string };
type Change = { key: string; value: string };

/**
 * Decision 284: set or clear the same limits on up to 50 spaces at once, all or nothing, after a recent
 * sign-in. The limit list comes from the first space's own payload, so new server keys appear here too.
 * A blank value resets that limit to none on every chosen space.
 */
export function BulkLimitsApply({ spaces }: { spaces: Space[] }) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<number[]>([]);
  const [changes, setChanges] = useState<Change[]>([{ key: "", value: "" }]);
  const offered = spaces.slice(0, LIMIT);
  const catalogue = useSpaceLimits(offered[0]?.id ?? 0, open);
  const rows = useMemo(() => catalogue.data ? unifyLimits(catalogue.data).filter(row => row.editable) : [], [catalogue.data]);
  const groups = useMemo(() => groupLimits(rows, catalogue.data?.areas), [rows, catalogue.data?.areas]);
  const apply = useBulkSpaceLimits();
  if (!offered.length) return null;
  const selected = picked.filter(id => offered.some(space => space.id === id));
  const chosen = changes.filter(change => change.key);
  const valid = chosen.length > 0 && chosen.every(change => validInput(change.value))
    && new Set(chosen.map(change => change.key)).size === chosen.length;
  const submit = () => {
    const set: Record<string, number> = {};
    const clear: string[] = [];
    for (const change of chosen) {
      const row = rows.find(item => item.key === change.key);
      if (!change.value.trim()) clear.push(change.key);
      else set[change.key] = row ? fromInput(row, change.value) : Number(change.value);
    }
    apply.mutate({ makerspace_ids: selected, set, clear }, { onSuccess: () => { setPicked([]); setChanges([{ key: "", value: "" }]); } });
  };
  const error = apply.error;
  const failed = error instanceof StructuredApiError && error.status === 409 && typeof error.body.failed_id === "number"
    ? t`No limits changed. ${offered.find(space => space.id === error.body.failed_id)?.name ?? t`Space #${String(error.body.failed_id)}`} was refused: ${typeof error.body.cause === "string" ? error.body.cause : error.message}`
    : error ? actionErrorText(error) : "";
  const edit = (index: number, patch: Partial<Change>) => setChanges(current => current.map((item, at) => at === index ? { ...item, ...patch } : item));
  return <div className="grid gap-2">
    <button type="button" className="desk-button min-h-11 w-fit" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {open ? t`Close bulk limits` : t`Set limits on several spaces`}</button>
    {open ? <fieldset className="grid gap-4 rounded-xl border border-line bg-panel p-3" disabled={apply.isPending}>
      <legend className="title-section px-1">{t`Spaces on this page`}</legend>
      <label className="flex min-h-11 items-center gap-2 text-sm font-semibold">
        <input type="checkbox" className="h-4 w-4" checked={selected.length === offered.length}
          onChange={event => setPicked(event.target.checked ? offered.map(space => space.id) : [])} />{t`Select all ${offered.length}`}
      </label>
      <ul className="grid gap-1 sm:grid-cols-2">{offered.map(space => <li key={space.id}><label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4" checked={selected.includes(space.id)}
          onChange={() => setPicked(current => current.includes(space.id) ? current.filter(id => id !== space.id) : [...current, space.id])} />{space.name}
      </label></li>)}</ul>
      <div className="grid gap-2">
        <p className="text-sm font-semibold text-ink">{t`Limits to change`}</p>
        <p className="text-xs text-muted">{t`Leave a value empty to reset that limit to none. Storage is in MB; money in whole currency units, per currency.`}</p>
        {catalogue.isLoading ? <LogoLoader label={t`Loading limits…`} size={48} className="min-h-16 py-3" /> : null}
        {changes.map((change, index) => <div key={index} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
          <Field label={t`Limit ${index + 1}`}><select className="desk-input w-full" value={change.key} onChange={event => edit(index, { key: event.target.value })}>
            <option value="">{t`Choose a limit`}</option>
            {groups.map(group => <optgroup key={group.key} label={group.label}>
              {group.rows.map(row => <option key={row.key} value={row.key}>{limitLabel(row.key, row.label)}</option>)}</optgroup>)}
          </select></Field>
          <Field label={t`New value ${index + 1}`}><input className="desk-input w-full tabular-nums" inputMode="numeric" placeholder={t`No limit`}
            value={change.value} onChange={event => edit(index, { value: event.target.value })} /></Field>
          <button type="button" className="desk-button-ghost min-h-11" disabled={changes.length === 1}
            onClick={() => setChanges(current => current.filter((_, at) => at !== index))}>{t`Remove`}</button>
        </div>)}
        <button type="button" className="desk-button-ghost min-h-11 w-fit" onClick={() => setChanges(current => [...current, { key: "", value: "" }])}>{t`Add another limit`}</button>
      </div>
      <button type="button" className="desk-button-primary min-h-11 w-fit" disabled={!selected.length || !valid || apply.isPending} onClick={submit}>
        {apply.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : plural(selected.length, { one: "Apply to # space", other: "Apply to # spaces" })}</button>
      {apply.isSuccess ? <p role="status" className="text-sm text-muted">{plural(apply.data.updated, { one: "Limits changed on # space.", other: "Limits changed on # spaces." })}</p> : null}
      {failed ? <p role="alert" className="text-sm text-danger">{failed}</p> : null}
    </fieldset> : null}
  </div>;
}
