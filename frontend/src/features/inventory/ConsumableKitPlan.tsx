import { t } from "@lingui/core/macro";
import { useState } from "react";
import { PendingIntake, type SelfBody, type SelfResult } from "./contextualIntake";
import { KitChoice } from "./KitChoice";
import type { SafeKit } from "./equipmentKitsApi";
import { useContextualIntent } from "./useContextualIntent";

export function ConsumableKitPlan({ scope, slug, pendingOwner, onLock, onDone, admitted, onSuccess }: { scope: string; slug: string; pendingOwner: PendingIntake<SelfBody>; onLock: () => void; onDone: () => void; admitted: () => boolean; onSuccess?: (result: SelfResult, scope: string) => void }) {
  const [kit, setKit] = useState<SafeKit | null>(null); const [purpose, setPurpose] = useState(""); const [denied, setDenied] = useState(false); const [message, setMessage] = useState("");
  const intent = useContextualIntent(scope, slug, pendingOwner, () => { setKit(null); setDenied(true); }, onDone, admitted, onSuccess);
  async function finish(result: ReturnType<typeof intent.retry>) {
    const value = await result;
    if (value) { setKit(null); setPurpose(""); if (!onSuccess) { onDone(); setMessage(value.kind === "consumable_plan" ? t`Consumable plan saved. No stock was used.` : t`Equipment request submitted for review.`); } }
  }
  if (denied) return <p className="text-sm text-muted" role="status">{t`This plan is unavailable for your access.`}</p>;
  return <section className="grid gap-3" data-replay-block><h3 className="title-section">{t`Plan consumables`}</h3>
    <p className="text-sm text-muted">{t`A plan does not use stock. Staff record actual use separately.`}</p>
    <KitChoice scope={scope} slug={slug} value={kit} onChange={setKit} disabled={intent.state === "sending" || intent.state === "uncertain"} consumableOnly />
    <label className="grid gap-1 text-sm">{t`Purpose`}<input className="desk-input" value={purpose} disabled={intent.state === "sending" || intent.state === "uncertain"} onChange={event => setPurpose(event.target.value)} /></label>
    {intent.error ? <p className="text-sm text-danger" role="alert">{intent.state === "uncertain" ? t`The outcome may be unknown. Review your history or retry the same plan.` : t`Check your plan and try again.`}</p> : null}
    {intent.state === "uncertain" ? <button type="button" className="desk-button w-fit" onClick={() => void finish(intent.retry())}>{t`Retry the same plan`}</button> : <button type="button" className="desk-button-primary w-fit" disabled={!kit || !purpose.trim() || intent.state === "sending"} onClick={() => { if (kit && admitted()) { onLock(); void finish(intent.begin({ requested_for: purpose.trim(), kit: { id: kit.id, version: kit.version } }, null, null)); } }}>{intent.state === "sending" ? t`Saving plan…` : t`Save plan`}</button>}
    {message ? <p className="text-sm text-success-ink" role="status">{message}</p> : null}
  </section>;
}
