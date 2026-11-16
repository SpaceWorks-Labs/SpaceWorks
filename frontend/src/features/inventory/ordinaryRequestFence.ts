import { onSessionCleared } from "../../lib/api/sessionContext";
import { getSessionOwner } from "../../lib/api/sessionTokens";

type Entry = { busy: boolean; unknown: boolean; reviewed: boolean; listeners: Set<() => void> };
const entries = new Map<string, Entry>();
onSessionCleared(context => {
  for (const [key, entry] of entries) {
    const [entryContext, entryOwner] = JSON.parse(key) as [string, string];
    if (entryContext === context && entryOwner !== getSessionOwner(context)) {
      entries.delete(key);
      entry.listeners.forEach(listener => listener());
    }
  }
});
export function ordinaryEntry(scope: string): Entry {
  let entry = entries.get(scope);
  if (!entry) { entry = { busy: false, unknown: false, reviewed: false, listeners: new Set() }; entries.set(scope, entry); }
  return entry;
}
export function notifyOrdinary(entry: Entry) { entry.listeners.forEach(listener => listener()); }
export function acquireOrdinary(scope: string): ((definite: boolean) => boolean) | undefined {
  const entry = ordinaryEntry(scope);
  if (entry.busy || entry.unknown) return undefined;
  entry.busy = true; entry.unknown = true; notifyOrdinary(entry);
  return definite => {
    if (entries.get(scope) !== entry) return false;
    entry.busy = false;
    if (definite) entry.unknown = false;
    notifyOrdinary(entry);
    return true;
  };
}
