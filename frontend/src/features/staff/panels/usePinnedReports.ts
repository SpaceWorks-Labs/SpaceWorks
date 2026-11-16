import { useCallback, useState } from "react";
import { readStorage, writeStorage } from "../../../lib/safeStorage";

const key = (scope: string | number) => `spaceworks.reports.pinned.${scope}`;

function read(scope: string | number): string[] {
  try {
    const parsed: unknown = JSON.parse(readStorage(key(scope), "[]"));
    return Array.isArray(parsed) ? parsed.filter((entry): entry is string => typeof entry === "string") : [];
  } catch { return []; }
}

/** Pinned reports are a per-browser convenience, kept the way the theme and other viewer preferences are. */
export function usePinnedReports(scope: string | number) {
  const [state, setState] = useState(() => ({ scope, pinned: read(scope) }));
  const pinned = state.scope === scope ? state.pinned : read(scope);
  const toggle = useCallback((report: string) => {
    const current = read(scope);
    const next = current.includes(report) ? current.filter(entry => entry !== report) : [...current, report];
    writeStorage(key(scope), JSON.stringify(next));
    setState({ scope, pinned: next });
  }, [scope]);
  return { pinned: new Set(pinned) as ReadonlySet<string>, toggle };
}
