import { useCallback, useState } from "react";

// The faces of the last few printed cards, kept in memory only (object URLs), so a card can be printed
// again with the network down. Nothing is persisted: closing the tab drops them and revokes the URLs.
const KEEP = 5;

export type QueuedPrint = { id: string; label: string; stockKey: string; widthMm: number; heightMm: number; faces: string[] };

export function useDeskPrintQueue() {
  const [queue, setQueue] = useState<QueuedPrint[]>([]);
  const remember = useCallback((entry: QueuedPrint) => setQueue((current) => {
    const kept = [entry, ...current.filter((item) => item.id !== entry.id)];
    kept.slice(KEEP).forEach((dropped) => dropped.faces.forEach((url) => URL.revokeObjectURL(url)));
    return kept.slice(0, KEEP);
  }), []);
  return { queue, remember };
}
