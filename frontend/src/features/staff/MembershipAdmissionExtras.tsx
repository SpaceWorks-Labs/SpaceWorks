import { t } from "@lingui/core/macro";
import type { AdmissionSettings } from "../members/membershipAdmissionApi";

// `fresh` marks a purpose added in this edit: its key follows its name until saved; a
// saved key never changes, so the ledger keeps matching it. The server drops `fresh`.
type Purpose = { key: string; label: string; description: string; fresh?: boolean };
const slugify = (text: string) => text.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64);

/** Release-2 admission settings, each shown only while its switch is on (#95):
 * the lapse days for "again after a lapse", the member-number pattern (X12) and the
 * consent ledger's purposes and notice version (X10). */
export function MembershipAdmissionExtras({ value, features, onChange }: {
  value: AdmissionSettings; features: string[]; onChange: (next: AdmissionSettings) => void;
}) {
  const on = (key: string) => features.includes(`membership.${key}`);
  const purposes = value.consent_purposes ?? [];
  const setPurposes = (next: Purpose[]) => onChange({ ...value, consent_purposes: next });
  return <>
    {value.rejoin_dues_rule === "after_lapse" ? <label className="grid gap-1 text-sm text-ink">{t`Days away that count as a lapse`}<input className="desk-input" type="number" min={1} max={3650} value={value.rejoin_after_days ?? 365}
        onChange={(event) => onChange({ ...value, rejoin_after_days: Number(event.target.value) })} /></label> : null}
    {on("member_numbers") ? <label className="grid gap-1 text-sm text-ink">{t`Member number pattern`}<input className="desk-input" maxLength={40} placeholder="{number:4}" value={value.member_number_pattern ?? ""}
        onChange={(event) => onChange({ ...value, member_number_pattern: event.target.value })} />
      <span className="text-muted">{t`Use ${"{number}"} or ${"{number:4}"} once, and optionally ${"{year}"}, e.g. TNK-${"{number:4}"}. Numbers never change.`}</span>
    </label> : null}
    {on("consent") ? <fieldset className="grid gap-3 rounded border border-line p-3">
      <legend className="text-sm font-semibold text-ink">{t`Consents members can give`}</legend>
      <label className="grid gap-1 text-sm text-ink">{t`Privacy notice version`}<input className="desk-input" maxLength={64} value={value.privacy_notice_version ?? ""}
          onChange={(event) => onChange({ ...value, privacy_notice_version: event.target.value })} /></label>
      {purposes.map((purpose, index) => <div key={index} className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]">
        <input className="desk-input" aria-label={t`Purpose ${index + 1} name`} maxLength={120} value={purpose.label}
          onChange={(event) => setPurposes(purposes.map((row, at) => at === index ? { ...row, label: event.target.value, key: (row as Purpose).fresh ? slugify(event.target.value) : row.key } : row))} />
        <input className="desk-input" aria-label={t`Purpose ${index + 1} description`} maxLength={500} value={purpose.description}
          onChange={(event) => setPurposes(purposes.map((row, at) => at === index ? { ...row, description: event.target.value } : row))} />
        <button className="desk-button" type="button" onClick={() => setPurposes(purposes.filter((_, at) => at !== index))}>{t`Remove`}</button>
      </div>)}
      {purposes.length < 20 ? <div><button className="desk-button" type="button"
        onClick={() => setPurposes([...purposes, { key: "", label: "", description: "", fresh: true }])}>{t`Add a purpose`}</button></div> : null}
      <p className="text-sm text-muted">{t`Members agree to each purpose themselves and can withdraw at any time. There are no guardian or age fields.`}</p>
    </fieldset> : null}
  </>;
}
