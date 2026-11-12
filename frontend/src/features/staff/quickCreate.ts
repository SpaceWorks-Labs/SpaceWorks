import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

export function quickCreateCommands(actions: readonly string[], tabs: readonly string[], superadmin = false) {
  return [
    { key: "new-request", label: t`New request / direct handout`, tab: "direct", action: "issue_direct_loan", kind: "request" },
    { key: "new-item", label: t`New item`, tab: "inventory", action: "edit_inventory", kind: "item" },
    { key: "new-event", label: t`New event`, tab: "events", action: "manage_events", kind: "event" },
    { key: "new-booking", label: t`New booking`, tab: "bookings", action: "manage_bookings", kind: "booking" },
  ].filter(command => tabs.includes(command.tab) && (superadmin || actions.includes(command.action)))
    .map(command => ({ ...command, query: { create: command.kind } }));
}

/** Consume once so Back does not reopen a completed form. */
export function useQuickCreate(kind: string, open: () => void) {
  const [params, setParams] = useSearchParams();
  const requested = params.get("create") === kind;
  useEffect(() => {
    if (!requested) return;
    open();
    setParams(current => { const next = new URLSearchParams(current); next.delete("create"); return next; }, { replace: true });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- open and setParams are read once when ?create= appears; re-running on their identity would reopen the form this effect just consumed
  }, [requested]);
}
