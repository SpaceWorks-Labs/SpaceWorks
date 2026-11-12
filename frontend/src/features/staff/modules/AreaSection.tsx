import { t } from "@lingui/core/macro";
import { ModuleCard, type CardActions } from "./ModuleCard";
import type { AreaModel, CardModel } from "./moduleModel";

export type AreaProps = {
  area: AreaModel; cards: CardModel[]; opened: ReadonlySet<string>; onOpen: (key: string, open: boolean) => void;
  actions: CardActions; names: (keys: string[]) => string; onBulk?: (area: AreaModel, on: boolean) => void;
};

export function AreaSection({ area, cards, opened, onOpen, actions, names, onBulk }: AreaProps) {
  const switchable = area.cards.filter(card => card.row && !card.lock);
  const on = switchable.filter(card => card.on).length;
  const label = area.label;
  const headingId = `area-${area.key}`;
  return <section aria-labelledby={headingId} className="@container grid min-w-0 gap-3">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0 flex-1 basis-56">
        <h2 id={headingId} className="break-words text-lg font-semibold text-ink">{label}</h2>
        <p className="break-words text-sm text-muted">{area.alwaysOn ? t`Always on. ${area.description}` : area.description}</p>
        {switchable.length ? <p className="text-sm text-muted">{t`${on} of ${switchable.length} switched on`}</p> : null}
      </div>
      {onBulk && switchable.length > 1 ? <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={actions.busy || on === switchable.length} aria-label={t`Switch on all of ${label}`} onClick={() => onBulk(area, true)}>{t`Switch on all`}</button>
        <button type="button" className="desk-button" disabled={actions.busy || on === 0} aria-label={t`Switch off all of ${label}`} onClick={() => onBulk(area, false)}>{t`Switch off all`}</button>
      </div> : null}
    </div>
    <div className="grid min-w-0 gap-3 @2xl:grid-cols-2">
      {cards.map(card => <ModuleCard key={card.key} card={card} open={opened.has(card.key)} onOpen={open => onOpen(card.key, open)} actions={actions} names={names} />)}
    </div>
  </section>;
}
