import { t } from "@lingui/core/macro";

import { UnitPicker } from "./UnitPicker";

export type ImportUnitChoice = { unitId: number | null; verify: boolean };

/**
 * Import options from parity O-B1: land every imported row in one unit and, in verify mode, hold the
 * rows for that unit's lead to approve before any invitation is sent (Members › Units › Import review).
 */
export function ImportUnitFields({ makerspaceId, value, onChange }: {
  makerspaceId: number; value: ImportUnitChoice; onChange: (value: ImportUnitChoice) => void;
}) {
  return <fieldset className="grid gap-3 rounded-xl border border-line p-4">
    <legend className="px-1 text-sm font-semibold text-ink">{t`Unit`}</legend>
    <UnitPicker makerspaceId={makerspaceId} value={value.unitId} label={t`Put everyone in`} noneLabel={t`No unit`}
      onChange={unitId => onChange({ unitId, verify: unitId === null ? false : value.verify })} />
    <label className="flex min-h-11 items-start gap-3 text-sm">
      <input type="checkbox" className="mt-0.5 h-5 w-5 accent-accent" checked={value.verify} disabled={value.unitId === null}
        onChange={event => onChange({ ...value, verify: event.target.checked })} />
      <span className="grid gap-0.5"><span className="text-ink">{t`Ask the unit lead to approve each row first`}</span>
        <span className="text-muted">{value.unitId === null ? t`Choose a unit to turn this on.` : t`Nobody is invited until the lead approves their row.`}</span></span>
    </label>
  </fieldset>;
}

/** The import form fields the server reads (`unit_id`, `verify`); nothing is sent without a unit. */
export function appendImportUnit(body: FormData, value: ImportUnitChoice) {
  if (value.unitId === null) return body;
  body.append("unit_id", String(value.unitId));
  if (value.verify) body.append("verify", "true");
  return body;
}
