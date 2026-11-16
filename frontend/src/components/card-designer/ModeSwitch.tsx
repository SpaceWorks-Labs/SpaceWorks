// Quick or Advanced: quick is the default for people who just want a good-looking card; advanced is the full
// canvas. The choice is remembered per browser (storage may be unavailable, so every access is guarded).
import { t } from "@lingui/core/macro";
import { useCallback, useState } from "react";

import { SegmentedControl } from "../ui/SegmentedControl";

export type StudioMode = "quick" | "advanced";
export const MODE_KEY = "spaceworks.card-studio-mode";

function readMode(): StudioMode {
  try { return window.localStorage.getItem(MODE_KEY) === "advanced" ? "advanced" : "quick"; } catch { return "quick"; }
}

export function useStudioMode(): [StudioMode, (mode: StudioMode) => void] {
  const [mode, setMode] = useState<StudioMode>(readMode);
  const change = useCallback((next: StudioMode) => {
    setMode(next);
    try { window.localStorage.setItem(MODE_KEY, next); } catch { /* the choice just is not remembered */ }
  }, []);
  return [mode, change];
}

export function ModeSwitch({ mode, onChange }: { mode: StudioMode; onChange: (mode: StudioMode) => void }) {
  return <SegmentedControl label={t`Design mode`} value={mode} onChange={(value) => onChange(value as StudioMode)}
    options={[{ value: "quick", label: t`Quick` }, { value: "advanced", label: t`Advanced` }]} />;
}
