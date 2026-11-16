import { t } from "@lingui/core/macro";
import { useId } from "react";

import { publicUnitRows, type PublicUnits } from "./joinUnitsApi";

const INDENT = "\u2003";

/**
 * The unit an applicant joins (parity O-B1): preselected from a `?unit=CODE` link, otherwise chosen
 * here. Choosing a unit narrows the plans to the ones offered in it. Optional: an invite link's unit,
 * or the person's existing unit, applies when none is chosen.
 */
export function JoinUnitNotice({ data, code, linkCode, settling = false, onChange }: {
  data: PublicUnits; code: string; linkCode: string; onChange: (code: string) => void;
  /** True while the answer for `code` is still loading (the previous one is shown meanwhile). */
  settling?: boolean;
}) {
  const id = useId();
  const rows = publicUnitRows(data.units);
  if (!rows.length) return null;
  const selected = data.selected && data.selected.code === code ? data.selected : null;
  const top = data.levels[0]?.trim();
  const label = top ? t`Your ${top}` : t`Your unit`;
  return <div className="mt-3 grid gap-2">
    {selected && code === linkCode ? <p role="status" className="text-sm text-ink">
      {selected.level_name ? t`You are joining ${selected.name} (${selected.level_name}).` : t`You are joining ${selected.name}.`}</p> : null}
    {linkCode && code === linkCode && !selected && !settling ? <p role="alert" className="text-sm text-danger">{t`That unit link is no longer valid. Choose your unit below.`}</p> : null}
    <label htmlFor={id} className="text-sm font-semibold text-ink">{label}</label>
    <select id={id} className="desk-input max-w-full" value={rows.some(row => row.code === code) ? code : ""} onChange={event => onChange(event.target.value)}>
      <option value="">{t`I'm not sure yet`}</option>
      {rows.map(unit => <option key={unit.code} value={unit.code}>
        {`${INDENT.repeat(unit.depth)}${unit.name}${unit.level_name ? ` · ${unit.level_name}` : ""}`}</option>)}
    </select>
    {selected && data.plan_ids !== null ? <p className="text-sm text-muted">{t`Showing the plans offered in ${selected.name}.`}</p> : null}
  </div>;
}
