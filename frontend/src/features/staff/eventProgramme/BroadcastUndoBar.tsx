import { plural, t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Undo2 } from "lucide-react";
import { BoxArt } from "../../../components/BoxSpinner";

/** Visible countdown for the five-second send hold; Undo cancels before delivery starts. */
export function BroadcastUndoBar({ until, busy, onUndo }: { until: string; busy: boolean; onUndo: () => void }) {
  const deadline = new Date(until).getTime();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (now >= deadline) return;
    const timer = setTimeout(() => setNow(Date.now()), 250);
    return () => clearTimeout(timer);
  }, [now, deadline]);
  const seconds = Math.max(0, Math.ceil((deadline - now) / 1000));
  if (seconds === 0) return <p role="status" className="desk-panel border-outline p-3 text-sm">{t`Sending now. Delivery has started, so accepted email can no longer be recalled.`}</p>;
  return <div role="status" className="desk-panel border-outline shadow-overlay flex flex-wrap items-center justify-between gap-3 p-3">
    <p className="text-sm">{t`Sending in`} <span className="font-semibold tabular-nums">{seconds}</span> {plural(seconds, { one: "second…", other: "seconds…" })}</p>
    <button type="button" className="desk-button inline-flex items-center gap-2" disabled={busy} onClick={onUndo}><Undo2 aria-hidden="true" className="size-4" />{busy ? <><BoxArt size={16} mono />{t`Undoing…`}</> : t`Undo send`}</button>
  </div>;
}
