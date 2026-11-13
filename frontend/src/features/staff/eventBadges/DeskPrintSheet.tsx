// After a check-in: the person's real badge, Print (Enter), Skip, Edit design (hidden on stations).
// Printing draws the badge again at true size (96 px per inch) and hands it to the shared print shell, which
// opens a window whose @page is the stock. Everything needed is already on the device, so it works offline.
import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";

import { PX_PER_MM, printNodes, type ReceiptOutcome } from "../../../components/card-print";
import { Modal } from "../../../components/ui";
import { DeskBadgeFace, deskSize } from "./DeskBadgeFace";
import { designFor, type DeskBadge, type DeskBundle } from "./deskBadgeApi";

const PREVIEW_MAX_PX = 300;
const QR_WAIT_MS = 2000;

async function qrReady(node: HTMLElement, needed: boolean) {
  const until = Date.now() + QR_WAIT_MS;
  while (needed && Date.now() < until && !node.querySelector("img[src^='blob:']")) await new Promise((done) => window.setTimeout(done, 50));
}

export function DeskPrintSheet({ badge, bundle, onPrinted, onSkip, onEdit }: {
  badge: DeskBadge; bundle: DeskBundle;
  /** Records the receipt; resolves how it was kept so the operator knows. */
  onPrinted: (info: { stock: string; role: string }) => Promise<ReceiptOutcome | void>;
  onSkip: () => void;
  /** Absent on stations: a station never edits a design. */
  onEdit?: () => void;
}) {
  const chosen = designFor(bundle, badge.role);
  const printNode = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"ready" | "printing" | "sent" | "blocked">("ready");
  const [receipt, setReceipt] = useState<ReceiptOutcome | void>();
  const size = chosen ? deskSize(chosen.design) : { widthMm: 1, heightMm: 1 };
  const previewScale = Math.min(PREVIEW_MAX_PX / size.widthMm, PREVIEW_MAX_PX / size.heightMm);

  async function print() {
    if (!chosen || state === "printing" || !printNode.current) return;
    setState("printing");
    await qrReady(printNode.current, Boolean(badge.checkin_payload));
    const face = printNode.current.firstElementChild as HTMLElement | null;
    const result = face ? await printNodes([face], { widthMm: size.widthMm, heightMm: size.heightMm }, { title: badge.name }) : "blocked";
    if (result === "blocked") { setState("blocked"); return; }
    setReceipt(await onPrinted({ stock: chosen.design.stock, role: badge.role }));
    setState("sent");
  }
  const printRef = useRef(print);
  printRef.current = print;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key !== "Enter" || target?.closest("button, a, input, select, textarea")) return;
      event.preventDefault(); void printRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return <Modal open onClose={onSkip} title={state === "sent" ? t`Badge sent to the printer` : t`Print a badge?`}
    footer={<div className="flex flex-wrap gap-2">
      <button className="desk-button" type="button" onClick={onSkip}>{state === "sent" ? t`Done` : t`Skip`}</button>
      {onEdit ? <button className="desk-button" type="button" onClick={onEdit}>{t`Edit design`}</button> : null}
      <button className="desk-button-primary" type="button" autoFocus disabled={!chosen || state === "printing"} onClick={() => void print()}>
        {state === "sent" ? t`Print again` : t`Print badge (Enter)`}</button></div>}>
    <div className="grid justify-items-center gap-3">
      <p className="text-sm text-ink">{t`${badge.name} is checked in.`}{badge.provisional ? t` This is a provisional badge.` : ""}</p>
      {chosen ? <DeskBadgeFace badge={badge} design={chosen.design} logos={bundle.logos} pxPerMm={previewScale} />
        : <p role="alert" className="text-sm text-danger">{t`No badge design is published for this event yet.`}</p>}
      {state === "blocked" ? <p role="alert" className="text-sm text-danger">{t`Your browser blocked the print window. Allow pop-ups for this site, then print again.`}</p> : null}
      {state === "sent" && receipt === "queued" ? <p role="status" className="text-sm text-muted">{t`Print recorded on this device. It will be sent when the connection is back.`}</p> : null}
      {state === "sent" && receipt === "lost" ? <p role="status" className="text-sm text-warn-ink">{t`The badge printed, but the print could not be recorded.`}</p> : null}
    </div>
    {/* The true-size copy the print window takes: off screen, never visible. */}
    <div ref={printNode} aria-hidden="true" className="pointer-events-none fixed -left-[10000px] top-0">
      {chosen ? <DeskBadgeFace badge={badge} design={chosen.design} logos={bundle.logos} pxPerMm={PX_PER_MM} /> : null}
    </div>
  </Modal>;
}
