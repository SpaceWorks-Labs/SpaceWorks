// The selected item's properties, as in SpaceWorks-Events: text size, box width or size, bold, position from
// the left and top, align on the badge, and reset (this item or the whole layout).
import { t } from "@lingui/core/macro";

import type { BadgeDesigns } from "./badgeApi";
import { NumberSlider, SwitchLine } from "./badgeControls";
import { elementBoxHeight, ELEMENTS, isSquare, isText, layoutForPaper, minimumElementSize, type BadgeElement } from "./badgeGeometry";
import { elementLabels } from "./badgeLabels";
import { layoutFlags, type BadgeSettings } from "./badgeNormalize";
import { SAFE_MARGIN_MM } from "./BadgeCanvas";
import type { Update } from "./BadgeSections";

export function visibleItems(settings: BadgeSettings, branding: BadgeDesigns["branding"]): Record<BadgeElement, boolean> {
  return {
    header: Boolean((settings.showBadgeLabel && settings.badgeLabel.trim()) || settings.heading.trim()),
    name: settings.showName, email: settings.showEmail, details: settings.printFieldKeys.length > 0, qr: settings.showQr,
    footer: settings.showFooter && Boolean(settings.footerText.trim()),
    logo: settings.showLogo && branding.has_organisation_logo, eventLogo: settings.showEventLogo && branding.has_event_logo,
    symbol: settings.showSymbol, photo: settings.showPhoto, sponsors: settings.showSponsors && branding.sponsor_count > 0,
    idNumber: settings.showIdNumber, validUntil: settings.showValidUntil,
  };
}

export function BadgeInspector({ settings, branding, selected, onSelect, update }: { settings: BadgeSettings;
  branding: BadgeDesigns["branding"]; selected: BadgeElement; onSelect: (element: BadgeElement) => void; update: Update }) {
  const labels = elementLabels();
  const visible = visibleItems(settings, branding);
  const text = isText(selected);
  const at = settings.elementPositions[selected];
  const size = settings.elementSizes[selected];
  const height = elementBoxHeight(selected, settings.elementSizes, settings.widthMm, settings.heightMm);
  const place = (xMm: number, yMm: number) => update({ elementPositions: { ...settings.elementPositions,
    [selected]: { xMm: Math.round(xMm * 10) / 10, yMm: Math.round(yMm * 10) / 10 } } });
  const align: [string, () => void][] = [
    [t`Left`, () => place(SAFE_MARGIN_MM, at.yMm)], [t`Centre`, () => place((settings.widthMm - size) / 2, at.yMm)],
    [t`Right`, () => place(settings.widthMm - size - SAFE_MARGIN_MM, at.yMm)], [t`Top`, () => place(at.xMm, SAFE_MARGIN_MM)],
    [t`Middle`, () => place(at.xMm, (settings.heightMm - height) / 2)],
    [t`Bottom`, () => place(at.xMm, settings.heightMm - height - SAFE_MARGIN_MM)],
  ];
  const fresh = () => layoutForPaper(settings.template, settings.widthMm, settings.heightMm, layoutFlags(settings));
  const resetItem = () => {
    const layout = fresh();
    update({ elementPositions: { ...settings.elementPositions, [selected]: layout.elementPositions[selected] },
      elementSizes: { ...settings.elementSizes, [selected]: layout.elementSizes[selected] },
      elementTextSizes: { ...settings.elementTextSizes, [selected]: layout.elementTextSizes[selected] },
      elementBold: { ...settings.elementBold, [selected]: layout.elementBold[selected] } });
  };
  const minimum = minimumElementSize(selected);
  const coordinate = (label: string, value: number, apply: (value: number) => void) =>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{label}</span>
      <input className="desk-input min-h-11 tabular-nums" type="number" step={settings.gridSizeMm} value={value}
        onChange={(event) => { if (event.target.value.trim()) apply(Number(event.target.value)); }} /></label>;

  return <div className="grid gap-5">
    <div className="grid gap-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t`Items`}</h4>
      <div role="radiogroup" aria-label={t`Select an item`} className="flex flex-wrap gap-1.5">
        {ELEMENTS.filter((element) => visible[element] || element === selected).map((element) =>
          <button key={element} type="button" role="radio" aria-checked={selected === element} onClick={() => onSelect(element)}
            className={`min-h-11 rounded-full border px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${selected === element ? "border-outline bg-ink text-panel" : "border-line text-muted hover:bg-surface hover:text-ink"}`}>
            {labels[element]}</button>)}
      </div>
    </div>
    <div className="grid gap-3 rounded-control border border-line p-3.5">
      <p className="text-sm font-semibold text-ink">{labels[selected]}</p>
      {!visible[selected] ? <p className="text-xs text-muted">{t`Hidden on the badge right now.`}</p> : null}
      {text ? <NumberSlider label={t`Text size`} unit="pt" min={6} max={48} step={0.5} value={settings.elementTextSizes[selected]}
        onChange={(value) => update({ elementTextSizes: { ...settings.elementTextSizes, [selected]: value } })} /> : null}
      <NumberSlider label={isSquare(selected) ? t`Size` : selected === "sponsors" ? t`Strip width` : t`Box width`} unit="mm"
        min={minimum} max={Math.max(minimum, settings.widthMm - 4)} step={1} value={size}
        onChange={(value) => update({ elementSizes: { ...settings.elementSizes, [selected]: value } })} />
      {text ? <SwitchLine label={t`Bold`} checked={settings.elementBold[selected]}
        onChange={(bold) => update({ elementBold: { ...settings.elementBold, [selected]: bold } })} /> : null}
      <div className="grid grid-cols-2 gap-2">
        {coordinate(t`From left (mm)`, at.xMm, (x) => place(x, at.yMm))}
        {coordinate(t`From top (mm)`, at.yMm, (y) => place(at.xMm, y))}
      </div>
      <div className="grid gap-1.5">
        <p className="text-xs text-muted">{t`Align on the badge`}</p>
        <div className="grid grid-cols-3 gap-1">
          {align.map(([label, run]) => <button key={label} type="button" className="desk-button min-h-11 px-2" onClick={run}>{label}</button>)}
        </div>
      </div>
      <button type="button" className="desk-button-ghost min-h-11 justify-self-start" onClick={resetItem}>{t`Reset this item`}</button>
    </div>
    {selected === "qr" && size < 20 ? <p role="status" className="text-xs text-warn-ink">
      {t`The QR always prints at least 20 mm (18 mm on ID cards) so it scans reliably.`}</p> : null}
    {selected === "symbol" ? <p className="text-xs text-muted">{t`Keep a quarter of the symbol's height clear on every side.`}</p> : null}
    <button type="button" className="desk-button-ghost min-h-11 justify-self-start" onClick={() => update(fresh())}>
      {t`Reset the whole layout`}</button>
  </div>;
}
