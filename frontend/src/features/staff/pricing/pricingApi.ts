import { t } from "@lingui/core/macro";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import type {
  PriceDiscount, PricingCurrency, PricingDefault, PricingDefaultWrite, PricingDomainEnum, PricingImpact, RentalTiming,
} from "../../../generated/api";

export type { PriceDiscount, PricingDefault, PricingDefaultWrite, PricingImpact, RentalTiming };
export type PricingDomain = PricingDomainEnum;

/** One tab per area; `module` is what must be installed (lending is core, so always shown). */
export const PRICING_DOMAINS: { domain: PricingDomain; label: string; module: string | null }[] = [
  { domain: "loans", label: t`Inventory`, module: null },
  { domain: "machines", label: t`Machines`, module: "machines" },
  { domain: "bookings", label: t`Bookings`, module: "bookings" },
  { domain: "events", label: t`Events`, module: "events" },
  { domain: "membership", label: t`Membership`, module: "membership" },
];

export function installedDomains(enabledModules: readonly string[]) {
  return PRICING_DOMAINS.filter(entry => entry.module === null || enabledModules.includes(entry.module));
}

// The shop prices each product itself, so it has no tab above, but a discount can still name it.
const EXTRA_LABELS: Record<string, string> = { shop: t`Shop` };
export const domainLabel = (domain: string) => PRICING_DOMAINS.find(entry => entry.domain === domain)?.label ?? EXTRA_LABELS[domain] ?? domain;

/** Mirrors `apps/payments/pricing/components.py` (labels for discount scoping and the impact list). */
export const COMPONENT_LABELS: Record<PricingDomain, [string, string][]> = {
  loans: [["rental_per_loan", t`Rental per loan`], ["rental_per_day", t`Rental per day`], ["deposit", t`Refundable deposit`],
    ["late_per_day", t`Late fee per day`], ["damage", t`Damage`], ["lost", t`Lost item`]],
  machines: [["time", t`Machine time per hour`], ["material", t`Material per unit`], ["per_job", t`Per job`]],
  bookings: [["per_booking", t`Per booking`], ["per_hour", t`Per hour`]],
  events: [["per_registration", t`Per registration`]],
  membership: [["dues", t`Membership dues`], ["joining_fee", t`Joining fee`]],
  // L22: a shop item is priced on its own variant; only member discounts scope to it.
  shop: [["item", t`Item price`]],
};

export function componentLabel(key: string) {
  for (const rows of Object.values(COMPONENT_LABELS)) {
    const found = rows.find(([component]) => component === key);
    if (found) return found[1];
  }
  return key.replace(/_/g, " ");
}

export const UNIT_WORDING: Record<string, string> = {
  item: t`per item`, item_day: t`per item per day`, hour: t`per hour`, material_unit: t`per unit of material`,
  job: t`per job`, booking: t`per booking`, registration: t`per registration`, day: t`per day`, loan: t`per loan`,
  term: t`per membership term`, once: t`once, when joining`,
};

const space = (id: number) => `/admin/makerspace/${id}/pricing`;
const json = (method: string, body?: unknown): RequestInit =>
  ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const pricingKeys = {
  card: (id: number, domain: string) => ["pricing", id, domain] as const,
  timing: (id: number) => ["pricing-timing", id] as const,
  currency: (id: number) => ["pricing-currency", id] as const,
  discounts: (id: number, archived: boolean) => ["pricing-discounts", id, archived] as const,
};

export const pricingApi = {
  card: (id: number, domain: string) => staffRequest<PricingDefault>(`${space(id)}/${domain}`),
  impact: (id: number, domain: string, body: PricingDefaultWrite) =>
    staffRequest<PricingImpact>(`${space(id)}/${domain}/impact`, json("POST", body)),
  save: (id: number, domain: string, body: PricingDefaultWrite) =>
    staffRequest<PricingDefault>(`${space(id)}/${domain}`, json("PUT", body)),
  timing: (id: number) => staffRequest<RentalTiming>(`${space(id)}/loans/rental-timing`),
  setTiming: (id: number, rental_timing: RentalTiming["rental_timing"]) =>
    staffRequest<RentalTiming>(`${space(id)}/loans/rental-timing`, json("PUT", { rental_timing })),
  currency: (id: number) => staffRequest<PricingCurrency>(`${space(id)}/currency`),
  setCurrency: (id: number, default_currency: string) =>
    staffRequest<PricingCurrency>(`${space(id)}/currency`, json("PUT", { default_currency })),
  discounts: (id: number, archived: boolean) =>
    staffRequest<PriceDiscount[]>(`${space(id)}/discounts${archived ? "?archived=1" : ""}`),
  createDiscount: (id: number, body: Partial<PriceDiscount>) =>
    staffRequest<PriceDiscount>(`${space(id)}/discounts`, json("POST", body)),
  updateDiscount: (id: number, discount: number, body: Partial<PriceDiscount>) =>
    staffRequest<PriceDiscount>(`${space(id)}/discounts/${discount}`, json("PATCH", body)),
  archiveDiscount: (id: number, discount: number) =>
    staffRequest<PriceDiscount>(`${space(id)}/discounts/${discount}/archive`, json("POST")),
};

export const REFUSALS: Record<string, string> = {
  setting_not_delegated: t`Only the Space Manager, or a manager they have handed these settings to, can change them.`,
  setting_locked: t`The Space Manager has locked these prices, so only they can change them.`,
  component_not_allowed: t`One of these prices does not apply to this area.`,
  discount_invalid: t`The discount is not valid.`,
};

export const isNotFound = (error: unknown) => error instanceof StructuredApiError && error.status === 404;

const GENERIC_DETAILS = new Set(["That price component does not apply here.", "The discount is not valid."]);

/** `{detail, code}` bodies: known codes get plain wording, plus the server's detail when it says more. */
export function pricingError(error: unknown) {
  if (error instanceof StructuredApiError) {
    const known = error.code ? REFUSALS[error.code] : undefined;
    const extra = error.detail && !GENERIC_DETAILS.has(error.detail) ? error.detail : "";
    if (known && (error.code === "component_not_allowed" || error.code === "discount_invalid")) {
      return extra ? `${known} ${extra}` : known;
    }
    if (known) return known;
    if (error.status === 403) return t`You don't have permission to change this.`;
    return error.message;
  }
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}
