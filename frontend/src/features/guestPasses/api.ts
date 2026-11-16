// Decision 223 (L1a/L1b/L4): guest passes, day passes and the guest policy. Hand-typed like the
// neighbouring feature api modules, so a regenerated client cannot shift these shapes under us.
import { t } from "@lingui/core/macro";
import { memberRequest, staffRequest, StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { eligibilityMessage } from "../../lib/eligibilityCopy";

export type PassKind = "event" | "sponsored" | "day";
export type PassStatus = "issued" | "active" | "expired" | "revoked" | "converted";
export type BorrowMode = "none" | "on_site" | "full_with_deposit";
export type MachineMode = "none" | "supervised" | "after_induction_cert";
export type Entitlements = { borrow?: BorrowMode; machines?: MachineMode };
export type Paged<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type StaffPass = {
  id: number; kind: PassKind; status: PassStatus; valid_from: string; valid_until: string;
  holder_id: number; holder_name: string; holder_email: string; sponsor_id: number | null; sponsor_name: string;
  product_id: number | null; entitlements: Entitlements; waiver_version: string | null; waiver_accepted_at: string | null;
  payment_status: string | null; revoked_at: string | null; revoked_reason: string; converted_membership_id: number | null;
  created_at: string;
};
export type HolderPass = {
  id: number; kind: PassKind; status: PassStatus; valid_from: string; valid_until: string; entitlements: Entitlements;
  sponsor_name: string; waiver_accepted: boolean; waiver_required: boolean; payment_status: string | null;
  wallet_platforms?: string[];
};
export type HolderPasses = { passes: HolderPass[]; visits_30d: number; join_threshold: number; should_prompt_join: boolean };
export type SponsoredGuest = { id: number; guest_name: string; pass_date: string; status: PassStatus; items_outstanding: boolean };
export type DayPassOffer = { id: number; name: string; amount: string; currency: string };
export type DayPassProduct = DayPassOffer & {
  entitlements: Entitlements; daily_cap: number | null; is_public: boolean; is_active: boolean; archived_at: string | null;
};
export type PurchaseResult = { pass_id: number; status: string; payment_id: number | null; payment_status: string | null; amount: string; currency: string };
export type GuestPassPolicy = {
  guest_borrowing_mode: BorrowMode; guest_machine_mode: MachineMode; sponsored_liability: "guest" | "sponsor";
  walk_in_registration_creates: "guest_pass" | "membership"; waiver_required_on_site: boolean; waiver_gate_without_passes: boolean;
  sponsor_min_tenure_days: number; max_concurrent_guests_per_sponsor: number; sponsor_must_be_present: boolean;
  visits_before_join_prompt: number; hard_visit_cap: number | null; day_pass_daily_cap: number | null;
};
export type ScanResult = {
  valid: boolean; reason: string; pass_id: number | null; holder_name: string; kind: string;
  valid_until: string | null; entitlements: Entitlements;
};
export type PersonRef = { holder_email: string } | { holder_id: number };

const json = (method: string, body?: unknown): RequestInit => ({ method, body: JSON.stringify(body ?? {}) });
const admin = (id: number) => `/admin/makerspaces/${id}`;
const member = (id: number) => `/member/makerspaces/${id}`;

export const guestKeys = {
  all: (id: number) => ["guest-passes", id] as const,
  roster: (id: number, filters: Record<string, string>) => ["guest-passes", id, "roster", filters] as const,
  policy: (id: number) => ["guest-passes", id, "policy"] as const,
  products: (id: number) => ["guest-passes", id, "products"] as const,
  mine: (id: number) => ["member", "guest-passes", id, "mine"] as const,
  sponsored: (id: number) => ["member", "guest-passes", id, "sponsored"] as const,
  offers: (id: number) => ["member", "guest-passes", id, "day-passes"] as const,
  publicOffers: (slug: string) => ["public", slug, "day-passes"] as const,
};

export const guestStaffApi = {
  roster: (id: number, filters: Record<string, string>) =>
    staffRequest<Paged<StaffPass>>(`${admin(id)}/guest-passes?${new URLSearchParams(filters)}`),
  issue: (id: number, input: PersonRef & { sponsor_id?: number; day?: string; operation_id?: string }) =>
    staffRequest<StaffPass>(`${admin(id)}/guest-passes`, json("POST", input)),
  sell: (id: number, input: PersonRef & { product_id: number; day?: string; operation_id?: string }) =>
    staffRequest<PurchaseResult>(`${admin(id)}/guest-passes/sell`, json("POST", input)),
  revoke: (id: number, passId: number, reason: string) =>
    staffRequest<StaffPass>(`${admin(id)}/guest-passes/${passId}/revoke`, json("POST", { reason })),
  stampWaiver: (id: number, passId: number) => staffRequest<StaffPass>(`${admin(id)}/guest-passes/${passId}/waiver`, json("POST")),
  scan: (id: number, token: string) => staffRequest<ScanResult>(`${admin(id)}/guest-passes/scan`, json("POST", { token })),
  policy: (id: number) => staffRequest<GuestPassPolicy>(`${admin(id)}/guest-pass-policy`),
  savePolicy: (id: number, next: Partial<GuestPassPolicy>) =>
    staffRequest<GuestPassPolicy>(`${admin(id)}/guest-pass-policy`, json("PATCH", next)),
  products: (id: number) => staffRequest<DayPassProduct[]>(`${admin(id)}/day-pass-products`),
  createProduct: (id: number, input: Partial<DayPassProduct>) =>
    staffRequest<DayPassProduct>(`${admin(id)}/day-pass-products`, json("POST", input)),
  updateProduct: (id: number, productId: number, input: Partial<DayPassProduct>) =>
    staffRequest<DayPassProduct>(`${admin(id)}/day-pass-products/${productId}`, json("PATCH", input)),
  archiveProduct: (id: number, productId: number) =>
    staffRequest<DayPassProduct>(`${admin(id)}/day-pass-products/${productId}/archive`, json("POST")),
};

export const guestMemberApi = {
  mine: (id: number) => memberRequest<HolderPasses>(`${member(id)}/guest-passes`),
  acceptWaiver: (id: number, passId: number) =>
    memberRequest<HolderPass>(`${member(id)}/guest-passes/${passId}/accept-waiver`, json("POST", { accepted: true })),
  wallet: (id: number, passId: number, platform: string) =>
    memberRequest<{ platform: string; url: string; expires_in: number | null }>(`${member(id)}/guest-passes/${passId}/wallet/${platform}`, json("POST")),
  sponsored: (id: number) => memberRequest<SponsoredGuest[]>(`${member(id)}/guest-passes/sponsored`),
  sponsor: (id: number, email: string, operationId: string) =>
    memberRequest<{ detail: string }>(`${member(id)}/guest-passes/sponsored`, json("POST", { email, operation_id: operationId })),
  revokeSponsored: (id: number, passId: number, reason: string) =>
    memberRequest<SponsoredGuest>(`${member(id)}/guest-passes/sponsored/${passId}/revoke`, json("POST", { reason })),
  offers: (id: number) => memberRequest<DayPassOffer[]>(`${member(id)}/day-passes`),
  purchase: (id: number, productId: number, input: { day?: string; operation_id: string }) =>
    memberRequest<PurchaseResult>(`${member(id)}/day-passes/${productId}/purchase`, json("POST", input)),
};

export const publicDayPasses = (slug: string) => tenantPublicRequest<DayPassOffer[]>(slug, `/public/${slug}/day-passes`);

/** A fresh idempotency key, so a double-click or a retry never issues or sells twice. */
export const operationId = () => (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`);

/** Plain-language copy for a refusal, falling back to the server's own sentence. */
export function guestErrorText(error: unknown, fallback = t`Something went wrong. Try again.`): string {
  const known = eligibilityMessage(error);
  if (known) return known;
  if (error instanceof StructuredApiError) return error.detail ?? error.message;
  return error instanceof Error ? error.message : fallback;
}

/** `holder_email` for something that looks like an address, else `holder_id` for a number. */
export function personRef(value: string): PersonRef | null {
  const text = value.trim();
  if (/^\d+$/.test(text)) return { holder_id: Number(text) };
  return text.includes("@") ? { holder_email: text } : null;
}
