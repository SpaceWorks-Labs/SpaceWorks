import { t } from "@lingui/core/macro";
import { useId, useMemo } from "react";

import type { JoinFieldModes } from "../membershipAdmissionApi";
import { JoinPhotoField } from "./JoinPhotoField";
import { GST_STATES, callingCodeOptions, type JoinExtrasDraft, type JoinExtrasErrors } from "./joinFieldsModel";

/**
 * Parity O-B2: what a plan's join form asks besides its questions -- a phone number with its country
 * code, a state (the GST place of supply) and a card photo. Fields a plan does not ask for are not
 * rendered at all. `onFile` (a resubmission) marks values that may already be held: the server keeps those
 * when they are left blank, so the browser does not insist on them.
 */
export function JoinFormExtras({ modes, value, onChange, errors = {}, disabled = false, onFile = {} }: {
  modes: JoinFieldModes; value: JoinExtrasDraft; onChange: (value: JoinExtrasDraft) => void; errors?: JoinExtrasErrors;
  disabled?: boolean; onFile?: { phone?: boolean; state?: boolean; photo?: boolean };
}) {
  const phoneId = useId();
  const regionId = useId();
  const stateId = useId();
  const codes = useMemo(() => callingCodeOptions(), []);
  const set = (patch: Partial<JoinExtrasDraft>) => onChange({ ...value, ...patch });
  const keep = t`Leave blank to keep the number you gave before, if any.`;
  return <fieldset disabled={disabled} className="grid min-w-0 gap-4">
    <legend className="sr-only">{t`Your details`}</legend>
    {modes.phone !== "hidden" ? <div className="grid min-w-0 gap-1">
      <label htmlFor={phoneId} className="text-sm font-semibold text-ink">{modes.phone === "required" ? t`Phone number (required)` : t`Phone number (optional)`}</label>
      <div className="flex min-w-0 flex-wrap gap-2">
        <label htmlFor={regionId} className="sr-only">{t`Country code`}</label>
        <select id={regionId} className="desk-input w-full sm:w-56" value={value.region} onChange={(event) => set({ region: event.target.value })}>
          {codes.map((option) => <option key={option.region} value={option.region}>{option.label}</option>)}
        </select>
        <input id={phoneId} className="desk-input min-w-0 flex-1 basis-40" type="tel" inputMode="tel" autoComplete="tel-national" maxLength={20}
          value={value.national} aria-invalid={Boolean(errors.phone)} aria-describedby={errors.phone ? `${phoneId}-error` : undefined}
          onChange={(event) => set({ national: event.target.value })} />
      </div>
      {onFile.phone ? <p className="text-sm text-muted">{keep}</p> : null}
      {errors.phone ? <p id={`${phoneId}-error`} role="alert" className="text-sm text-danger">{errors.phone}</p> : null}
    </div> : null}
    {modes.state !== "hidden" ? <div className="grid min-w-0 gap-1">
      <label htmlFor={stateId} className="text-sm font-semibold text-ink">{modes.state === "required" ? t`State (required)` : t`State (optional)`}</label>
      <select id={stateId} className="desk-input max-w-full sm:max-w-sm" value={value.state_code} aria-invalid={Boolean(errors.state_code)}
        aria-describedby={errors.state_code ? `${stateId}-error` : `${stateId}-hint`} onChange={(event) => set({ state_code: event.target.value })}>
        <option value="">{onFile.state ? t`Keep what I gave before` : t`Choose your state`}</option>
        {GST_STATES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
      </select>
      <p id={`${stateId}-hint`} className="text-sm text-muted">{t`Used as the place of supply on your tax invoices.`}</p>
      {errors.state_code ? <p id={`${stateId}-error`} role="alert" className="text-sm text-danger">{errors.state_code}</p> : null}
    </div> : null}
    {modes.photo !== "off" ? <JoinPhotoField required={modes.photo === "required"} file={value.photo} consent={value.consent}
      onFile={(photo) => set({ photo, consent: photo ? value.consent : false })} onConsent={(consent) => set({ consent })}
      error={errors.photo} onFileNote={onFile.photo ? t`A photo you sent before is kept unless you choose a new one here.` : undefined} />
      : null}
  </fieldset>;
}
