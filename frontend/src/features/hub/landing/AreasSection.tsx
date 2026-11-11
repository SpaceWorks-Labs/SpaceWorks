import { t } from "@lingui/core/macro";
import { ArrowRight, Check } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { DOCS_LINKS } from "../hubLinks";
import { hubAreas, type AreaTone } from "./areas";

const TONES: Record<AreaTone, string> = {
  success: "bg-success text-on-success", warn: "bg-warn text-on-warn", info: "bg-info text-on-info", neutral: "border border-line bg-surface text-ink",
};

/** Six areas as WAI-ARIA tabs: arrow keys move between them, each panel carries a sample record. */
export function AreasSection() {
  const areas = hubAreas();
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const select = (index: number, focus = false) => {
    const next = (index + areas.length) % areas.length;
    setActive(next);
    if (focus) refs.current[next]?.focus();
  };
  const area = areas[active];
  const Icon = area.icon;
  return <section id="areas" aria-labelledby="areas-title" className="sw-hub-section">
    <div className="sw-hub-wrap">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-end md:gap-10">
        <h2 id="areas-title" className="sw-hub-h2">{t`Turn on what you run. Leave off what you don’t.`}</h2>
        <p className="sw-hub-lede">{t`Each makerspace chooses its own areas. Switch one off and it leaves every screen; its history stays.`}</p>
      </div>
      <div className="mt-10 grid gap-6 lg:mt-14 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)] lg:gap-10">
        <div role="tablist" aria-label={t`Areas`} aria-orientation="vertical" className="sw-hub-area-tabs">
          {areas.map((item, index) => {
            const TabIcon = item.icon;
            return <button key={item.key} ref={node => { refs.current[index] = node; }} type="button" role="tab"
              id={`area-tab-${item.key}`} aria-selected={index === active} aria-controls="area-panel" tabIndex={index === active ? 0 : -1}
              className="sw-hub-area-tab" onClick={() => select(index)}
              onKeyDown={event => {
                const keys: Record<string, number> = { ArrowDown: index + 1, ArrowRight: index + 1, ArrowUp: index - 1, ArrowLeft: index - 1, Home: 0, End: areas.length - 1 };
                if (event.key in keys) { event.preventDefault(); select(keys[event.key], true); }
              }}>
              <span className="sw-hub-area-icon" aria-hidden="true"><TabIcon size={20} /></span>
              <span className="grid min-w-0 text-left"><span className="font-semibold">{item.name}</span>
                <span className="text-sm text-muted">{item.tagline}</span></span>
            </button>;
          })}
        </div>
        <div id="area-panel" role="tabpanel" aria-labelledby={`area-tab-${area.key}`} tabIndex={0} key={area.key} className="sw-hub-area-panel">
          <div className="grid content-start gap-5">
            <span className="sw-hub-area-icon sw-hub-area-icon-lg" aria-hidden="true"><Icon size={28} /></span>
            <h3 className="font-display text-3xl font-extrabold tracking-[-0.02em] text-ink">{area.name}</h3>
            <p className="text-lg leading-7 text-muted">{area.body}</p>
            <ul className="grid gap-3">{area.points.map(point => <li key={point} className="flex items-start gap-3 text-ink">
              <Check size={18} className="mt-1 shrink-0 text-accent-ink" aria-hidden="true" />{point}</li>)}</ul>
            <Link to={DOCS_LINKS.search(area.docsQuery)} className="desk-button-ghost w-fit -ml-3 gap-2">
              {t`Read the ${area.name} docs`}<ArrowRight size={16} aria-hidden="true" /></Link>
          </div>
          <figure className="sw-hub-record" aria-label={t`Sample ${area.name} record`}>
            <figcaption className="border-b border-line px-5 py-4 font-semibold text-ink">{area.record.title}</figcaption>
            <ul>{area.record.rows.map(row => <li key={row.label} className="flex items-center justify-between gap-4 border-b border-line px-5 py-4 last:border-b-0">
              <span className="min-w-0 text-ink">{row.label}</span>
              <span className={`inline-flex min-h-7 shrink-0 items-center rounded-full px-3 text-xs font-semibold ${TONES[row.tone]}`}>{row.value}</span>
            </li>)}</ul>
            <p className="bg-surface px-5 py-3 text-xs text-muted">{t`Sample data`}</p>
          </figure>
        </div>
      </div>
    </div>
  </section>;
}
