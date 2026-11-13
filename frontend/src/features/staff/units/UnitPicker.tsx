import { t } from "@lingui/core/macro";

import { ErrorText, Field } from "../../../components/ui";
import { isSurfaceOff } from "../../../lib/api";
import { orderedUnits } from "./unitHierarchy";
import { unitErrorText, useMemberUnits, type MemberUnit } from "./unitsApi";

export type UnitPickerProps = {
  makerspaceId: number;
  value: number | null;
  onChange: (unitId: number | null) => void;
  label?: string;
  hint?: string;
  /** Shown as the empty choice; omit it to make a unit required. */
  noneLabel?: string;
  disabled?: boolean;
  /** Units that may not be chosen (for a move: the unit's own subtree and levels too deep). */
  isDisabled?: (unit: MemberUnit) => boolean;
  /** Already-loaded units (the tree editor passes its own list); otherwise the picker loads them. */
  units?: readonly MemberUnit[];
};

const INDENT = "\u2003";

/**
 * The one unit picker every screen uses (member unit, staff scope, invite links, import, move). It
 * lists what the server returns for this caller, so a unit-scoped staff member is only ever offered
 * their own subtree. Archived units are never offered, except the current value so it still reads.
 * While `membership.units` is off the server answers a typed 404 and the picker renders nothing.
 */
export function UnitPicker({ makerspaceId, value, onChange, label = t`Unit`, hint, noneLabel, disabled = false, isDisabled, units }: UnitPickerProps) {
  const query = useMemberUnits(makerspaceId, { enabled: !units });
  if (!units && isSurfaceOff(query.error)) return null;
  const source = units ?? query.data?.units ?? [];
  const rows = orderedUnits(source).filter(unit => !unit.archived || unit.id === value);
  const loading = !units && query.isPending;
  return <div className="grid gap-1">
    <Field label={label} hint={hint}>
      <select className="desk-input max-w-full" value={value ?? ""} disabled={disabled || loading}
        onChange={event => onChange(event.target.value ? Number(event.target.value) : null)}>
        {loading ? <option value="">{t`Loading units…`}</option> : null}
        {!loading && (noneLabel !== undefined || value === null) ? <option value="">{noneLabel ?? t`Choose a unit`}</option> : null}
        {rows.map(unit => <option key={unit.id} value={unit.id} disabled={unit.archived || isDisabled?.(unit)}>
          {`${INDENT.repeat(unit.depth)}${unit.name} · ${unit.code}${unit.archived ? ` (${t`archived`})` : ""}`}
        </option>)}
      </select>
    </Field>
    {!units && query.isError ? <ErrorText message={unitErrorText(query.error)} onRetry={() => void query.refetch()} /> : null}
    {!loading && !units && query.isSuccess && !rows.length ? <p className="text-sm text-muted">{t`No units yet. A Space Manager adds them under Settings › Member units.`}</p> : null}
  </div>;
}
