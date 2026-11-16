import { t } from "@lingui/core/macro";
import { useBroadcastTallies } from "./broadcastApi";

const LABELS = [["delivered", "Delivered"], ["waiting", "Waiting"], ["failed", "Failed"], ["skipped", "Skipped"]] as const;

/** Counts only: the ledger never names recipients here. */
export function BroadcastTalliesRow({ makerspaceId, eventId, campaignId, status }: { makerspaceId: number; eventId: number; campaignId: number; status: string }) {
  const live = ["queued", "sending"].includes(status);
  const tallies = useBroadcastTallies(makerspaceId, eventId, campaignId, live);
  if (!tallies.data || !["queued", "sending", "sent", "failed", "cancelled"].includes(status)) return null;
  const data = tallies.data;
  return <dl aria-label={t`Delivery tallies`} className="grid grid-cols-2 gap-2 sm:grid-cols-4">{LABELS.map(([key, label]) => <div key={key} className="rounded-xl border border-line bg-surface p-3">
    <dt className="text-xs text-muted">{label}</dt><dd className="text-xl font-semibold tabular-nums">{data[key]}</dd>
  </div>)}<p className="col-span-full text-xs text-muted">{t`${data.total} recipients in this send. Each person is counted once, by their best outcome across channels.`}</p></dl>;
}
