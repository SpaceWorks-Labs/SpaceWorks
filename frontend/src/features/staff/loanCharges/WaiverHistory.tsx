import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { COMPONENT_LABELS, type LoanFeeWaiver } from "./loanChargesApi";
import { StatusPill } from "../../../components/ui";

export function formatWhen(value: string) {
  return new Date(value).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
}

function coveredText(waiver: LoanFeeWaiver) {
  const all = !Array.isArray(waiver.components) || waiver.components.length === 0;
  return all ? t`Every loan fee` : waiver.covered.map(key => COMPONENT_LABELS[key] ?? key).join(", ");
}

/** Append-only history: a revocation is its own row pointing at the waiver it ends. */
export function WaiverHistory({ waivers, canRevoke, onRevoke }: {
  waivers: LoanFeeWaiver[]; canRevoke: boolean; onRevoke: (waiver: LoanFeeWaiver) => void;
}) {
  return <section aria-label={t`Fee waivers`} className="grid gap-2">
    <h3 className="text-sm font-semibold text-ink">{t`Fee waivers`}</h3>
    <ul className="grid gap-2">
      {waivers.map(waiver => {
        const revocation = waiver.revokes !== null;
        return <li key={waiver.id} className="grid gap-1 rounded-xl border border-line p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-ink">{revocation ? t`Revoked waiver #${String(waiver.revokes)}` : t`Waiver #${waiver.id} · ${coveredText(waiver)}`}</span>
            {revocation ? null : waiver.revoked ? <StatusPill label={t`Revoked`} tone="neutral" />
              : canRevoke ? <button className="desk-button" type="button" onClick={() => onRevoke(waiver)}
                aria-label={t`Revoke waiver #${waiver.id}`}>{t`Revoke`}</button> : <StatusPill label={t`Active`} tone="info" />}
          </div>
          <p className="text-muted">{waiver.created_by_name} · <time dateTime={waiver.created_at}>{formatWhen(waiver.created_at)}</time></p>
          <p className="break-words text-ink">{waiver.reason}</p>
        </li>;
      })}
    </ul>
  </section>;
}
