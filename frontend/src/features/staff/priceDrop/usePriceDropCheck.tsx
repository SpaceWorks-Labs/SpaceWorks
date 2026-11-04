import { useCallback, useRef, useState, type ReactNode } from "react";

import { PriceDropDialog } from "./PriceDropDialog";
import { previewPriceDrop, usePriceDropOn, type PriceDropReport } from "./priceDropApi";

/**
 * The guard every price form runs before it saves (#163A).
 *
 * `await check(path, method, body)` previews the save with the same request. It resolves
 * `true` straight away when price-drop refunds are off, when nothing paid would get cheaper,
 * or when the preview cannot answer (the real save then shows its own error). When paid,
 * not-yet-used items would cost less, it opens `PriceDropDialog` and resolves with the
 * person's answer. Render `dialog` anywhere in the form.
 */
export function usePriceDropCheck(makerspaceId?: number): {
  check: (path: string, method: string, body: unknown) => Promise<boolean>;
  dialog: ReactNode;
  checking: boolean;
} {
  const on = usePriceDropOn(makerspaceId);
  const [report, setReport] = useState<PriceDropReport | null>(null);
  const [checking, setChecking] = useState(false);
  const answer = useRef<((value: boolean) => void) | null>(null);

  const check = useCallback(async (path: string, method: string, body: unknown) => {
    if (!on) return true;
    setChecking(true);
    let found: PriceDropReport | null = null;
    try {
      found = await previewPriceDrop(path, method, body);
    } finally {
      setChecking(false);
    }
    if (!found || found.count === 0) return true;
    setReport(found);
    return new Promise<boolean>(resolve => { answer.current = resolve; });
  }, [on]);

  const close = (value: boolean) => {
    setReport(null);
    answer.current?.(value);
    answer.current = null;
  };

  const dialog = report
    ? <PriceDropDialog report={report} onConfirm={() => close(true)} onClose={() => close(false)} />
    : null;
  return { check, dialog, checking };
}
