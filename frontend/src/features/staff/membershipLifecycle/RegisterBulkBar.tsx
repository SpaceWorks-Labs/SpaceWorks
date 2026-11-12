import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BulkActionToolbar, StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi, lifecycleKeys, type RegisterBulkAction, type RegisterRow, type RowResult } from "../membershipLifecycleApi";
import { UnitPicker } from "../units/UnitPicker";
import { rowResultLabel } from "./registerModel";
import { BoxArt } from "../../../components/BoxSpinner";

export const MAX_BULK = 200;
export type BulkAbilities = { titles: boolean; units: boolean; reminders: boolean; cards: boolean };

function actionChoices(can: BulkAbilities): [RegisterBulkAction, string][] {
  return [
    ...(can.titles ? [["assign_title", t`Give a title`] as [RegisterBulkAction, string]] : []),
    ...(can.units ? [["move_unit", t`Move to a unit`] as [RegisterBulkAction, string]] : []),
    ...(can.reminders ? [["send_reminder", t`Send a renewal reminder`] as [RegisterBulkAction, string]] : []),
    ...(can.cards ? [["issue_cards", t`Issue member cards`], ["email_cards", t`Email member cards`]] as [RegisterBulkAction, string][] : []),
  ];
}

/**
 * Parity O-B2: one action for up to 200 chosen members. Each member runs the same single-member service
 * the member page uses, so one refusal never blocks the rest; the outcome for every row comes back and is
 * shown beside it. The server asks for a fresh sign-in confirmation first when the last one is old.
 */
