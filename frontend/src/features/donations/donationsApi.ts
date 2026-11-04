import { API_V1_URL, StructuredApiError, getAccessToken, memberRequest, tenantPublicRequest } from "../../lib/api";

// Hand-written mirrors of `apps/payments/donations/serializers_public.py` (lane L18). Swap for the
// generated client once the OpenAPI snapshot is refreshed.
export type Campaign = {
  id: number; kind: "campaign" | "fund"; name: string; slug: string; description: string;
  goal_amount: string | null; raised_amount: string; currency: string; starts_at: string | null; ends_at: string | null;
};
export type DonationPage = {
  makerspace: string; intro: string; currency: string; minimum_amount: string; suggested_amounts: string[];
  campaigns: Campaign[]; online_available: boolean; recurring_available: boolean; tax_receipts_available: boolean;
  tax_registration_number: string; guest_allowed: boolean;
};
export type Offline = { instructions: string; upi: { vpa?: string; payee_name?: string; uri?: string } | null; claimable: boolean };
export type GiftStatus = {
  id: number; makerspace: string; campaign: string; amount: string; currency: string;
  status: "pending" | "paid" | "cancelled"; payment_status: string; created_at: string; paid_at: string | null;
  receipt_number: string; tax_receipt_number: string; donor_pan_masked: string; online_available: boolean;
  checkout_url: string; status_token: string; offline: Offline | null;
};
export type Interval = "monthly" | "quarterly" | "yearly";
export type PledgeStatus = {
  id: number; makerspace: string; campaign: string; amount: string; currency: string; interval: Interval;
  status: "active" | "paused" | "cancelled"; starts_on: string; next_due_on: string; donor_pan_masked: string;
  manage_token: string;
};
export type PledgeAction = { action: "pause" | "resume" | "cancel" | "update"; amount?: string | null; interval?: Interval | null };
export type GiverFields = {
  donor_name?: string; donor_email?: string; email_code?: string;
  wants_tax_receipt?: boolean; donor_pan?: string; donor_address?: string;
};
export type GiftInput = GiverFields & { amount: string; campaign?: number | null; note?: string };
export type PledgeInput = GiverFields & { amount: string; interval: Interval; campaign?: number | null };

export const INTERVAL_LABELS: Record<Interval, string> = { monthly: "Every month", quarterly: "Every quarter", yearly: "Every year" };

export const donationKeys = {
  page: (slug: string) => ["donation-page", slug] as const,
  gift: (token: string) => ["donation-link", token] as const,
  pledge: (token: string) => ["pledge-link", token] as const,
  memberGifts: (id: number) => ["member-donations", id] as const,
  memberPledges: (id: number) => ["member-pledges", id] as const,
};

export const signedIn = () => Boolean(getAccessToken("member"));

/**
 * Giving and a guest's own signed links are browser flows no API-client scope reaches, so they go
 * without the publishable key (like pay links). A signed-in giver sends their own session.
 */
export async function giverRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (signedIn() && init.method && init.method !== "GET") return memberRequest<T>(path, init);
  const response = await fetch(`${API_V1_URL}${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  if (response.status === 202 || response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new StructuredApiError(response.status, body);
  return body as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const slugPath = (slug: string) => `/public/${encodeURIComponent(slug)}`;
const token = (value: string) => encodeURIComponent(value);

export const donationsApi = {
  page: (slug: string) => tenantPublicRequest<DonationPage>(slug, `${slugPath(slug)}/donations`),
  sendCode: (slug: string, email: string) => giverRequest<void>(`${slugPath(slug)}/donations/email-code`,
    { method: "POST", body: JSON.stringify({ donor_email: email }) }),
  give: (slug: string, body: GiftInput) => giverRequest<GiftStatus>(`${slugPath(slug)}/donations/give`, post(body)),
  pledge: (slug: string, body: PledgeInput) => giverRequest<PledgeStatus>(`${slugPath(slug)}/donations/pledges`, post(body)),
  gift: (value: string) => giverRequest<GiftStatus>(`/public/donation-links/${token(value)}`),
  checkout: (value: string) => giverRequest<GiftStatus>(`/public/donation-links/${token(value)}/checkout`,
    { method: "POST" }),
  claim: (value: string, body: { reference: string; paid_on: string }) =>
    giverRequest<{ id: number; status: string }>(`/public/donation-links/${token(value)}/claim`, post(body)),
  taxReceiptUrl: (value: string) => `${API_V1_URL}/public/donation-links/${token(value)}/tax-receipt.pdf`,
  guestPledge: (value: string) => giverRequest<PledgeStatus>(`/public/pledge-links/${token(value)}`),
  changeGuestPledge: (value: string, body: PledgeAction) =>
    giverRequest<PledgeStatus>(`/public/pledge-links/${token(value)}`, { method: "POST", body: JSON.stringify(body) }),
  memberGifts: (id: number) => memberRequest<GiftStatus[]>(`/member/makerspaces/${id}/donations`),
  memberPledges: (id: number) => memberRequest<PledgeStatus[]>(`/member/makerspaces/${id}/pledges`),
  changeMemberPledge: (id: number, pledge: number, body: PledgeAction) =>
    memberRequest<PledgeStatus>(`/member/makerspaces/${id}/pledges/${pledge}`, post(body)),
  memberReceiptPath: (id: number, gift: number) => `/member/makerspaces/${id}/donations/${gift}/tax-receipt.pdf`,
};

/** Plain-language errors for the giving forms; field errors join into one line. */
export function giveError(error: unknown) {
  if (!(error instanceof StructuredApiError)) return error instanceof Error ? error.message : "Something went wrong. Try again.";
  const messages: Record<string, string> = {
    donor_identity_required: "Sign in, or give your name, email and the code we emailed you.",
    amount_below_minimum: "That amount is below the smallest gift here.",
    campaign_closed: "That campaign isn't taking gifts right now.",
    tax_receipts_unavailable: "This space doesn't issue tax-exempt receipts right now.",
    pan_invalid: "Enter a valid 10-character PAN, like ABCDE1234F.",
    feature_disabled: "Giving is turned off here.",
  };
  if (error.status === 429) return "Too many tries. Wait a minute and try again.";
  const code = errorCode(error);
  return (code && messages[code]) || error.message;
}

/** DRF wraps a field-error dict's `code` in a list; a plain APIException carries it as a string. */
export function errorCode(error: unknown) {
  if (!(error instanceof StructuredApiError)) return undefined;
  const raw = error.body.code;
  return error.code ?? (Array.isArray(raw) && typeof raw[0] === "string" ? raw[0] : undefined);
}

export function money(currency: string, amount: string) {
  return `${currency.toUpperCase()} ${amount}`;
}
