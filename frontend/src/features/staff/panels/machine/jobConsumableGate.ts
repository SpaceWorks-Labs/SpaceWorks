import { t } from "@lingui/core/macro";

import { entriesPayload, entriesProblem, missingRequired, type EntryValues } from "../../../machine-consumables/entries";
import type { JobConsumables } from "./jobConsumablesApi";
import type { DialogAction } from "./jobActionBody";

/** The actions that carry consumable entries: quote sends estimates, complete and fail send what was used. */
export const CONSUMABLE_ACTIONS: DialogAction[] = ["quote", "complete", "fail"];

export const activeRows = (data: JobConsumables | undefined) => (data?.profile ?? []).filter(row => row.is_active);

/** Why a dialog action cannot be sent yet because of consumables, or empty. Completing needs every required row recorded, now or earlier. */
export function consumableBlocker(action: DialogAction, data: JobConsumables | undefined, entries: EntryValues): string {
  if (!data || !CONSUMABLE_ACTIONS.includes(action)) return "";
  const rows = activeRows(data);
  const typed = entriesProblem(rows, entries, false);
  if (typed || action !== "complete") return typed;
  const pending = missingRequired(rows.filter(row => data.missing_required.includes(row.key)), entries);
  return pending.length ? t`Record ${pending.map(row => row.name).join(", ")} before completing.` : "";
}

export const consumableEntries = (action: DialogAction, data: JobConsumables | undefined, entries: EntryValues) =>
  data && CONSUMABLE_ACTIONS.includes(action) ? entriesPayload(activeRows(data), entries) : [];
