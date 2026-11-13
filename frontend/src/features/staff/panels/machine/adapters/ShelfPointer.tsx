import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Callout, Field } from "../../../../../components/ui";
import type { AdapterSummary } from "./adaptersApi";
import { useTargetLabel } from "./bindingTargets";
import { ShelfCalibrate } from "./ShelfCalibrate";
import { ShelfIndicate, ShelfWalk } from "./ShelfWalk";
import { ShelfPointerLimits } from "./ShelfPointerLimits";

type Mode = "indicate" | "calibrate" | "walk" | "limits";

/** The shelf pointer: point at a place, calibrate where each place is, and walk the shelves one by one. Staff only. */
export function ShelfPointer({ makerspaceId, adapter }: { makerspaceId: number; adapter: AdapterSummary }) {
  const pointers = adapter.bindings.filter(binding => binding.capabilities.includes("locate.calibrate") || binding.capabilities.includes("locate.indicate"));
  const label = useTargetLabel(makerspaceId, pointers);
  const [bindingId, setBindingId] = useState(pointers[0]?.id ?? "");
  const [mode, setMode] = useState<Mode>("indicate");
  const binding = pointers.find(row => row.id === bindingId) ?? pointers[0];
  if (!binding) return <p className="text-sm text-muted">{t`No shelf pointer is bound to this adapter.`}</p>;
  const canIndicate = binding.capabilities.includes("locate.indicate");
  const canCalibrate = binding.capabilities.includes("locate.calibrate");
  const modes: { key: Mode; label: string }[] = [...(canIndicate ? [{ key: "indicate" as const, label: t`Indicate` }, { key: "walk" as const, label: t`Walk the shelves` }] : []),
    ...(canCalibrate ? [{ key: "calibrate" as const, label: t`Calibrate` }] : []), { key: "limits" as const, label: t`Laser limits` }];
  const active = modes.some(row => row.key === mode) ? mode : modes[0].key;
  return <div className="grid gap-4">
    <Callout size="inline" tone="warn" lead={t`Staff only.`} body={t`Saved positions and what the pointer is aimed at are never shown to the public.`} />
    {pointers.length > 1 ? <Field label={t`Pointer`}><select className="desk-input" value={binding.id} onChange={event => setBindingId(event.target.value)}>
      {pointers.map(row => <option key={row.id} value={row.id}>{label(row.target_type, row.machine_id, row.target_id, row.external_ref)}</option>)}</select></Field> : null}
    <div className="flex flex-wrap gap-2" role="group" aria-label={t`Pointer mode`}>
      {modes.map(row => <button key={row.key} type="button" className={active === row.key ? "desk-button-primary" : "desk-button"} aria-pressed={active === row.key}
        onClick={() => setMode(row.key)}>{row.label}</button>)}</div>
    {active === "indicate" ? <ShelfIndicate makerspaceId={makerspaceId} binding={binding} /> : null}
    {active === "walk" ? <ShelfWalk makerspaceId={makerspaceId} binding={binding} /> : null}
    {active === "limits" ? <ShelfPointerLimits makerspaceId={makerspaceId} binding={binding} /> : null}
    {active === "calibrate" ? <ShelfCalibrate makerspaceId={makerspaceId} binding={binding} /> : null}
  </div>;
}
