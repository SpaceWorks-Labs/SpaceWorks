// A copy of unsaved design edits on this device, so a dropped connection never loses work.
// Written only when a save fails for a reason other than a conflict; cleared after any save
// succeeds. Storage can be missing or blocked (private windows), so every access is guarded,
// and the copy is offered back only for the exact revision it was based on.
import type { CardDocument } from "./cardTypes";

export type DeviceDraft = { revision: number; savedAt: string; document: CardDocument };

const key = (designId: number) => `sw:card-design-draft:${designId}`;

export function readDeviceDraft(designId: number, revision: number): DeviceDraft | null {
  try {
    const raw = window.localStorage.getItem(key(designId));
    if (!raw) return null;
    const value = JSON.parse(raw) as DeviceDraft;
    return value && value.revision === revision && value.document?.version === 2 ? value : null;
  } catch {
    return null;
  }
}

export function writeDeviceDraft(designId: number, revision: number, document: CardDocument) {
  try {
    window.localStorage.setItem(key(designId), JSON.stringify({ revision, savedAt: new Date().toISOString(), document }));
    return true;
  } catch {
    return false;
  }
}

export function clearDeviceDraft(designId: number) {
  try {
    window.localStorage.removeItem(key(designId));
  } catch {
    // Nothing stored, or storage blocked: nothing to clear.
  }
}
