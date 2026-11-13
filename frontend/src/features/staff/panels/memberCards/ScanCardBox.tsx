import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";
import { ScanWorkbench } from "../../../../components/ui";
import { opsStatusLabel } from "../../opsPresentation";
import { useResolveCard } from "./api";
import { PresenceCheckIn } from "./PresenceCheckIn";

const OUTCOME_TEXT = {
  ok: t`Card valid — admit this member.`,
  revoked: t`Card revoked — do not accept it.`,
  inactive: t`Membership not active — do not accept this card.`,
} as const;

/** Refused cards reveal only their outcome; the identity remains private. */
export function ScanCardBox({ makerspaceId }: { makerspaceId: number }) {
  const resolve = useResolveCard(makerspaceId);
  const sequence = useRef(0);
  const lastPayload = useRef("");
  const [recent, setRecent] = useState<{ key: string; label: string; tone: "success" | "danger" }[]>([]);
  const result = !resolve.isPending ? resolve.data : undefined;
  const lookup = (value: string) => {
    if (value.trim()) lastPayload.current = value.trim();
    if (value.trim()) resolve.mutate(value, { onSuccess: row => setRecent(current => [
      { key: String(++sequence.current), label: OUTCOME_TEXT[row.outcome], tone: row.outcome === "ok" ? "success" as const : "danger" as const }, ...current,
    ].slice(0, 5)) });
  };
  return <div aria-label={t`Scan card`}>
    <ScanWorkbench onFind={lookup} onScan={lookup} searchLabel="Card payload"
      helper={t`Scan or paste a card payload to check whether it is still valid.`} findPending={resolve.isPending}
      state={resolve.error ? { status: "error", error: resolve.error instanceof Error ? resolve.error.message : t`Couldn't check that card. Try again.`,
        onRetry: () => resolve.reset() } : { status: "ready" }}
      result={result ? { tone: result.outcome === "ok" ? "success" : "danger", title: OUTCOME_TEXT[result.outcome],
        next: { label: t`Next card`, onClick: () => resolve.reset() },
        children: result.outcome === "ok" ? <div className="grid gap-3">
          <dl className="grid gap-1 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-3">
            <dt>{t`Card`}</dt><dd className="tabular-nums">{result.card_number}</dd>
            <dt>{t`Name`}</dt><dd>{result.printed_name}</dd>
            <dt>{t`Membership`}</dt><dd>{opsStatusLabel(result.membership_status ?? "")}</dd>
          </dl>{result.photo_url ? <img className="h-24 w-24 rounded-lg border border-line object-cover" src={result.photo_url}
            alt={"Photo on file for " + (result.printed_name ?? "this card")} /> : null}
          <PresenceCheckIn makerspaceId={makerspaceId} payload={lastPayload.current} />
        </div> : undefined } : undefined}
      recent={recent} recentTitle="Recent card checks" />
  </div>;
}
