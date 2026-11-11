import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ErrorText, Field, Modal } from "../../../components/ui";
import { levelLabel } from "./unitHierarchy";
import { unitErrorText, unitKeys, unitsApi, type MemberUnit, type MemberUnitDetail } from "./unitsApi";

export type UnitEditTarget = { kind: "create"; parent: MemberUnit | null } | { kind: "edit"; unit: MemberUnit };

const CODE = /^[A-Z0-9]{1,6}$/;

/** Create a unit (under a parent, or at the top) or edit one: name, code, order and payment instructions. */
export function UnitEditDialog({ makerspaceId, target, units, levels, onClose, onSaved }: {
  makerspaceId: number; target: UnitEditTarget; units: readonly MemberUnit[]; levels: readonly string[];
  onClose: () => void; onSaved: (unit: MemberUnitDetail) => void;
}) {
  const editing = target.kind === "edit" ? target.unit : null;
  const detail = useQuery({ queryKey: unitKeys.detail(makerspaceId, editing?.id ?? 0), enabled: Boolean(editing),
    queryFn: () => unitsApi.detail(makerspaceId, editing!.id) });
  return editing && !detail.data
    ? <Modal open title={t`Edit ${editing.name}`} onClose={onClose}>
      {detail.isError ? <ErrorText message={unitErrorText(detail.error)} onRetry={() => void detail.refetch()} />
        : <p role="status" className="text-sm text-muted">{t`Loading the unit…`}</p>}
    </Modal>
    : <UnitForm makerspaceId={makerspaceId} target={target} detail={detail.data} units={units} levels={levels} onClose={onClose} onSaved={onSaved} />;
}

function UnitForm({ makerspaceId, target, detail, units, levels, onClose, onSaved }: {
  makerspaceId: number; target: UnitEditTarget; detail?: MemberUnitDetail; units: readonly MemberUnit[]; levels: readonly string[];
  onClose: () => void; onSaved: (unit: MemberUnitDetail) => void;
}) {
  const parent = target.kind === "create" ? target.parent : null;
  const level = detail ? detail.level : parent ? parent.level + 1 : 0;
  const kind = levelLabel(levels, level, () => t`unit`);
  const [name, setName] = useState(detail?.name ?? "");
  const [code, setCode] = useState(detail?.code ?? "");
  const [order, setOrder] = useState(String(detail?.sort_order ?? 0));
  const [instructions, setInstructions] = useState(detail?.payment_instructions ?? "");
  const save = useMutation({
    mutationFn: () => {
      const input = { name: name.trim(), sort_order: Number(order) || 0, payment_instructions: instructions.trim() };
      if (detail) return unitsApi.update(makerspaceId, detail.id, { ...input, ...(code !== detail.code ? { code } : {}) });
      return unitsApi.create(makerspaceId, { ...input, parent_id: parent?.id ?? null, ...(code ? { code } : {}) });
    },
    onSuccess: onSaved,
  });
  const codeProblem = code && !CODE.test(code) ? t`Use 1 to 6 capital letters or digits.` : undefined;
  const orderProblem = !/^\d{1,6}$/.test(order) ? t`Use a whole number from 0.` : undefined;
  const ready = name.trim().length > 0 && !codeProblem && !orderProblem;
  const source = detail?.effective_instructions_unit_id && detail.effective_instructions_unit_id !== detail.id
    ? units.find(unit => unit.id === detail.effective_instructions_unit_id) : null;
  const title = detail ? t`Edit ${detail.name}` : parent ? t`New ${kind} in ${parent.name}` : t`New ${kind}`;
  return <Modal open size="xl" title={title} onClose={() => { if (!save.isPending) onClose(); }}>
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); if (ready && !save.isPending) save.mutate(); }}>
      <Field label={t`Name`} className="sm:col-span-2">
        <input className="desk-input" required maxLength={120} value={name} onChange={event => setName(event.target.value)} />
      </Field>
      <Field label={t`Code`} error={codeProblem}
        hint={detail ? t`Used in join links (?unit=${detail.code}). It can't change once members or plans use the unit.` : t`Used in join links. Leave blank to make one from the name.`}>
        <input className="desk-input font-mono uppercase" maxLength={6} autoComplete="off" spellCheck={false} value={code}
          onChange={event => setCode(event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} />
      </Field>
      <Field label={t`Order`} hint={t`Lower numbers are listed first.`} error={orderProblem}>
        <input className="desk-input" inputMode="numeric" value={order} onChange={event => setOrder(event.target.value)} />
      </Field>
      <Field label={t`Offline payment instructions`} className="sm:col-span-2"
        hint={t`Shown to members of this unit and the units beneath it when they pay offline. Leave blank to use the nearest parent unit's, or else the space's.`}>
        <textarea className="desk-input min-h-24" maxLength={2000} value={instructions} onChange={event => setInstructions(event.target.value)} />
      </Field>
      {detail && !instructions.trim() ? <div className="grid gap-1 rounded-xl border border-line bg-surface p-3 text-sm sm:col-span-2" aria-live="polite">
        {detail.effective_payment_instructions && source
          ? <><span className="font-semibold text-ink">{t`Members here now see ${source.name}'s instructions:`}</span>
            <span className="whitespace-pre-line text-muted">{detail.effective_payment_instructions}</span></>
          : <span className="text-muted">{t`No unit above this one sets instructions, so members see the space's own.`}</span>}
      </div> : null}
      {save.error ? <div className="sm:col-span-2"><ErrorText message={unitErrorText(save.error)} /></div> : null}
      <div className="flex flex-wrap justify-end gap-2 sm:col-span-2">
        <button type="button" className="desk-button min-h-11" disabled={save.isPending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-primary min-h-11" disabled={!ready || save.isPending}>
          {save.isPending ? t`Saving…` : detail ? t`Save unit` : t`Add unit`}</button>
      </div>
    </form>
  </Modal>;
}
