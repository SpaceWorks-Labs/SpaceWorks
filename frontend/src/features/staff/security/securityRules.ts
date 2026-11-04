/**
 * The frozen per-space security rows (#128 C-2; `accounts/login_security_settings.py`) as the
 * panel needs them: number ranges, choice labels, and which values are at least as strict as a
 * platform lock (a floor, #111 Q9). The server re-checks every value; this keeps the controls
 * from offering a value it would refuse.
 */
import type { SecuritySetting } from "../../../lib/api/securitySettings";
import { parseCidr, within } from "./cidr";

type IntRule = { min: number; max: number; unit: string; zeroOff?: boolean };
export const INT_RULES: Record<string, IntRule> = {
  "security.remembered_device_days": { min: 1, max: 90, unit: "days" },
  "security.staff_session_max_hours": { min: 1, max: 720, unit: "hours" },
  "security.staff_idle_timeout_minutes": { min: 0, max: 1440, unit: "minutes", zeroOff: true },
};
const CHOICE_LABELS: Record<string, string> = { off: "Off", after_failures: "After failed attempts", always: "Always" };

export const choiceLabel = (value: unknown) => CHOICE_LABELS[String(value)] ?? String(value);
export const asList = (value: unknown) => Array.isArray(value) ? value.map(String) : [];

/** A value as words: "30 days", "Off", "Any network", "2 networks". */
export function describeValue(setting: SecuritySetting, value: unknown) {
  if (setting.kind === "bool") return value ? "On" : "Off";
  if (setting.kind === "choice") return choiceLabel(value);
  if (setting.kind === "list") { const count = asList(value).length; return count ? `${count} ${count === 1 ? "network" : "networks"}` : "Any network"; }
  const rule = INT_RULES[setting.key];
  if (rule?.zeroOff && Number(value) === 0) return "Off";
  return rule ? `${String(value)} ${rule.unit}` : String(value);
}

/** What a lock allows, e.g. "at most 30 days" or "After failed attempts or stricter". */
export function describeFloor(setting: SecuritySetting, floor: unknown) {
  if (setting.kind === "bool") return describeValue(setting, floor);
  if (setting.kind === "choice") return `${choiceLabel(floor)} or stricter`;
  if (setting.kind === "list") return asList(floor).length ? `only networks within ${asList(floor).join(", ")}` : "any network";
  const rule = INT_RULES[setting.key];
  if (rule?.zeroOff && Number(floor) === 0) return "any value";
  return `at most ${describeValue(setting, floor)}`;
}

/** Null when `value` is valid and at least as strict as the lock's floor; otherwise why not. */
export function strictnessProblem(setting: SecuritySetting, value: unknown): string | null {
  const floor = setting.lock?.floor;
  if (setting.kind === "int") {
    const number = Number(value);
    const rule = INT_RULES[setting.key];
    if (!Number.isInteger(number)) return "Enter a whole number.";
    if (rule && (number < rule.min || number > rule.max)) return `Choose ${rule.min}–${rule.max} ${rule.unit}.`;
    if (floor === undefined || floor === null) return null;
    const locked = Number(floor);
    if (rule?.zeroOff && locked === 0) return null;
    if ((rule?.zeroOff && number === 0) || number > locked) return `The platform lock allows ${describeFloor(setting, floor)}.`;
    return null;
  }
  if (setting.kind === "choice") {
    const order = setting.choices.map(String);
    if (!order.includes(String(value))) return "Choose one of the options.";
    if (floor !== undefined && floor !== null && order.indexOf(String(value)) < order.indexOf(String(floor))) {
      return `The platform lock allows ${describeFloor(setting, floor)}.`;
    }
    return null;
  }
  if (setting.kind === "list") {
    const entries = asList(value).map(parseCidr);
    if (entries.some(entry => entry === null)) return "Each entry must be a network like 203.0.113.0/24 or 2001:db8::/32.";
    const floors = asList(floor).map(parseCidr).filter(entry => entry !== null);
    if (!floors.length) return null;
    if (!entries.length || entries.some(entry => !floors.some(outer => within(entry!, outer)))) {
      return `The platform lock allows ${describeFloor(setting, floor)}.`;
    }
  }
  return null;
}
