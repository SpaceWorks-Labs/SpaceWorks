import { useState, type DragEvent } from "react";

import { dropPosition } from "./boardOrder";
import type { JobBoard, StaffJob } from "./machineJobsApi";

/** What one queue card needs to take part in drag to reorder (#141). */
export type CardDrag = {
  draggable: true; dragging: boolean; over: boolean;
  onDragStart: (event: DragEvent) => void; onDragOver: (event: DragEvent) => void; onDragLeave: () => void;
  onDrop: (event: DragEvent) => void; onDragEnd: () => void;
};

/**
 * Pointer drag to reorder one queue column. The move buttons stay the keyboard and screen-reader way
 * to reorder; a drop calls the same reorder endpoint with the same placement, and `announcement` says
 * what moved for the live region.
 */
export function useQueueDrag(board: JobBoard | undefined, onMove: (job: StaffJob, position: number) => void) {
  const [dragId, setDragId] = useState<number | null>(null);
  const [overId, setOverId] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const reset = () => { setDragId(null); setOverId(null); };
  const dragFor = (job: StaffJob, column: StaffJob[]): CardDrag => {
    const source = () => column.find(row => row.id === dragId);
    const position = () => {
      const from = source();
      return from && board ? dropPosition(from, job, column, board) : null;
    };
    return {
      draggable: true, dragging: dragId === job.id, over: overId === job.id && dragId !== job.id,
      onDragStart: event => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(job.id));
        setDragId(job.id);
      },
      onDragOver: event => {
        if (position() === null) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        if (overId !== job.id) setOverId(job.id);
      },
      onDragLeave: () => setOverId(current => (current === job.id ? null : current)),
      onDrop: event => {
        event.preventDefault();
        const from = source(), place = position();
        reset();
        if (!from || place === null) return;
        onMove(from, place);
        setAnnouncement(`Moved ${from.title} to place ${column.findIndex(row => row.id === job.id) + 1} in the queue.`);
      },
      onDragEnd: reset,
    };
  };
  return { dragFor, announcement };
}
