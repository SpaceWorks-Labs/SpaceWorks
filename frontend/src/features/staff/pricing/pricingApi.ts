import { StructuredApiError, staffRequest } from "../../../lib/api";
import type {
  PriceDiscount, PricingCurrency, PricingDefault, PricingDefaultWrite, PricingDomainEnum, PricingImpact, RentalTiming,
} from "../../../generated/api";

export type { PriceDiscount, PricingDefault, PricingDefaultWrite, PricingImpact, RentalTiming };
export type PricingDomain = PricingDomainEnum;

/** One tab per area; `module` is what must be installed (lending is core, so always shown). */
export const PRICING_DOMAINS: { domain: PricingDomain; label: string; module: string | null }[] = [
  { domain: "loans", label: "Lending", module: null },
  { domain: "machines", label: "Machines", module: "machines" },
  { domain: "bookings", label: "Bookings", module: "bookings" },
  { domain: "events", label: "Events", module: "events" },
  { domain: "membership", label: "Membership", module: "membership" },
];

export function installedDomains(enabledModules: readonly string[]) {
  return PRICING_DOMAINS.filter(entry => entry.module === null || enabledModules.includes(entry.module));
}

// The shop prices each product itself, so it has no tab above, but a discount can still name it.
const EXTRA_LABELS: Record<string, string> = { shop: "Shop" };
export const domainLabel = (domain: string) => PRICING_DOMAINS.find(entry => entry.domain === domain)?.label ?? EXTRA_LABELS[domain] ?? domain;

/** Mirrors `apps/payments/pricing/components.py` (labels for discount scoping and the impact list). */
export const COMPONENT_LABELS: Record<PricingDomain, [string, string][]> = {
  loans: [["rental_per_loan", "Rental per loan"], ["rental_per_day", "Rental per day"], ["deposit", "Refundable deposit"],
    ["late_per_day", "Late fee per day"], ["damage", "Damage"], ["lost", "Lost item"]],
  machines: [["time", "Machine time per hour"], ["material", "Material per unit"], ["per_job", "Per job"]],
  bookings: [["per_booking", "Per booking"], ["per_hour", "Per hour"]],
  events: [["per_registration", "Per registration"]],
  membership: [["dues", "Membership dues"], ["joining_fee", "Joining fee"]],
  // L22: a shop item is priced on its own variant; only member discounts scope to it.
  shop: [["item", "Item price"]],
};

export function componentLabel(key: string) {
  for (const rows of Object.values(COMPONENT_LABELS)) {
    const found = rows.find(([component]) => component === key);
    if (found) return found[1];
  }
  return key.replace(/_/g, " ");
}

export const UNIT_WORDING: Record<string, string> = {
  item: "per item", item_day: "per item per day", hour: "per hour", material_unit: "per unit of material",
  job: "per job", booking: "per booking", registration: "per registration", day: "per day", loan: "per loan",
  term: "per membership term", once: "once, when joining",
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
  setting_not_delegated: "Only the Space Manager, or a manager they have handed these settings to, can change them.",
  setting_locked: "The Space Manager has locked these prices, so only they can change them.",
  component_not_allowed: "One of these prices does not apply to this area.",
  discount_invalid: "The discount is not valid.",
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
    if (error.status === 403) return "You don't have permission to change this.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}