export function RegisterBulkBar({ makerspaceId, selected, can, onClear, onResults, matchCount = 0, filter = {} }: {
  makerspaceId: number; selected: number[]; can: BulkAbilities; onClear: () => void; onResults: (results: RowResult[]) => void;
  /** How many members the current filters match, and those filters: lets one action cover them all. */
  matchCount?: number; filter?: Record<string, string>;
}) {
  const client = useQueryClient();
  const choices = actionChoices(can);
  const [action, setAction] = useState<RegisterBulkAction | "">("");
  const [titleId, setTitleId] = useState("");
  const [primary, setPrimary] = useState(false);
  const [unitId, setUnitId] = useState<number | null>(null);
  const titles = useQuery({ queryKey: lifecycleKeys.titles(makerspaceId), queryFn: () => lifecycleApi.titles(makerspaceId), enabled: action === "assign_title" });
  const [confirmAll, setConfirmAll] = useState(false);
  const apply = useMutation({
    mutationFn: (all: boolean) => lifecycleApi.registerBulk(makerspaceId, {
      action: action as RegisterBulkAction, ...(all ? { filter } : { membership_ids: selected.slice(0, MAX_BULK) }),
      ...(action === "assign_title" ? { title_id: Number(titleId), primary } : {}),
      ...(action === "move_unit" ? { unit_id: unitId } : {}),
    }),
    onSuccess: (results) => {
      setConfirmAll(false);
      onResults(results);
      void client.invalidateQueries({ queryKey: ["membership-l4", makerspaceId, "register"] });
    },
  });
  if (!choices.length) return null;
  const tooMany = selected.length > MAX_BULK;
  const ready = Boolean(action) && !tooMany && (action !== "assign_title" || Boolean(titleId));
  const canApplyAll = Boolean(action) && (action !== "assign_title" || Boolean(titleId)) && matchCount > selected.length && matchCount <= MAX_BULK;
  return <div className="grid gap-2">
    <BulkActionToolbar selectedCount={selected.length} onClear={onClear} actions={<>
      <label className="flex min-w-0 items-center gap-2"><span className="sr-only">{t`Bulk action`}</span>
        <select className="desk-input max-w-full" value={action} onChange={(event) => { setAction(event.target.value as RegisterBulkAction | ""); setConfirmAll(false); apply.reset(); }}>
          <option value="">{t`Choose an action`}</option>
          {choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
      {action === "assign_title" ? <>
        <label className="flex min-w-0 items-center gap-2"><span className="sr-only">{t`Title`}</span>
          <select className="desk-input max-w-full" value={titleId} onChange={(event) => setTitleId(event.target.value)}>
            <option value="">{t`Choose a title`}</option>
            {(titles.data ?? []).filter((title) => !title.archived_at).map((title) => <option key={title.id} value={title.id}>{title.name}</option>)}
          </select></label>
        <label className="flex min-h-11 items-center gap-2"><input className="h-4 w-4" type="checkbox" checked={primary} onChange={(event) => setPrimary(event.target.checked)} />{t`Make it their main title`}</label>
      </> : null}
      {action === "move_unit" ? <UnitPicker makerspaceId={makerspaceId} label={t`Move to`} noneLabel={t`No unit (take them out)`} value={unitId} onChange={setUnitId} /> : null}
      <button className="desk-button-primary" type="button" disabled={!ready || apply.isPending} onClick={() => apply.mutate(false)}>
        {apply.isPending ? <><BoxArt size={16} mono />{t`Applying…`}</> : t`Apply to ${Math.min(selected.length, MAX_BULK)}`}</button>
      {canApplyAll ? <button className="desk-button" type="button" disabled={apply.isPending} onClick={() => setConfirmAll(true)}>
        {t`Apply to all ${matchCount} matching`}</button> : null}
    </>} />
    {confirmAll && canApplyAll ? <div role="alertdialog" aria-label={t`Confirm the action for every match`} className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-panel p-3">
      <p className="text-sm text-ink">{t`This will run the action for all ${matchCount} members matching the current filters.`}</p>
      <button className="desk-button-primary" type="button" disabled={apply.isPending} onClick={() => apply.mutate(true)}>{apply.isPending ? <><BoxArt size={16} mono />{t`Applying…`}</> : t`Yes, apply to ${matchCount}`}</button>
      <button className="desk-button" type="button" onClick={() => setConfirmAll(false)}>{t`Cancel`}</button>
    </div> : null}
    {tooMany ? <p role="alert" className="text-sm text-warn-ink">{t`Choose at most ${MAX_BULK} members for one action. Narrow the list or clear some rows.`}</p> : null}
    {apply.error ? <p role="alert" className="text-sm text-danger">{apply.error instanceof StructuredApiError ? apply.error.message : t`That did not work. Try again.`}</p> : null}
  </div>;
}

/** The outcome of the last bulk action, one line per member, failures first. */
export function RegisterBulkResults({ results, rows, onDismiss }: { results: RowResult[]; rows: RegisterRow[]; onDismiss: () => void }) {
  const names = new Map(rows.map((row) => [row.membership_id, row.name || row.email || row.member_number]));
  const failed = results.filter((item) => !item.ok);
  const ordered = [...failed, ...results.filter((item) => item.ok)];
  return <section aria-label={t`Bulk action results`} className="grid gap-2 rounded-xl border border-line bg-panel p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p role="status" className="text-sm font-semibold text-ink">
        {failed.length ? t`Done for ${results.length - failed.length} of ${results.length}. ${failed.length} not changed.` : t`Done for all ${results.length}.`}</p>
      <button className="desk-button" type="button" onClick={onDismiss}>{t`Dismiss`}</button>
    </div>
    <div className="max-h-64 overflow-y-auto">
      <table className="w-full text-left text-sm"><caption className="sr-only">{t`Result for each member`}</caption>
        <thead className="text-xs text-muted"><tr><th scope="col" className="py-1 pr-3 font-semibold">{t`Member`}</th><th scope="col" className="py-1 font-semibold">{t`Result`}</th></tr></thead>
        <tbody>{ordered.map((item) => <tr key={item.id} className="border-t border-line">
          <td className="py-1.5 pr-3 text-ink">{names.get(item.id) ?? t`Member #${item.id}`}</td>
          <td className="py-1.5"><StatusPill tone={item.ok ? "success" : "warn"} label={rowResultLabel(item.ok ? "" : item.code)} /></td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>;
}
