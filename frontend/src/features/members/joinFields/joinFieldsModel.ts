import { t } from "@lingui/core/macro";

import { formatLocale } from "../../../lib/format";
import type { JoinFieldModes } from "../membershipAdmissionApi";

// Parity O-B2: the join form's extras besides its questions -- a card photo, a phone number and a
// state. Each is off/hidden, optional or required per plan; the server re-checks every rule.

/** GSTN state and union-territory codes (place of supply), as `payments/tax/gstin.py` lists them. */
export const GST_STATES: [string, string][] = [
  ["01", "Jammu and Kashmir"], ["02", "Himachal Pradesh"], ["03", "Punjab"], ["04", "Chandigarh"], ["05", "Uttarakhand"],
  ["06", "Haryana"], ["07", "Delhi"], ["08", "Rajasthan"], ["09", "Uttar Pradesh"], ["10", "Bihar"], ["11", "Sikkim"],
  ["12", "Arunachal Pradesh"], ["13", "Nagaland"], ["14", "Manipur"], ["15", "Mizoram"], ["16", "Tripura"],
  ["17", "Meghalaya"], ["18", "Assam"], ["19", "West Bengal"], ["20", "Jharkhand"], ["21", "Odisha"],
  ["22", "Chhattisgarh"], ["23", "Madhya Pradesh"], ["24", "Gujarat"], ["26", "Dadra and Nagar Haveli and Daman and Diu"],
  ["27", "Maharashtra"], ["29", "Karnataka"], ["30", "Goa"], ["31", "Lakshadweep"], ["32", "Kerala"], ["33", "Tamil Nadu"],
  ["34", "Puducherry"], ["35", "Andaman and Nicobar Islands"], ["36", "Telangana"], ["37", "Andhra Pradesh"],
  ["38", "Ladakh"], ["97", "Other Territory"],
];

/** Calling codes offered beside the phone number; the country names come from the browser, translated. */
const CALLING_CODES: [string, string][] = [
  ["IN", "91"], ["AE", "971"], ["AU", "61"], ["BD", "880"], ["CA", "1"], ["DE", "49"], ["FR", "33"], ["GB", "44"],
  ["ID", "62"], ["IE", "353"], ["JP", "81"], ["KE", "254"], ["LK", "94"], ["MY", "60"], ["NG", "234"], ["NP", "977"],
  ["NZ", "64"], ["OM", "968"], ["PH", "63"], ["PK", "92"], ["QA", "974"], ["SA", "966"], ["SG", "65"], ["US", "1"], ["ZA", "27"],
];

export function callingCodeOptions(): { region: string; code: string; label: string }[] {
  let names: Intl.DisplayNames | null = null;
  try { names = new Intl.DisplayNames([formatLocale()], { type: "region" }); } catch { names = null; }
  return CALLING_CODES.map(([region, code]) => ({ region, code, label: `${names?.of(region) ?? region} (+${code})` }))
    .sort((left, right) => (left.region === "IN" ? -1 : right.region === "IN" ? 1 : left.label.localeCompare(right.label)));
}

export const NO_EXTRAS: JoinFieldModes = { photo: "off", phone: "hidden", state: "hidden" };

export type JoinExtrasDraft = { region: string; national: string; state_code: string; photo: File | null; consent: boolean };
export const EMPTY_EXTRAS: JoinExtrasDraft = { region: "IN", national: "", state_code: "", photo: null, consent: false };
export type JoinExtrasErrors = Partial<Record<"phone" | "state_code" | "photo", string>>;

export const asksForAnything = (modes: JoinFieldModes) => modes.photo !== "off" || modes.phone !== "hidden" || modes.state !== "hidden";

/** The full number the server stores, `+<code><digits>`; empty when nothing was typed. */
export function e164(draft: JoinExtrasDraft): string {
  const digits = draft.national.replace(/[\s().-]/g, "").replace(/^0+/, "");
  if (!digits) return "";
  const code = CALLING_CODES.find(([region]) => region === draft.region)?.[1] ?? "91";
  return `+${code}${digits}`;
}

/**
 * Browser-side checks, so the common slips are caught before anything uploads. `onFile` lists what is
 * already on file for a resubmission: a required field already given may be left blank.
 */
export function validateExtras(modes: JoinFieldModes, draft: JoinExtrasDraft, onFile: { phone?: boolean; state?: boolean; photo?: boolean } = {}): JoinExtrasErrors {
  const errors: JoinExtrasErrors = {};
  const phone = e164(draft);
  if (modes.phone !== "hidden") {
    if (phone && !/^\+[1-9][0-9]{6,14}$/.test(phone)) errors.phone = t`Enter the number without the country code, digits only.`;
    else if (!phone && modes.phone === "required" && !onFile.phone) errors.phone = t`Enter your phone number.`;
  }
  if (modes.state === "required" && !draft.state_code && !onFile.state) errors.state_code = t`Choose your state.`;
  if (modes.photo !== "off") {
    if (draft.photo && !draft.consent) errors.photo = t`Tick the consent box to send your photo.`;
    else if (!draft.photo && modes.photo === "required" && !onFile.photo) errors.photo = t`Add a photo of yourself.`;
  }
  return errors;
}

/** Server field errors (`join_fields: {phone: [...], ...}`) as one message per field. */
export function serverExtrasErrors(body: unknown): JoinExtrasErrors {
  const raw = body && typeof body === "object" ? (body as Record<string, unknown>).join_fields : null;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const text = (value: unknown) => (Array.isArray(value) ? value.join(" ") : typeof value === "string" ? value : "");
  return Object.fromEntries(Object.entries(raw as Record<string, unknown>)
    .filter(([key]) => ["phone", "state_code", "photo"].includes(key)).map(([key, value]) => [key, text(value)]));
}
