// The working copy of one badge design, as in SpaceWorks-Events: every change autosaves 800 ms later through
// the compare-and-swap design PUT ({document: {version: 2, source}, revision}); offline (or when the network
// drops) the design is kept on this device and saved when the connection returns; a 409 means someone else
// saved first, and the organiser picks whose version wins. Undo/redo share the card designer's history.
import { t } from "@lingui/core/macro";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { CardDesign, CardDocument } from "../../../components/card-designer/cardTypes";
import { designKey } from "../../../components/card-designer/designerApi";
import { clearDeviceDraft, readDeviceDraft, writeDeviceDraft } from "../../../components/card-designer/deviceDraft";
import { useUndoHistory, useUndoShortcuts } from "../../../components/card-designer/undoHistory";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import { badgeSource, saveBadge, type BadgeDocument } from "./badgeApi";
import type { BadgeSaveStatus } from "./badgeLabels";
import { normalizeSettings, TEXT_LIMITS, type BadgeSettings } from "./badgeNormalize";

export const SAVE_DELAY_MS = 800;
type Context = { canEdit: boolean; eventTitle: string; organisationName: string };

const asDocument = (settings: BadgeSettings) =>
  ({ version: 2, source: { format: "badge_v1", settings } } satisfies BadgeDocument) as unknown as CardDocument;

function deviceCopy(design: CardDesign) {
  const draft = readDeviceDraft(design.id, design.revision);
  const settings = draft ? badgeSource({ ...design, document: draft.document }) : null;
  return draft && settings ? { savedAt: draft.savedAt, settings } : null;
}

