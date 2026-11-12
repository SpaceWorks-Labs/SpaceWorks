import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useExitingItems } from "../../lib/motion";
import { dismissToast, toastStore, undoToast } from "./toastStore";
import { BoxArt } from "../BoxSpinner";

export function ToastHost() {
  const live = useSyncExternalStore(toastStore.subscribe, toastStore.snapshot);
  // A dismissed toast stays on screen, inert, while its exit plays; announcements follow the live rows only.
  const shown = useExitingItems(live, row => row.id);
  const rows = live;
  const [announcement, setAnnouncement] = useState<{ text: string; error: boolean }>({ text: "", error: false });
  const previous = useRef(new Map<number, string>());
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    const changed = [...rows].reverse().find(row => previous.current.get(row.id) !== row.message);
    previous.current = new Map(rows.map(row => [row.id, row.message]));
    if (!changed) {
      if (!rows.length) { clearTimeout(timer.current); setAnnouncement({ text: "", error: false }); }
      return;
    }
    clearTimeout(timer.current);
    setAnnouncement({ text: "", error: false });
    // A separate DOM update announces repeated messages too, without moving focus.
    timer.current = setTimeout(() => setAnnouncement({ text: changed.message, error: changed.tone === "error" }), 50);
  }, [rows]);
  return <>
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement.error ? "" : announcement.text}</div>
    <div className="sr-only" role="alert" aria-atomic="true">{announcement.error ? announcement.text : ""}</div>
    <aside aria-label={t`Notifications`} className="fixed right-[max(1rem,env(safe-area-inset-right))] bottom-[calc(6rem+env(safe-area-inset-bottom))] z-50 grid max-h-[60dvh] w-[min(24rem,calc(100vw-2rem))] gap-2 overflow-y-auto overflow-x-clip overscroll-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {shown.map(({ item: row, leaving }) => <div key={row.id} data-state={leaving ? "closed" : "open"} inert={leaving} className="sw-fx-toast desk-panel border-outline shadow-overlay p-4">
        <p className={`break-words text-sm ${row.tone === "error" ? "text-danger" : "text-ink"}`}>{row.message}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {row.action ? <button className="desk-button-ghost underline" type="button" disabled={row.busy} onClick={row.action.onClick}>{row.action.label}</button> : null}
          {row.undo ? <button className="desk-button-ghost underline" type="button" disabled={row.busy} onClick={() => void undoToast(row.id)}>{row.busy ? <><BoxArt size={16} mono />{t`Undoing…`}</> : t`Undo`}</button> : null}
          <button className="desk-button-ghost" type="button" disabled={row.busy} onClick={() => dismissToast(row.id)}>{t`Dismiss`}</button>
        </div>
      </div>)}
    </aside>
  </>;
}
