import { t } from "@lingui/core/macro";
import type { ContrastPair } from "../../../lib/brandColours";
import { issuesOf, suggestFix, type ColourKey, type Theme } from "../../../lib/colourFix";

const FIELD_LABEL = (key: ColourKey) => key === "primary_color" ? t`Primary fill` : t`Link colour`;

function Row({ pair, advice }: { pair: ContrastPair; advice?: boolean }) {
  const kind = advice ? t`Advice` : t`Required`;
  return <li className="flex flex-wrap justify-between gap-x-3 text-sm text-danger">
    <span>{pair.mode === "light" ? t`Light` : t`Solid black`}: {pair.pair}</span>
    <span>{kind}: {pair.ratio.toFixed(2)}:1 / {pair.minimum}:1</span>
  </li>;
}

type Props = { theme: Theme; pairs: ContrastPair[]; errors: string[]; valid: boolean; onFix: (key: ColourKey, value: string) => void };

/** Same pairs and thresholds as theme_contrast.py (4.5:1 text, 3:1 UI), plus one advice check the API does not block. */
export function ContrastPanel({ theme, pairs, errors, valid, onFix }: Props) {
  const { blocking, advice } = valid ? issuesOf(theme) : { blocking: [], advice: [] };
  const fix = valid ? suggestFix(theme) : null;
  const text = pairs.filter((pair) => pair.minimum === 4.5), ui = pairs.filter((pair) => pair.minimum === 3);
  const worst = (list: ContrastPair[]) => list.length ? Math.min(...list.map((pair) => pair.ratio)) : 0;
  const ok = valid && blocking.length === 0 && advice.length === 0;
  return <section aria-labelledby="colour-contrast" className="grid gap-2 rounded-card border border-line bg-panel p-4">
    <h4 id="colour-contrast" className="title-section">{t`Contrast checks`}</h4>
    <p className="text-sm text-muted">{t`Text must reach 4.5:1 and component edges 3:1 (WCAG AA), in light and solid-black dark. Lowest text ${worst(text).toFixed(2)}:1, lowest component ${worst(ui).toFixed(2)}:1.`}</p>
    <div aria-live="polite" className="grid gap-1">
      {blocking.length ? <ul className="grid gap-1">{blocking.map((pair) => <Row key={`${pair.mode}-${pair.pair}`} pair={pair} />)}</ul> : null}
      {advice.length ? <ul className="grid gap-1">{advice.map((pair) => <Row key={`${pair.mode}-${pair.pair}`} pair={pair} advice />)}</ul> : null}
      {ok ? <p className="text-sm text-success-ink">{t`All checked pairs meet WCAG AA in both modes.`}</p> : null}
      {blocking.length ? <p className="text-sm text-danger">{t`Saving is blocked until the required checks pass.`}</p> : null}
      {advice.length && !blocking.length ? <p className="text-sm text-muted">{t`Advice does not block saving: buttons are harder to see against the page.`}</p> : null}
      {errors.map((error) => <p className="text-sm text-danger" key={error}>{error}</p>)}
      {!valid ? <p className="text-sm text-danger">{t`Enter a #RGB or #RRGGBB colour. Public pages use Maker Teal until valid colours are saved.`}</p> : null}
    </div>
    {fix ? <div className="flex flex-wrap items-center gap-2">
      <span className="inline-block h-6 w-6 rounded-control border border-outline" style={{ backgroundColor: fix.value }} aria-hidden="true" />
      <button type="button" className="desk-button" onClick={() => onFix(fix.key, fix.value)}>{t`Fix it: use ${fix.value} for ${FIELD_LABEL(fix.key)}`}</button>
    </div> : null}
    <details className="text-sm"><summary className="cursor-pointer font-semibold">{t`All ${pairs.length} checked pairs`}</summary>
      <ul className="mt-2 grid gap-1">{pairs.map((pair) => <li key={`${pair.mode}-${pair.pair}`} className="flex flex-wrap justify-between gap-x-3">
        <span>{pair.mode === "light" ? t`Light` : t`Solid black`}: {pair.pair}</span>
        <span className={pair.ratio >= pair.minimum ? "text-success-ink" : "text-danger"}>{pair.ratio.toFixed(2)}:1 / {pair.minimum}:1 {pair.ratio >= pair.minimum ? t`Pass` : t`Fail`}</span>
      </li>)}</ul>
    </details>
  </section>;
}
