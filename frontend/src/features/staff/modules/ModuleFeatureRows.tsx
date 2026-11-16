import { t } from "@lingui/core/macro";
import type { CardModel, FeatureModel } from "./moduleModel";

function FeatureRow({ feature, disabled, onToggle }: { feature: FeatureModel; disabled: boolean; onToggle: (feature: FeatureModel, on: boolean) => void }) {
  const helpId = `feature-help-${feature.key}`;
  const needId = `feature-needs-${feature.key}`;
  const lockId = `feature-lock-${feature.key}`;
  const described = [feature.help ? helpId : "", feature.needs ? needId : "", feature.lock ? lockId : ""].filter(Boolean).join(" ") || undefined;
  return <li className="flex min-h-11 items-start gap-3 border-t border-line py-2 first:border-0">
    <input type="checkbox" role="switch" className="mt-1 h-5 w-5 shrink-0 accent-accent" aria-label={feature.label} aria-describedby={described}
      checked={feature.on && !feature.needs && !feature.lock} disabled={disabled || !!feature.lock} onChange={event => onToggle(feature, event.target.checked)} />
    <span className="grid min-w-0 gap-0.5 text-sm">
      <span className="break-words text-ink">{feature.label}</span>
      {feature.help ? <span id={helpId} className="break-words text-muted">{feature.help}</span> : null}
      {feature.needs ? <span id={needId} className="text-muted">{t`Needs ${feature.needs.label}. Switching this on offers to switch it on too.`}</span> : null}
      {feature.lock ? <span id={lockId} className="text-muted">{t`Not installed on this server, so it cannot be switched on. Whoever runs the server can add it back.`}</span> : null}
    </span>
  </li>;
}

export function ModuleFeatureRows({ card, id, busy, onToggle }: { card: CardModel; id: string; busy: boolean; onToggle: (feature: FeatureModel, on: boolean) => void }) {
  return <ul id={id} aria-label={t`Features of ${card.label}`} className="mt-3 grid">
    {card.features.map(feature => <FeatureRow key={feature.key} feature={feature} disabled={busy || card.lock === "not_shipped"} onToggle={onToggle} />)}
  </ul>;
}