export function useBadgeDesign(design: CardDesign, { canEdit, eventTitle, organisationName }: Context) {
  const client = useQueryClient();
  const fromServer = useCallback((row: CardDesign) => normalizeSettings(badgeSource(row), eventTitle, organisationName),
    [eventTitle, organisationName]);
  const [settings, setSettings] = useState(() => fromServer(design));
  const [status, setStatus] = useState<BadgeSaveStatus>("saved");
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [device, setDevice] = useState(() => (canEdit ? deviceCopy(design) : null));
  const latest = useRef(settings);
  const revision = useRef(design.revision);
  const timer = useRef<number | null>(null);
  const inFlight = useRef(false);
  const dirty = useRef(false);
  const saveRef = useRef<() => Promise<void>>(async () => undefined);

  const schedule = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    setStatus("pending");
    dirty.current = true;
    timer.current = window.setTimeout(() => void saveRef.current(), SAVE_DELAY_MS);
  }, []);

  const keepOnDevice = useCallback(() => {
    const kept = writeDeviceDraft(design.id, revision.current, asDocument(latest.current));
    setStatus(kept ? "local" : "error");
    setError(kept ? null : t`The design couldn't be saved. Check your connection and try again.`);
  }, [design.id]);

  const save = useCallback(async () => {
    if (!canEdit) return;
    if (timer.current) { window.clearTimeout(timer.current); timer.current = null; }
    if (inFlight.current) { dirty.current = true; return; }
    if (typeof navigator !== "undefined" && navigator.onLine === false) { keepOnDevice(); return; }
    inFlight.current = true;
    dirty.current = false;
    setStatus("saving");
    try {
      const saved = await saveBadge(design.id, latest.current, revision.current);
      revision.current = saved.revision;
      client.setQueryData(designKey(design.id), saved);
      clearDeviceDraft(design.id);
      setError(null);
      setConflict(false);
      setStatus("saved");
      inFlight.current = false;
      if (dirty.current) schedule();
    } catch (failure) {
      inFlight.current = false;
      if (!(failure instanceof StructuredApiError)) { keepOnDevice(); return; }
      writeDeviceDraft(design.id, revision.current, asDocument(latest.current));
      setConflict(failure.status === 409);
      setStatus("error");
      setError(failure.status === 409 ? null : failure.message);
    }
  }, [canEdit, client, design.id, keepOnDevice, schedule]);
  saveRef.current = save;

  const write = useCallback((next: BadgeSettings) => {
    latest.current = next;
    setSettings(next);
    schedule();
  }, [schedule]);
  const history = useUndoHistory(settings, write);
  useUndoShortcuts(history.undo, history.redo, canEdit);

  /** Apply a change (normalised like the server); text stays exactly as typed while editing. */
  const update = useCallback((patch: Partial<BadgeSettings>, record = true) => {
    if (!canEdit) return;
    const current = latest.current;
    if (record) history.record(current);
    const next = normalizeSettings({ ...current, ...patch }, eventTitle, organisationName);
    for (const [key, limit] of Object.entries(TEXT_LIMITS) as [keyof typeof TEXT_LIMITS, number][]) {
      next[key] = (patch[key] ?? current[key]).slice(0, limit);
    }
    if (patch.watermark) next.watermark = { ...next.watermark, text: patch.watermark.text.slice(0, 32) };
    const labels = patch.printFieldLabels;
    if (labels) {
      next.printFieldLabels = Object.fromEntries(Object.entries(next.printFieldLabels)
        .map(([key, value]) => [key, (labels[key] ?? value).slice(0, 60)]));
    }
    write(next);
  }, [canEdit, eventTitle, history, organisationName, write]);
  const checkpoint = useCallback(() => history.record(latest.current), [history]);

  /** Take a server copy as the working copy (an import, a restart, or "load their version"). */
  const adopt = useCallback((fresh: CardDesign, record = false) => {
    if (timer.current) window.clearTimeout(timer.current);
    if (record) history.record(latest.current);
    revision.current = fresh.revision;
    dirty.current = false;
    const next = fromServer(fresh);
    latest.current = next;
    setSettings(next);
    setStatus("saved");
    setError(null);
    setConflict(false);
  }, [fromServer, history]);

  // A newer server copy (a publish, another desk) is adopted only while nothing local is unsaved.
  useEffect(() => {
    if (design.revision > revision.current && status === "saved" && !inFlight.current) adopt(design);
  }, [adopt, design, status]);

  // Save the device copy once the connection comes back.
  useEffect(() => {
    if (!canEdit) return;
    const onOnline = () => { if (status === "local" || (status === "error" && !conflict)) void saveRef.current(); };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [canEdit, conflict, status]);

  // Leaving with a save still waiting: send it now rather than dropping it.
  useEffect(() => () => {
    if (timer.current) { window.clearTimeout(timer.current); void saveRef.current(); }
  }, []);

  const fetchFresh = useCallback(() => client.fetchQuery({ queryKey: designKey(design.id), staleTime: 0,
    queryFn: () => staffRequest<CardDesign>(`/admin/card-designs/${design.id}`) }), [client, design.id]);
  const loadTheirs = useCallback(async () => adopt(await fetchFresh()), [adopt, fetchFresh]);
  const keepMine = useCallback(async () => {
    const fresh = await fetchFresh();
    revision.current = fresh.revision;
    setConflict(false);
    await saveRef.current();
  }, [fetchFresh]);

  const restoreDevice = useCallback(() => {
    if (!device) return;
    history.record(latest.current);
    write(normalizeSettings(device.settings, eventTitle, organisationName));
    setDevice(null);
  }, [device, eventTitle, history, organisationName, write]);
  const discardDevice = useCallback(() => { clearDeviceDraft(design.id); setDevice(null); }, [design.id]);

  /** Save now (before a publish, an import or a convert); resolves once the server has the design. */
  const flush = useCallback(async () => { if (dirty.current || timer.current) await saveRef.current(); }, []);

  return { settings, update, checkpoint, undo: history.undo, redo: history.redo, canUndo: history.canUndo,
    canRedo: history.canRedo, status, error, conflict, retry: save, flush, adopt, loadTheirs, keepMine,
    device, restoreDevice, discardDevice };
}
