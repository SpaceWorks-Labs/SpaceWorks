import { t } from "@lingui/core/macro";
import { ChevronDown } from "lucide-react";
import { StatusPill } from "../../../components/ui";
import { workflowLabel } from "../../../lib/moduleLabels";
import { ModuleFeatureRows } from "./ModuleFeatureRows";
import { cardState, type CardModel, type FeatureModel } from "./moduleModel";

export type CardActions = { busy: boolean; onToggle: (card: CardModel, on: boolean) => void; onFeature: (card: CardModel, feature: FeatureModel, on: boolean) => void };

function lockText(card: CardModel): string | null {
  if (card.lock === "core") return t`Always on. This is part of the core system and cannot be switched off.`;
  if (card.lock === "not_shipped") return t`Not installed on this server, so it cannot be switched on. Whoever runs the server can add it back.`;
  if (card.lock === "limit" && !card.on) return t`This area has a usage limit on this hosting plan. Ask the platform administrator to switch it on.`;
  return null;
}

/** Lines under the description: what the switch does next, in the words of the registry. */
function notes(card: CardModel, names: (keys: string[]) => string): string[] {
  const row = card.row;
  if (!row) return [];
  const out: string[] = [];
  const lock = lockText(card);
  if (lock) out.push(lock);
  if (!card.on && row.pulls_in.length) out.push(t`Switching on also switches on: ${names(row.pulls_in)}.`);
  if (card.on && row.required_by.length) out.push(t`Needed by ${names(row.required_by)}. Those switch off with it.`);
  if (card.on && !card.lock) {
    const parts = [...row.workflows.map(workflowLabel), ...(card.features.length ? [t`${card.features.length} features`] : [])];
    out.push(parts.length ? t`Switching off hides: ${parts.join(", ")}. Your data is kept.` : t`Switching off hides this area. Your data is kept.`);
  }
  return out;
}

export function ModuleCard({ card, open, onOpen, actions, names }: { card: CardModel; open: boolean; onOpen: (open: boolean) => void; actions: CardActions; names: (keys: string[]) => string }) {
  const state = cardState(card);
  const id = `module-${card.key}`;
  const lines = notes(card, names);
  const featuresOn = card.features.filter(feature => feature.on && !feature.needs && !feature.lock).length;
  return <article id={id} aria-labelledby={`${id}-title`} className="min-w-0 rounded-control border border-line bg-panel p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1 basis-48">
        <h3 id={`${id}-title`} className="break-words text-base font-semibold text-ink">{card.label}</h3>
        {card.description ? <p className="mt-1 break-words text-sm text-muted">{card.description}</p> : null}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <StatusPill tone={state === "on" ? "success" : "neutral"} label={state === "locked" ? t`Locked` : state === "on" ? t`On` : t`Off`} />
        {card.row ? <input type="checkbox" role="switch" className="h-6 w-6 accent-accent" aria-label={card.label} aria-describedby={lines.length ? `${id}-notes` : undefined}
          checked={card.on} disabled={actions.busy || state === "locked"} onChange={event => actions.onToggle(card, event.target.checked)} /> : null}
      </div>
    </div>
    {lines.length ? <div id={`${id}-notes`} className="mt-3 grid gap-1">{lines.map(line => <p key={line} className="text-sm text-muted">{line}</p>)}</div> : null}
    {card.features.length ? <>
      <button type="button" className="mt-3 flex min-h-11 w-full items-center justify-between gap-2 rounded-control border border-line px-3 text-left text-sm font-semibold text-ink hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        aria-expanded={open} aria-controls={`${id}-features`} onClick={() => onOpen(!open)}>
        <span>{t`Features: ${featuresOn} of ${card.features.length} on`}</span>
        <ChevronDown aria-hidden="true" className={`h-4 w-4 shrink-0 ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? <ModuleFeatureRows card={card} id={`${id}-features`} busy={actions.busy} onToggle={(feature, on) => actions.onFeature(card, feature, on)} /> : null}
    </> : null}
  </article>;
}
