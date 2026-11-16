import { t } from "@lingui/core/macro";
// One level of the card-design approval switch (#136): on, off, or follow the broader level.
// Levels from most to least specific: event, ID programme, organisation, space.

export type ApprovalValue = boolean | null;

const toValue = (raw: string): ApprovalValue => (raw === "on" ? true : raw === "off" ? false : null);
const toRaw = (value: ApprovalValue) => (value === true ? "on" : value === false ? "off" : "inherit");
export const approvalWord = (value: boolean) => (value ? "needs approval" : "no approval");

export function ApprovalLevelSelect({ label, value, inherited, inheritLabel, onChange, disabled = false, allowInherit = true }: {
  label: string; value: ApprovalValue; inherited: boolean; inheritLabel: string; onChange: (value: ApprovalValue) => void;
  disabled?: boolean; allowInherit?: boolean;
}) {
  return <label className="grid gap-1 text-xs font-semibold text-muted">
    <span>{label}</span>
    <select className="desk-input min-h-11" value={toRaw(value)} disabled={disabled}
      onChange={(event) => onChange(toValue(event.target.value))}>
      {allowInherit ? <option value="inherit">{t`${inheritLabel} (now: ${approvalWord(inherited)})`}</option> : null}
      <option value="on">{t`Edits need a Space Manager's approval`}</option>
      <option value="off">{t`Edits publish straight away`}</option>
    </select>
  </label>;
}
