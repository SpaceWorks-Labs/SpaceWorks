// Bulk badges for an event (I21): pick who (a status set), then either download a PDF job (one badge per page
// for card and label printers, or A4 / Letter sheets with crop marks) or print the set from this browser, one
// badge per page at the stock size. The status sets are the server's (apps/events/id_cards_preview.py).
import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";

import { enqueueReceipt, newReceipt, PX_PER_MM, printNodes, type PrintReceipt } from "../../../components/card-print";
import { CardJobList, useStartCardJob } from "../../cards/cardJobs";
import { DeskBadgeFace, deskSize } from "./DeskBadgeFace";
import { designFor, fetchDesk, sendDeskReceipts, STATUS_SETS, type BadgeReceipt, type DeskResponse, type StatusSet } from "./deskBadgeApi";
import { BoxArt } from "../../../components/BoxSpinner";

export function statusSetLabels(): Record<StatusSet, string> {
  return {
    confirmed: t`Confirmed attendees`, attendees_without_crew: t`Attendees without crew`, crew: t`Crew`,
    checked_in: t`Checked in`, not_checked_in: t`Not yet checked in`, all: t`Everyone (confirmed, waitlisted, pending)`,
  };
}

export function BulkBadgesPanel({ eventId, canPrint }: { eventId: number; canPrint: boolean }) {
  const jobsPath = `/admin/events/${eventId}/card-jobs`;
  const start = useStartCardJob(jobsPath);
  const [statusSet, setStatusSet] = useState<StatusSet>("confirmed");
  const [paper, setPaper] = useState<"per_card" | "a4" | "letter">("per_card");
  const [batch, setBatch] = useState<DeskResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pages = useRef<HTMLDivElement>(null);
  const labels = statusSetLabels();
  if (!canPrint) return null;

  // One receipt per badge (method bulk), sent in batches of 200; what cannot be sent waits in the persistent queue.
  async function reportPrints(data: DeskResponse) {
    const receipts = (data.badges ?? []).map((badge) => newReceipt({ registration_id: badge.registration_id, method: "bulk" as const,
      role: badge.role, stock: designFor(data, badge.role)?.design.stock ?? "" }));
    for (let start = 0; start < receipts.length; start += 200) {
      const batch = receipts.slice(start, start + 200);
      try { await sendDeskReceipts(eventId, batch as BadgeReceipt[]); }
      catch { await Promise.all(batch.map((receipt) => enqueueReceipt(`event:${eventId}`, receipt as PrintReceipt))); }
    }
  }

  async function printHere() {
    setBusy(true); setMessage(null);
    try {
      const data = await fetchDesk(eventId, undefined, statusSet);
      if (!data.badges?.length) { setMessage(t`Nobody matches that set.`); return; }
      setBatch(data);
      // Let the faces and their QR codes draw, then hand them to the shared print shell.
      const wanted = data.badges.filter((badge) => badge.checkin_payload).length;
      const until = Date.now() + 8000;
      while (Date.now() < until && (pages.current?.querySelectorAll("img[src^='blob:']").length ?? 0) < wanted) await new Promise((done) => window.setTimeout(done, 100));
      const first = designFor(data, data.badges[0].role);
      const faces = Array.from(pages.current?.children ?? []) as HTMLElement[];
      if (!first || !faces.length) return;
      const result = await printNodes(faces, deskSize(first.design), { title: t`Event badges` });
      if (result === "blocked") { setMessage(t`Your browser blocked the print window. Allow pop-ups for this site, then print again.`); return; }
      await reportPrints(data);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : t`Could not prepare the badges.`);
    } finally { setBusy(false); }
  }

  return <section className="grid gap-3 rounded-md border border-line p-4" aria-labelledby="bulk-badges-title">
    <h4 id="bulk-badges-title" className="font-semibold text-ink">{t`Print many badges`}</h4>
    <div className="grid gap-2 sm:grid-cols-2">
      <label className="grid gap-1 text-sm text-ink">{t`Who`}
        <select className="desk-input" value={statusSet} onChange={(event) => setStatusSet(event.target.value as StatusSet)}>
          {STATUS_SETS.map((key) => <option key={key} value={key}>{labels[key]}</option>)}</select></label>
      <label className="grid gap-1 text-sm text-ink">{t`Paper`}
        <select className="desk-input" value={paper} onChange={(event) => setPaper(event.target.value as typeof paper)}>
          <option value="per_card">{t`One badge per page (card or label printer)`}</option>
          <option value="a4">{t`A4 sheets with crop marks`}</option><option value="letter">{t`Letter sheets with crop marks`}</option></select></label>
    </div>
    {statusSet === "all" ? <p className="text-sm text-muted">{t`Waitlisted and pending people print as provisional badges, without a check-in code.`}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary min-h-11" disabled={start.isPending}
        onClick={() => start.mutate({ kind: "bulk_sheet", status_set: statusSet, paper })}>{t`Download PDF`}</button>
      <button type="button" className="desk-button min-h-11" disabled={busy} onClick={() => void printHere()}>{busy ? <><BoxArt size={16} mono />{t`Preparing…`}</> : t`Print from this browser`}</button>
    </div>
    {message || start.error ? <p role="alert" className="text-sm text-danger">{message ?? start.error?.message}</p> : null}
    <CardJobList listPath={jobsPath} />
    <div ref={pages} aria-hidden="true" className="pointer-events-none fixed -left-[10000px] top-0">
      {batch?.badges?.map((badge) => {
        const chosen = designFor(batch, badge.role);
        return chosen ? <DeskBadgeFace key={badge.registration_id} badge={badge} design={chosen.design} logos={batch.logos} pxPerMm={PX_PER_MM} /> : null;
      })}
    </div>
  </section>;
}
