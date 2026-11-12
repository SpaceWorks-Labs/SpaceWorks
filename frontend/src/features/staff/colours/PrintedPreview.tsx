import { t } from "@lingui/core/macro";
import { lazy, Suspense } from "react";
import { rgb } from "../../../lib/brandColours";
import { toHex } from "../../../lib/colourFix";

const SampleIdCard = lazy(() => import("../../auth/SampleIdCard").then((m) => ({ default: m.SampleIdCard })));

// Same fallback the billing document snapshot uses when no link colour is set (payments/document_snapshot.py).
export const DOCUMENT_DEFAULT_ACCENT = "#FF7447";

/** Receipts take only the link colour; the ID card below is drawn by the real card renderer with its own colours. */
export function PrintedPreview({ accent, mode }: { accent: string; mode: "light" | "dark" }) {
  const parsed = rgb(accent.trim());
  const header = parsed ? toHex(parsed) : DOCUMENT_DEFAULT_ACCENT;
  return <div className="grid gap-3">
    <div data-testid={`receipt-${mode}`} data-accent={header} className="overflow-hidden rounded-control border border-line bg-white text-xs text-[#142c2a]">
      <div className="px-3 py-2 font-semibold text-[#142c2a]" style={{ borderBottom: `4px solid ${header}` }}>{t`Receipt R-0042`}</div>
      <div className="flex justify-between px-3 py-2"><span>{t`Membership, monthly`}</span><span>{t`Paid`}</span></div>
    </div>
    {mode === "light" ? <div className="grid justify-items-start gap-1">
      <Suspense fallback={null}><SampleIdCard width={200} /></Suspense>
      <p className="text-xs text-muted">{t`ID card: keeps its own card-designer colours.`}</p>
    </div> : <p className="text-xs text-muted">{t`Printed documents are always on paper, so they have no dark version.`}</p>}
  </div>;
}
