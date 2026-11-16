import { t } from "@lingui/core/macro";
import type { ShopSettings } from "./staffShopApi";

export type ShopSettingValues = Required<Omit<ShopSettings, "updated_at">>;
type NumericKey = Exclude<keyof ShopSettingValues, "policy_text" | "pickup_note">;
export const SHOP_NUMBER_FIELDS: { key: NumericKey; label: string; hint: string; min: number; max: number }[] = [
  { key: "online_hold_minutes", label: t`Online hold (minutes)`, hint: t`How long stock is set aside while a buyer pays online.`, min: 5, max: 120 },
  { key: "desk_hold_hours", label: t`Pay-at-desk hold (hours)`, hint: t`How long an unpaid order waits at the desk.`, min: 1, max: 720 },
  { key: "returns_window_days", label: t`Returns window (days)`, hint: t`Days after payment that items can come back. Zero means no returns.`, min: 0, max: 365 },
  { key: "first_reminder_days", label: t`First pickup reminder (days)`, hint: t`Days after an order is ready.`, min: 1, max: 90 },
  { key: "second_reminder_days", label: t`Second pickup reminder (days)`, hint: t`Days after an order is ready.`, min: 1, max: 180 },
  { key: "uncollected_cancel_days", label: t`Cancel uncollected after (days)`, hint: t`Paid orders then open a refund case.`, min: 1, max: 365 },
];
export const SHOP_SETTING_DEFAULTS: ShopSettingValues = { online_hold_minutes: 15, desk_hold_hours: 48,
  returns_window_days: 14, first_reminder_days: 3, second_reminder_days: 7, uncollected_cancel_days: 30,
  policy_text: "", pickup_note: "" };

export function shopSettingsProblem(values: ShopSettingValues) {
  for (const field of SHOP_NUMBER_FIELDS) {
    if (!Number.isInteger(values[field.key]) || values[field.key] < field.min || values[field.key] > field.max) {
      return t`${field.label} must be a whole number between ${field.min} and ${field.max}.`;
    }
  }
  if (values.second_reminder_days <= values.first_reminder_days) return t`The second reminder comes after the first.`;
  if (values.policy_text.length > 2000 || values.pickup_note.length > 300) return t`Shorten the policy or pickup note.`;
  return "";
}

/** Send only changes the current per-key policy permits; the backend rechecks atomically. */
export function shopSettingsPatch(values: ShopSettingValues, saved: ShopSettings, editable: ReadonlySet<string>) {
  return Object.fromEntries(Object.entries(values).filter(([key, value]) =>
    editable.has(`shop_${key}`) && value !== saved[key as keyof ShopSettingValues])) as Partial<ShopSettingValues>;
}
