import { t } from "@lingui/core/macro";
import { currentSessionContext, type SessionContext } from "../../lib/api/sessionContext";
export type Toast = { id: number; message: string; tone: "success" | "error" | "info"; undo?: () => Promise<unknown>; undoKey?: string; busy?: boolean;
  action?: { label: string; onClick(): void } };
let nextId = 0;
let nextSession = 0;
const states = new Map<SessionContext, { session: number; rows: Toast[]; timers: Map<number, ReturnType<typeof setTimeout>> }>();
const state = (context = currentSessionContext()) => {
  if (!states.has(context)) states.set(context, { session: ++nextSession, rows: [], timers: new Map() });
  return states.get(context)!;
};
const listeners = new Set<() => void>();
const publish = () => listeners.forEach(listener => listener());
export const toastStore = {
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
  snapshot: () => state().rows,
};

export const toastSession = () => state().session;
export function clearToasts(context = currentSessionContext()) {
  const value = state(context); value.session = ++nextSession;
  value.timers.forEach(clearTimeout); value.timers.clear();
  value.rows = []; publish();
}

/** A newer edit retires the older compensation for this resource. */
export function invalidateToastUndo(key: string) {
  state().rows = state().rows.map(row => row.undoKey === key ? { ...row, undo: undefined } : row);
  publish();
}

export function dismissToast(id: number, context = currentSessionContext()) {
  const value = state(context);
  if (value.rows.find(row => row.id === id)?.busy) return;
  clearTimeout(value.timers.get(id)); value.timers.delete(id);
  value.rows = value.rows.filter(row => row.id !== id); publish();
}

/** Undo is an awaited compensating server call, supplied only by reversible actions. */
export function toast(message: string, options: { tone?: Toast["tone"]; undo?: Toast["undo"]; undoKey?: string; duration?: number; action?: Toast["action"] } = {}) {
  const id = ++nextId;
  state().rows = [...state().rows, { id, message, tone: options.tone ?? "success", undo: options.undo, undoKey: options.undoKey, action: options.action }]; publish();
  const context = currentSessionContext();
  if (options.tone !== "error") state().timers.set(id, setTimeout(() => dismissToast(id, context), options.duration ?? 8000));
  return id;
}

export async function undoToast(id: number) {
  const row = state().rows.find(value => value.id === id);
  if (!row?.undo || row.busy) return;
  const startedIn = state().session;
  clearTimeout(state().timers.get(id)); state().timers.delete(id);
  state().rows = state().rows.map(value => value.id === id ? { ...value, busy: true } : value); publish();
  try {
    await row.undo();
    if (startedIn !== state().session) return;
    state().rows = state().rows.filter(value => value.id !== id); publish();
    toast(t`Action undone.`);
  } catch (error) {
    if (startedIn !== state().session) return;
    state().rows = state().rows.map(value => value.id === id ? { id, tone: "error", message: error instanceof Error ? t`Could not undo: ${error.message}` : t`Could not undo. Please refresh and try again.` } : value);
    publish();
  }
}
