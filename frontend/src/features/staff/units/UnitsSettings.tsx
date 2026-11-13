import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { EmptyState, ErrorText } from "../../../components/ui";
import { isSurfaceOff } from "../../../lib/api";
import { UnitEditDialog, type UnitEditTarget } from "./UnitEditDialog";
import { UnitLevelsEditor } from "./UnitLevelsEditor";
import { UnitMoveDialog } from "./UnitMoveDialog";
import { UnitTree } from "./UnitTree";
import { levelLabel } from "./unitHierarchy";
import { unitErrorText, unitKeys, unitsApi, useMemberUnits, type MemberUnit } from "./unitsApi";

/**
 * Districts, chapters and branches inside one space (parity O-B1): name the levels, build the tree,
 * move and archive units. `canManage` mirrors `manage_member_units`; without it, or for a unit-scoped
 * caller (`scoped`: the server sends only their subtree and refuses tree writes), the tree is read-only.
 * Hidden entirely while `membership.units` is off (the server's typed 404).
 */
export function UnitsSettings({ makerspaceId, canManage }: { makerspaceId: number; canManage: boolean }) {
  const client = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<UnitEditTarget | null>(null);
  const [moving, setMoving] = useState<MemberUnit | null>(null);
  const [notice, setNotice] = useState("");
  const list = useMemberUnits(makerspaceId, { archived: showArchived });
  const refresh = () => client.invalidateQueries({ queryKey: unitKeys.all(makerspaceId) });
  const done = (text: string) => { setNotice(text); void refresh(); };
  const move = useMutation({
    mutationFn: ({ unit, parentId }: { unit: MemberUnit; parentId: number | null }) => unitsApi.move(makerspaceId, unit.id, parentId),
    onMutate: () => setNotice(""),
    onSuccess: unit => {
      setMoving(null); done(t`${unit.name} moved.`);
      // A move changes which unit (and so which staff scope) every member below it sits in.
      void client.invalidateQueries({ queryKey: ["membership-l4", makerspaceId, "register"] });
      void client.invalidateQueries({ queryKey: ["members", makerspaceId] });
    },
  });
  const archive = useMutation({ mutationFn: (unit: MemberUnit) => unitsApi.archive(makerspaceId, unit.id),
    onMutate: () => setNotice(""), onSuccess: unit => done(t`${unit.name} archived.`) });
  const restore = useMutation({ mutationFn: (unit: MemberUnit) => unitsApi.restore(makerspaceId, unit.id),
    onMutate: () => setNotice(""), onSuccess: unit => done(t`${unit.name} restored.`) });
  if (isSurfaceOff(list.error)) return null;
  if (list.isPending) return <LogoLoader label={t`Loading units…`} size={48} className="min-h-16 py-3" />;
  if (list.isError) return <ErrorText message={unitErrorText(list.error)} onRetry={() => void list.refetch()} />;
  const { units, levels, templates, limit, used, scoped } = list.data;
  const editable = canManage && !scoped;
  const full = limit !== null && used >= limit;
  const topKind = levelLabel(levels, 0, () => t`unit`);
  const actionError = (moving ? null : move.error) ?? archive.error ?? restore.error;
  const add = editable ? <button type="button" className="desk-button-primary min-h-11" disabled={full}
    title={full ? t`This space has reached its allowance of units.` : undefined}
    onClick={() => setEditing({ kind: "create", parent: null })}>{t`Add ${topKind}`}</button> : null;
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted">
        {limit === null ? t`${used} active units` : t`${used} of ${limit} units used`}
        {scoped ? ` · ${t`You see only your own unit and the units beneath it.`}` : ""}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent"
          checked={showArchived} onChange={event => setShowArchived(event.target.checked)} />{t`Show archived`}</label>
        {units.length ? add : null}
      </div>
    </div>
    {editable ? <UnitLevelsEditor key={levels.join("\u0000")} makerspaceId={makerspaceId} levels={levels} templates={templates} /> : null}
    {notice ? <p role="status" className="text-sm text-ink">{notice}</p> : null}
    {actionError ? <ErrorText message={unitErrorText(actionError)} /> : null}
    {units.length ? <UnitTree units={units} levels={levels} editable={editable} busy={move.isPending || archive.isPending || restore.isPending}
      actions={{
        onEdit: unit => setEditing({ kind: "edit", unit }), onAddChild: unit => setEditing({ kind: "create", parent: unit }),
        onMove: unit => { move.reset(); setMoving(unit); }, onDropMove: (unit, parentId) => move.mutate({ unit, parentId }),
        onArchive: unit => archive.mutate(unit), onRestore: unit => restore.mutate(unit),
      }} />
      : <EmptyState title={editable ? t`Add your first ${topKind.toLocaleLowerCase()}` : t`No units yet`}
        description={editable ? t`Group members into areas, districts, chapters or branches. Plans, staff and payment instructions can then follow a unit.` : t`A Space Manager sets up this space's units.`}
        action={add} />}
    {editing ? <UnitEditDialog key={editing.kind === "edit" ? editing.unit.id : `new-${editing.parent?.id ?? "top"}`}
      makerspaceId={makerspaceId} target={editing} units={units} levels={levels} onClose={() => setEditing(null)}
      onSaved={unit => { setEditing(null); done(editing.kind === "edit" ? t`${unit.name} saved.` : t`${unit.name} added with code ${unit.code}.`); }} /> : null}
    {moving ? <UnitMoveDialog unit={moving} units={units} levels={levels} pending={move.isPending}
      error={move.error ? unitErrorText(move.error) : undefined} onClose={() => setMoving(null)}
      onMove={parentId => move.mutate({ unit: moving, parentId })} /> : null}
  </div>;
}
