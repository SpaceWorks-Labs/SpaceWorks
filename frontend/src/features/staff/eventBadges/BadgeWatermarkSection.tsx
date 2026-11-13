// The badge watermark, as in SpaceWorks-Events: none or text (up to 32 characters), strength 4–30 %, the
// accent or text colour, and an angle. Events also offers an image watermark; event badges here carry text
// only (the card engine compiles badges without an uploaded asset), so that choice is shown as unavailable.
import { t } from "@lingui/core/macro";

import { NumberSlider, Section } from "./badgeControls";
import type { BadgeSettings, Watermark } from "./badgeNormalize";
import type { Update } from "./BadgeSections";

const segment = (active: boolean) =>
  `min-h-11 rounded-control border px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${active ? "border-outline bg-panel text-ink" : "border-transparent text-muted hover:text-ink"}`;

export function BadgeWatermarkSection({ settings, update }: { settings: BadgeSettings; update: Update }) {
  const mark = settings.watermark;
  const kind = mark.kind === "text" ? "text" : "none";
  const set = (patch: Partial<Watermark>) => update({ watermark: { ...mark, ...patch } });
  return <Section title={t`Watermark`}>
    <div role="radiogroup" aria-label={t`Watermark`} className="inline-flex w-fit gap-1 rounded-control border border-line bg-surface p-1">
      <button type="button" role="radio" aria-checked={kind === "none"} className={segment(kind === "none")} onClick={() => set({ kind: "none" })}>{t`None`}</button>
      <button type="button" role="radio" aria-checked={kind === "text"} className={segment(kind === "text")} onClick={() => set({ kind: "text" })}>{t`Text`}</button>
      <button type="button" role="radio" aria-checked={false} disabled className={segment(false)} title={t`Event badges carry a text watermark only.`}>{t`Image`}</button>
    </div>
    <p className="text-xs text-muted">{t`Image watermarks aren't available on event badges; an imported one is dropped.`}</p>
    {kind === "text" ? <>
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Watermark text`}</span>
        <input className="desk-input min-h-11" maxLength={32} value={mark.text} placeholder={t`ATTENDEE`}
          onChange={(event) => set({ text: event.target.value })} /></label>
      <NumberSlider label={t`Strength`} unit="%" min={4} max={30} step={1} value={mark.opacityPct} onChange={(opacityPct) => set({ opacityPct })} />
      <div role="radiogroup" aria-label={t`Watermark colour`} className="inline-flex w-fit gap-1 rounded-control border border-line bg-surface p-1">
        {([["accent", t`Accent colour`], ["text", t`Text colour`]] as const).map(([value, label]) =>
          <button key={value} type="button" role="radio" aria-checked={mark.colour === value} className={segment(mark.colour === value)}
            onClick={() => set({ colour: value })}>{label}</button>)}
      </div>
      <NumberSlider label={t`Angle`} unit="°" min={-60} max={60} step={5} value={mark.angleDeg} onChange={(angleDeg) => set({ angleDeg })} />
    </> : null}
  </Section>;
}
