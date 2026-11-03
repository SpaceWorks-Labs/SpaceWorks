// The working copy of one design: undo/redo (50 whole-document snapshots), autosave
// debounced 900 ms with compare-and-swap, and a conflict state when someone else saved.
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { StructuredApiError } from "../../lib/api";
import type { CardDesign, CardDocument } from "./cardTypes";
import { designKey, saveDesign } from "./designerApi";

export type SaveStatus = "saved" | "pending" | "saving" | "error" | "conflict";
export const SAVE_STATUS_LABELS: Record<SaveStatus, string> = {
  saved: "Saved", pending: "Unsaved changes", saving: "Saving…", error: "Not saved", conflict: "Someone else saved",
};
const HISTORY = 50;
const SAVE_DELAY_MS = 900;

export function useCardDesign(design: CardDesign, canEdit: boolean) {
  const client = useQueryClient();
  const [document, setDocument] = useState<CardDocument>(design.document);
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [error, setError] = useState<string | null>(null);
  const [undoStack, setUndo] = useState<CardDocument[]>([]);
  const [redoStack, setRedo] = useState<CardDocument[]>([]);
  const revision = useRef(design.revision);
  const latest = useRef(document);
  const timer = useRef<number | null>(null);
  latest.current = document;

  useEffect(() => {
    // Adopt a newer server copy (a publish, another tab) only while nothing local is unsaved.
    if (design.revision > revision.current && status === "saved") {
      revision.current = design.revision;
      setDocument(design.document);
    }
  }, [design.revision, design.document, status]);

  const save = useCallback(async () => {
    if (!canEdit) return;
    setStatus("saving");
    try {
      const saved = await saveDesign(design.id, latest.current, revision.current);
      revision.current = saved.revision;
      client.setQueryData(designKey(design.id), saved);
      setError(null);
      setStatus((current) => (current === "pending" ? "pending" : "saved"));
    } catch (failure) {
      if (failure instanceof StructuredApiError && failure.status === 409) {
        setStatus("conflict");
      } else {
        setStatus("error");
        setError(failure instanceof Error ? failure.message : "The design couldn't be saved.");
      }
    }
  }, [canEdit, client, design.id]);

  const schedule = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    setStatus("pending");
    timer.current = window.setTimeout(() => void save(), SAVE_DELAY_MS);
  }, [save]);

  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);

  const update = useCallback((change: (current: CardDocument) => CardDocument, record = true) => {
    if (!canEdit) return;
    const previous = latest.current;
    const next = change(previous);
    if (next === previous) return;
    if (record) {
      setUndo((stack) => [...stack.slice(-(HISTORY - 1)), previous]);
      setRedo([]);
    }
    latest.current = next;
    setDocument(next);
    schedule();
  }, [canEdit, schedule]);

  const checkpoint = useCallback(() => {
    setUndo((stack) => [...stack.slice(-(HISTORY - 1)), latest.current]);
    setRedo([]);
  }, []);

  // Stacks are read from state but changed outside the setState updaters, so React's
  // StrictMode double-invocation cannot push a snapshot twice.
  const undo = useCallback(() => {
    const previous = undoStack[undoStack.length - 1];
    if (!previous) return;
    setUndo(undoStack.slice(0, -1));
    setRedo([...redoStack, latest.current]);
    latest.current = previous;
    setDocument(previous);
    schedule();
  }, [undoStack, redoStack, schedule]);

  const redo = useCallback(() => {
    const next = redoStack[redoStack.length - 1];
    if (!next) return;
    setRedo(redoStack.slice(0, -1));
    setUndo([...undoStack, latest.current]);
    latest.current = next;
    setDocument(next);
    schedule();
  }, [undoStack, redoStack, schedule]);

  const reload = useCallback(async () => {
    await client.invalidateQueries({ queryKey: designKey(design.id) });
    const fresh = client.getQueryData<CardDesign>(designKey(design.id));
    if (fresh) {
      revision.current = fresh.revision;
      setDocument(fresh.document);
    }
    setStatus("saved");
  }, [client, design.id]);

  /** Take a server copy as the working copy (after a reset, an import or a reload): local edits are dropped. */
  const adopt = useCallback((fresh: CardDesign) => {
    if (timer.current) window.clearTimeout(timer.current);
    revision.current = fresh.revision;
    latest.current = fresh.document;
    setDocument(fresh.document);
    setUndo([]);
    setRedo([]);
    setStatus("saved");
    setError(null);
  }, []);

  return { document, update, adopt, checkpoint, undo, redo, canUndo: undoStack.length > 0, canRedo: redoStack.length > 0,
    status, error, retry: save, reload, flush: save };
}
