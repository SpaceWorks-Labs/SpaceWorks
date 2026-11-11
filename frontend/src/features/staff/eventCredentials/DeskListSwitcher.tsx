// D22: the check-in desk can switch from "Entry" to an extra list (swag, a meal, a workshop) with `?list=<id>`
// in the address, so a desk can be bookmarked or shared. In list mode a scan collects from that list instead of
// recording entry; the collection can be undone for 60 seconds, and a waitlisted guest needs an explicit override.
import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { staffRequest } from "../../../lib/api";
import { toast } from "../../../components/ui/toastStore";
import { adminBase, useStaffQuery, type CheckInList, type ListEligibility } from "../eventParticipation/api";
import { LIST_REASONS } from "../eventParticipation/CheckInListRow";
import { orderLists } from "../eventParticipation/CheckInListsPanel";
import { deskFeedback } from "./deskFeedback";

export function useDeskList(eventId: number, enabled: boolean) {
  const [params, setParams] = useSearchParams();
  const lists = useStaffQuery<CheckInList[]>(eventId, "/checkin-lists/", enabled);
  const open = orderLists(lists.data ?? []).filter((list) => !list.archived);
  const active = open.find((list) => String(list.id) === params.get("list")) ?? null;
  const choose = (id: string) => setParams((previous) => { const next = new URLSearchParams(previous); if (id) next.set("list", id); else next.delete("list"); return next; });
  return { open, active, choose };
}

export function DeskListSwitcher({ open, active, choose }: ReturnType<typeof useDeskList>) {
  if (!open.length) return null;
  return <label className="grid gap-1 text-sm text-ink">{t`Desk`}
    <select className="desk-input" value={active?.id ?? ""} onChange={(event) => choose(event.target.value)}>
      <option value="">{t`Entry check-in`}</option>
      {open.map((list) => <option key={list.id} value={list.id}>{list.name}</option>)}
    </select></label>;
}

/** Collects one guest from `list`. Returns a refusal reason (already translated) or null on success. */
export async function collectFromList(eventId: number, list: CheckInList, registrationId: number, name: string, override = false): Promise<{ reason: string; code: string } | null> {
  try {
    const value = await staffRequest<ListEligibility>(`${adminBase(eventId)}/checkin-lists/${list.id}/scan/`, { method: "POST",
      body: JSON.stringify({ operation_id: crypto.randomUUID(), registration_id: registrationId, ...(override ? { override: true } : {}) }) });
    deskFeedback(true);
    const left = value.undo_until ? new Date(value.undo_until).getTime() - Date.now() : 0;
    toast(t`${name} collected from ${list.name}.`, left > 1000 && value.scan_id ? { duration: Math.min(left, 60_000), undoKey: `checkin-list-scan-${value.scan_id}`,
      undo: async () => { await staffRequest(`${adminBase(eventId)}/checkin-lists/${list.id}/scan/${value.scan_id}/undo/`, { method: "POST", body: "{}" }); } } : {});
    return null;
  } catch (cause) {
    deskFeedback(false);
    const code = (cause as { code?: string }).code ?? "";
    return { code, reason: LIST_REASONS()[code] ?? (cause instanceof Error ? cause.message : t`Could not record that collection.`) };
  }
}

/** Mounts the switcher and reports the chosen list upward, so the scanner can stay free of list state. */
export function DeskListSwitch({ eventId, onActive }: { eventId: number; onActive: (list: CheckInList | null) => void }) {
  const desk = useDeskList(eventId, true);
  const id = desk.active?.id ?? null;
  useEffect(() => { onActive(desk.active); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  return <DeskListSwitcher {...desk} />;
}
