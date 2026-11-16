import { t } from "@lingui/core/macro";
import { useState, type DragEvent } from "react";
import type { CrewRow } from "./api";

/**
 * The approved crew in staff order, moved by drag-and-drop or by the arrow buttons (keyboard and touch). The new
 * order shows at once and is sent as one `crew/reorder/` call; a refusal puts the server's order back.
 */
export function useCrewOrder(rows: CrewRow[], commit: (ids: number[]) => Promise<unknown>) {
  const [pending, setPending] = useState<number[] | null>(null);
  const [dragged, setDragged] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const byId = new Map(rows.map(row => [row.id, row]));
  const live = pending && pending.length === rows.length && pending.every(id => byId.has(id))
    ? pending.map(id => byId.get(id)!) : rows;
  const move = (from: number, to: number) => {
    if (to < 0 || to >= live.length || from === to) return;
    const ids = live.map(row => row.id); const [id] = ids.splice(from, 1); ids.splice(to, 0, id);
    setPending(ids);
    setAnnouncement(t`${byId.get(id)?.name ?? ""} moved to position ${to + 1} of ${ids.length}.`);
    commit(ids).catch(() => setAnnouncement(t`The order could not be saved, so the earlier order is back.`)).finally(() => setPending(null));
  };
  const handles = (row: CrewRow, index: number) => ({
    index, count: live.length, dragging: dragged === row.id, move: (to: number) => move(index, to),
    drag: {
      onDragStart: (event: DragEvent) => { setDragged(row.id); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(row.id)); },
      onDragOver: (event: DragEvent) => { if (dragged !== null) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; } },
      onDrop: (event: DragEvent) => { event.preventDefault(); const from = live.findIndex(item => item.id === dragged); setDragged(null); if (from >= 0) move(from, index); },
      onDragEnd: () => setDragged(null),
    },
  });
  return { rows: live, handles, announcement };
}
