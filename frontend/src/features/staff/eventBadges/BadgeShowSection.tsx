// What the badge shows: logos (symbol, organisation, event, sponsor strip) and the person's items.
// Turning an optional item on reflows an untouched layout so it has room; a hand-adjusted one keeps every position.
import { t } from "@lingui/core/macro";

import type { BadgeDesigns } from "./badgeApi";
import { Section, SwitchLine } from "./badgeControls";
import type { BadgeElement, Flags } from "./badgeGeometry";
import type { BadgeSettings } from "./badgeNormalize";
import type { Update } from "./BadgeSections";

export type ToggleItem = (flag: keyof Flags, on: boolean, element: BadgeElement) => void;

export function LogosSection({ settings, branding, sponsorMax, update, toggleItem }: { settings: BadgeSettings;
  branding: BadgeDesigns["branding"]; sponsorMax: number; update: Update; toggleItem: ToggleItem }) {
  const sponsors = branding.sponsor_count;
  return <Section title={t`Logos`}>
    <SwitchLine label={t`Space Works symbol`} hint={t`Placed unaltered, with clear space around it.`} checked={settings.showSymbol}
      onChange={(on) => toggleItem("showSymbol", on, "symbol")} />
    <SwitchLine label={t`Organisation logo`} hint={branding.has_organisation_logo ? undefined : t`Add a logo in organisation or space settings first.`}
      disabled={!branding.has_organisation_logo} checked={settings.showLogo && branding.has_organisation_logo}
      onChange={(on) => toggleItem("showLogo", on, "logo")} />
    <SwitchLine label={t`Event logo`} hint={branding.has_event_logo ? undefined : t`Add an image to the event first.`}
      disabled={!branding.has_event_logo} checked={settings.showEventLogo && branding.has_event_logo}
      onChange={(on) => toggleItem("showEventLogo", on, "eventLogo")} />
    <SwitchLine label={t`Sponsor logos`} disabled={sponsors === 0} checked={settings.showSponsors && sponsors > 0}
      hint={sponsors ? t`${sponsors} active sponsors with a logo.` : t`Add sponsors with logos to the event first.`}
      onChange={(on) => toggleItem("showSponsors", on, "sponsors")} />
    {settings.showSponsors && sponsors > 1 ? <label className="grid gap-1 text-xs font-semibold text-muted">
      <span>{t`Sponsors on each badge`}</span>
      <select className="desk-input min-h-11" value={Math.min(settings.sponsorLimit, sponsors)}
        onChange={(event) => update({ sponsorLimit: Number(event.target.value) })}>
        {Array.from({ length: Math.min(sponsorMax, sponsors) }, (_v, index) => index + 1).map((count) =>
          <option key={count} value={count}>{t`Up to ${count}`}</option>)}
      </select>
    </label> : null}
  </Section>;
}

export function ShowSection({ settings, update, toggleItem }: { settings: BadgeSettings; update: Update; toggleItem: ToggleItem }) {
  return <Section title={t`Show on the badge`}>
    <SwitchLine label={t`Attendee name`} checked={settings.showName} onChange={(showName) => update({ showName })} />
    <SwitchLine label={t`Shrink long names to fit`} hint={t`Keeps names on one line, down to 60% of the size.`}
      checked={settings.nameAutoFit} disabled={!settings.showName} onChange={(nameAutoFit) => update({ nameAutoFit })} />
    <SwitchLine label={t`Attendee photo`} hint={t`Their card photo (with consent), or their initials.`} checked={settings.showPhoto}
      onChange={(on) => toggleItem("showPhoto", on, "photo")} />
    {settings.showPhoto ? <div role="radiogroup" aria-label={t`Photo shape`} className="inline-flex w-fit gap-1 rounded-control border border-line bg-surface p-1">
      {([["circle", t`Circle`], ["rounded", t`Rounded square`]] as const).map(([value, label]) =>
        <button key={value} type="button" role="radio" aria-checked={settings.photoShape === value} onClick={() => update({ photoShape: value })}
          className={`min-h-11 rounded-control border px-3 text-sm font-semibold ${settings.photoShape === value ? "border-outline bg-panel text-ink" : "border-transparent text-muted hover:text-ink"}`}>
          {label}</button>)}
    </div> : null}
    <SwitchLine label={t`Attendee email`} checked={settings.showEmail} onChange={(showEmail) => update({ showEmail })} />
    <SwitchLine label={t`Check-in QR`} hint={t`Scanned at the desk to check people in.`} checked={settings.showQr}
      onChange={(showQr) => update({ showQr })} />
  </Section>;
}
