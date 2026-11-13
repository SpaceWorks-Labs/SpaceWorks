import { t } from "@lingui/core/macro";

import { Field } from "../../../../../components/ui";
import { targetTypeLabel } from "./adapterCopy";
import type { TargetType } from "./adaptersApi";
import { useTargetOptions } from "./bindingTargets";

/** What a shelf pointer can aim at: storage locations, items and boxes (staff only; poses never reach public pages). */
export const POINTER_TARGETS: TargetType[] = ["storage_location", "item", "box"];

export function PointerTargetSelect({ makerspaceId, type, onType, value, onValue }: {
  makerspaceId: number; type: TargetType; onType: (type: TargetType) => void; value: string; onValue: (value: string) => void;
}) {
  const { options, loading } = useTargetOptions(makerspaceId, type);
  return <div className="grid gap-4 sm:grid-cols-2">
    <Field label={t`Aim at`}>
      <select className="desk-input" value={type} onChange={event => { onType(event.target.value as TargetType); onValue(""); }}>
        {POINTER_TARGETS.map(row => <option key={row} value={row}>{targetTypeLabel(row)}</option>)}</select></Field>
    <Field label={targetTypeLabel(type)}>
      <select className="desk-input" value={value} disabled={loading} onChange={event => onValue(event.target.value)}>
        <option value="">{loading ? t`Loading…` : t`Choose…`}</option>
        {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>
  </div>;
}
