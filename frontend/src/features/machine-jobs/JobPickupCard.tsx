import { t } from "@lingui/core/macro";
import { useUpiQr } from "../members/MemberPaymentOffline";
import type { MemberJob } from "./types";

/**
 * Ready to collect: where to pick it up, and the pickup code as text AND as a QR the desk can
 * scan. The QR is drawn in the browser from the code itself (same writer as the payment QR).
 */
export function JobPickupCard({ job }: { job: Pick<MemberJob, "label" | "pickup_code" | "pickup_location" | "title"> }) {
  const ready = job.label === "ready_to_collect";
  const qr = useUpiQr(ready && job.pickup_code ? job.pickup_code : null);
  if (!ready) return null;
  return <section className="desk-panel grid gap-4 border-success p-5" aria-labelledby="job-pickup-title">
    <div><h2 id="job-pickup-title" className="title-panel">{t`Ready to collect`}</h2>
      <p className="mt-1 text-sm text-muted">{job.pickup_location ? <>{t`Pick it up at `}<strong className="text-ink">{job.pickup_location}</strong>.</> : t`Ask at the front desk.`} {t` Collect it within 14 days.`}</p></div>
    {job.pickup_code ? <div className="flex flex-wrap items-center gap-5">
      {qr ? <img src={qr} className="aspect-square w-40 rounded-md border border-line bg-white p-1" alt={t`QR code of pickup code ${job.pickup_code}`} />
        : <div className="grid aspect-square w-40 place-items-center rounded-md border border-line text-xs text-muted" role="status">{t`Drawing QR…`}</div>}
      <div className="grid gap-1">
        <p className="text-sm text-muted">{t`Pickup code`}</p>
        <p className="font-accent text-3xl font-semibold tracking-widest text-ink tabular-nums">{job.pickup_code}</p>
        <p className="text-sm text-muted">{t`Show this at the desk, or let staff scan the QR.`}</p>
      </div>
    </div> : null}
  </section>;
}
