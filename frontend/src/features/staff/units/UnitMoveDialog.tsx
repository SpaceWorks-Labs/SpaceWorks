import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorText, Modal } from "../../../components/ui";
import { UnitPicker } from "./UnitPicker";
import { canMoveUnder } from "./unitHierarchy";
import type { MemberUnit } from "./unitsApi";
import { BoxArt } from "../../../components/BoxSpinner";

/**
 * The keyboard and touch way to move a unit (drag-and-drop is the pointer shortcut). Only parents the
 * move can land under are offered: never the unit's own subtree, an archived unit, or a level deeper
 * than the space has named. The whole subtree moves with it.
 */
export function UnitMoveDialog({ unit, units, levels, pending, error, onClose, onMove }: {
  unit: MemberUnit; units: readonly MemberUnit[]; levels: readonly string[]; pending: boolean; error?: string;
  onClose: () => void; onMove: (parentId: number | null) => void;
}) {
  const [parentId, setParentId] = useState<number | null>(unit.parent_id);
  const topAllowed = canMoveUnder(units, levels, unit.id, null);
  const allowed = parentId === null ? topAllowed : canMoveUnder(units, levels, unit.id, parentId);
  const unchanged = parentId === unit.parent_id;
  return <Modal open title={t`Move ${unit.name}`} onClose={() => { if (!pending) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (allowed && !unchanged && !pending) onMove(parentId); }}>
      <p className="text-sm text-muted">{t`Everything under ${unit.name} moves with it. Members keep their unit.`}</p>
      <UnitPicker makerspaceId={0} units={units} value={parentId} onChange={setParentId} label={t`New parent`}
        noneLabel={topAllowed ? t`Top level (no parent)` : t`Top level is not possible here`}
        isDisabled={candidate => !canMoveUnder(units, levels, unit.id, candidate.id)}
        hint={t`Greyed-out units would put it inside itself or deeper than your named levels.`} />
      {!allowed && !unchanged ? <p className="text-sm text-danger">{t`It can't move there.`}</p> : null}
      {error ? <ErrorText message={error} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button min-h-11" disabled={pending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-primary min-h-11" disabled={pending || unchanged || !allowed}>{pending ? <><BoxArt size={16} mono />{t`Moving…`}</> : t`Move unit`}</button>
      </div>
    </form>
  </Modal>;
}
