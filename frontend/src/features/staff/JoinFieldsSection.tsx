import { t } from "@lingui/core/macro";

import { SegmentedControl } from "../../components/ui";

// Parity O-B2: what a plan's join form collects besides its questions. Each part has its own switch
// (`membership.join_photo`, `membership.join_contact_fields`); a value is only sent while its switch is on,
// so a space with the switch off never writes it (the server refuses it then).

export type JoinPlanFields = { join_photo: "off" | "optional" | "required"; join_phone: "hidden" | "optional" | "required"; join_state: "hidden" | "optional" | "required" };
export const EMPTY_JOIN_FIELDS: JoinPlanFields = { join_photo: "off", join_phone: "hidden", join_state: "hidden" };

export const joinPhotoOn = (features: string[]) => features.includes("membership.join_photo");
export const joinContactOn = (features: string[]) => features.includes("membership.join_contact_fields");

export function joinPlanFields(plan: Partial<JoinPlanFields>): JoinPlanFields {
  return { join_photo: plan.join_photo ?? "off", join_phone: plan.join_phone ?? "hidden", join_state: plan.join_state ?? "hidden" };
}

export function joinPlanInput(value: JoinPlanFields, features: string[]): Partial<JoinPlanFields> {
  return {
    ...(joinPhotoOn(features) ? { join_photo: value.join_photo } : {}),
    ...(joinContactOn(features) ? { join_phone: value.join_phone, join_state: value.join_state } : {}),
  };
}

/** The plan form's "Join form" block: photo off/optional/required, phone and state hidden/optional/required. */
export function JoinFieldsSection({ value, onChange, features }: { value: JoinPlanFields; onChange: (value: JoinPlanFields) => void; features: string[] }) {
  const photo = joinPhotoOn(features);
  const contact = joinContactOn(features);
  if (!photo && !contact) return null;
  const set = <K extends keyof JoinPlanFields>(key: K, next: JoinPlanFields[K]) => onChange({ ...value, [key]: next });
  const modes = [{ value: "hidden", label: t`Don't ask` }, { value: "optional", label: t`Optional` }, { value: "required", label: t`Required` }];
  return <fieldset className="grid gap-3 rounded-xl border border-line p-3 sm:col-span-3">
    <legend className="px-1 text-sm font-semibold text-ink">{t`Join form extras`}</legend>
    <p className="text-sm text-muted">{t`Asked on this plan's join form, after its questions. Answers reach the member's record only when they join, and never replace what is already there.`}</p>
    {photo ? <div className="grid gap-1">
      <span aria-hidden="true" className="text-sm font-medium text-ink">{t`Card photo`}</span>
        <SegmentedControl label={t`Card photo`} value={value.join_photo} onChange={(next) => set("join_photo", next as JoinPlanFields["join_photo"])}
        options={[{ value: "off", label: t`Don't ask` }, { value: "optional", label: t`Optional` }, { value: "required", label: t`Required` }]} />
      <p className="text-sm text-muted">{t`The applicant crops it and agrees to it being stored. It goes on their member card only if the card has no photo yet.`}</p>
    </div> : null}
    {contact ? <>
      <div className="grid gap-1">
        <span aria-hidden="true" className="text-sm font-medium text-ink">{t`Phone number`}</span>
        <SegmentedControl label={t`Phone number`} value={value.join_phone} onChange={(next) => set("join_phone", next as JoinPlanFields["join_phone"])} options={modes} />
        <p className="text-sm text-muted">{t`With a country code. Saved to their account only if it has no phone number yet.`}</p>
      </div>
      <div className="grid gap-1">
        <span aria-hidden="true" className="text-sm font-medium text-ink">{t`State`}</span>
        <SegmentedControl label={t`State`} value={value.join_state} onChange={(next) => set("join_state", next as JoinPlanFields["join_state"])} options={modes} />
        <p className="text-sm text-muted">{t`An Indian state or union territory, used as the GST place of supply on their invoices.`}</p>
      </div>
    </> : null}
  </fieldset>;
}
