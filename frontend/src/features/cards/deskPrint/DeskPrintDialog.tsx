// Desk instant print for one card (parity C19): pick the stock and orientation, fetch the faces once, and
// print them at true size through the shared print shell. Printed cards stay in an in-memory queue, so
// "Print again" works with the network down. Nothing is stored on the device.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, Field, Modal, SegmentedControl } from "../../../components/ui";
import { deskStock, stockFamilies, type Orientation, type StockFamily } from "./deskStocks";
import { fetchFaces, printFaces } from "./printFaces";
import type { QueuedPrint, useDeskPrintQueue } from "./useDeskPrintQueue";
import { BoxArt } from "../../../components/BoxSpinner";

/** One card (`facePath`) or several (`facePaths`, one card per page). Each path is a `.../print-face` route. */
export type DeskPrintTarget = { id: string; label: string; facePath?: string; facePaths?: string[] };

export function DeskPrintDialog({ target, queue, onClose, onPrinted }: {
  target: DeskPrintTarget | null; queue: ReturnType<typeof useDeskPrintQueue>; onClose: () => void;
  /** Runs once the faces are fetched (so the server has counted the print); the list refreshes there. */
  onPrinted?: () => void;
}) {
  const [family, setFamily] = useState<StockFamily>("cr80");
  const [orientation, setOrientation] = useState<Orientation>("landscape");
  const [withBack, setWithBack] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [blocked, setBlocked] = useState(false);
  const offline = typeof navigator !== "undefined" && !navigator.onLine;

  async function run(entry: QueuedPrint) {
    setBlocked((await printFaces(entry)) === "blocked");
  }

  async function print() {
    if (!target) return;
    setBusy(true); setError(null); setBlocked(false);
    const stock = deskStock(family, orientation);
    const faces: string[] = [];
    try {
      for (const path of target.facePaths ?? (target.facePath ? [target.facePath] : [])) {
        faces.push(...await fetchFaces(path, stock.key, withBack ? ["front", "back"] : ["front"]));
      }
      const entry = { id: `${target.id}:${stock.key}:${faces.length}`, label: target.label, stockKey: stock.key,
        widthMm: stock.widthMm, heightMm: stock.heightMm, faces };
      queue.remember(entry);
      onPrinted?.();
      await run(entry);
    } catch (caught) {
      faces.forEach((url) => URL.revokeObjectURL(url));
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return <Modal open={Boolean(target)} onClose={onClose} title={t`Print at the desk`}
    footer={<div className="desk-actions flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button" onClick={onClose}>{t`Close`}</button>
      <button type="button" className="desk-button-primary" disabled={busy || offline} onClick={() => void print()}>
        {busy ? <><BoxArt size={16} mono />{t`Preparing…`}</> : t`Print`}</button>
    </div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`The card prints at its real size on the stock you choose. Check the printer is set to the same paper size.`}</p>
      <Field label={t`Stock`}>
        <select className="desk-input min-h-11" value={family} onChange={(event) => setFamily(event.target.value as StockFamily)}>
          {stockFamilies().map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </Field>
      <SegmentedControl label={t`Orientation`} value={orientation} onChange={(value) => setOrientation(value as Orientation)}
        options={[{ value: "portrait", label: t`Portrait` }, { value: "landscape", label: t`Landscape` }]} />
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5" checked={withBack} onChange={(event) => setWithBack(event.target.checked)} />
        {t`Print the back as a second page`}</label>
      {offline ? <p role="status" className="text-sm text-warn-ink">{t`You are offline. Cards already fetched can still be printed again below.`}</p> : null}
      {blocked ? <p role="alert" className="text-sm text-danger">{t`The browser blocked the print window. Allow pop-ups for this site and print again.`}</p> : null}
      {error ? <ErrorBlock error={error} /> : null}
      {queue.queue.length ? <section aria-label={t`Print again`} className="grid gap-2 border-t border-line pt-3">
        <h3 className="text-sm font-semibold text-ink">{t`Print again`}</h3>
        <ul className="grid gap-2">{queue.queue.map((entry) => <li key={entry.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>{entry.label} <span className="text-xs text-muted">{entry.stockKey}</span></span>
          <button type="button" className="desk-button-ghost min-h-11" onClick={() => void run(entry)}>{t`Print again`}</button>
        </li>)}</ul>
      </section> : null}
    </div>
  </Modal>;
}
