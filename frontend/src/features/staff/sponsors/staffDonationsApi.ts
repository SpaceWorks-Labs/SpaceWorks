import { t } from "@lingui/core/macro";
import { downloadStaffFile, staffRequest } from "../../../lib/api";

// Hand-written mirrors of `apps/payments/donations/serializers_staff.py` and `serializers_sponsors.py`
// (lane L18). Swap for the generated client once the OpenAPI snapshot is refreshed.
export type StaffDonation = {
  id: number; campaign: number | null; campaign_name: string; pledge: number | null; period_start: string | null;
  donor: number | null; is_guest: boolean; donor_name: string; donor_email: string; donor_note: string; amount: string;
  currency: string; source: "online" | "desk" | "pledge"; status: "pending" | "paid" | "cancelled";
  wants_tax_receipt: boolean; donor_pan_masked: string; donor_address: string; tax_receipt_number: string;
  payment_id: number | null; payment_status: string; created_at: string; paid_at: string | null;
  cancelled_at: string | null; pii_masked?: boolean; recognize_publicly?: boolean;
  open_claim?: { id: number; reference: string; paid_on: string; status: string } | null;
};
export type StaffCampaign = {
  id: number; kind: "campaign" | "fund"; name: string; slug: string; description: string; goal_amount: string | null;
  currency: string; starts_at: string | null; ends_at: string | null; is_active: boolean; is_public: boolean;
  raised_amount?: string;
};
export type CampaignInput = Omit<StaffCampaign, "id" | "currency" | "raised_amount">;
/** Decision 242(m): one tax-exemption registration of the non-profit profile. */
export type TaxExemption = { scheme: string; number: string; valid_from: string; valid_until: string };
export type DonationSettings = {
  page_intro: string; suggested_amounts: string[]; minimum_amount: string; tax_exempt_registration_number: string;
  tax_exempt_valid_from: string | null; tax_exempt_valid_until: string | null; tax_exempt_registrant_pan: string;
  tax_exempt_note: string; updated_at?: string;
  is_nonprofit: boolean; legal_name: string; organization_registration_number: string; tax_exemptions: TaxExemption[];
  signatory_name: string; signatory_title: string; receipt_footer: string;
};
export type StaffDonor = {
  key: string; name: string; email: string; is_guest: boolean; gift_count: number; totals: Record<string, string>;
  last_gift_at: string | null; recurring: boolean; recognize_publicly: boolean; pii_masked?: boolean;
};
export type StaffPledge = {
  id: number; campaign: number | null; campaign_name: string; donor: number | null; donor_name: string;
  donor_email: string; amount: string; currency: string; interval: "monthly" | "quarterly" | "yearly";
  starts_on: string; next_due_on: string; ends_on: string | null; status: "active" | "paused" | "cancelled";
  wants_tax_receipt: boolean; donor_pan_masked: string; created_at: string; cancelled_at: string | null;
};
export type Settlement = { method: string; reference: string; received_at: string };
export type DeskGiftInput = {
  amount: string; donor_name: string; donor_email: string; campaign: number | null; note: string;
  wants_tax_receipt: boolean; donor_pan: string; donor_address: string; settlement: Settlement;
  recognize_publicly?: boolean;
};

export const donationStaffKeys = {
  gifts: (id: number, filters: string) => ["staff-donations", id, filters] as const,
  campaigns: (id: number) => ["staff-donation-campaigns", id] as const,
  settings: (id: number) => ["staff-donation-settings", id] as const,
  pledges: (id: number) => ["staff-donation-pledges", id] as const,
  donors: (id: number) => ["staff-donation-donors", id] as const,
};

const base = (id: number) => `/admin/makerspace/${id}/donations`;
const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const donationStaffApi = {
  gifts: (id: number, filters: string) => staffRequest<StaffDonation[]>(`${base(id)}${filters ? `?${filters}` : ""}`),
  recordDesk: (id: number, body: DeskGiftInput) => staffRequest<StaffDonation>(base(id), json("POST", body)),
  cancel: (id: number, gift: number, reason: string) =>
    staffRequest<StaffDonation>(`${base(id)}/${gift}/cancel`, json("POST", { reason })),
  openReturn: (id: number, gift: number, reason: string) =>
    staffRequest<StaffDonation>(`${base(id)}/${gift}/return`, json("POST", { reason })),
  taxReceipt: (id: number, gift: StaffDonation) =>
    downloadStaffFile(`${base(id)}/${gift.id}/tax-receipt.pdf`, `${gift.tax_receipt_number || `donation-${gift.id}`}.pdf`),
  campaigns: (id: number) => staffRequest<StaffCampaign[]>(`${base(id)}/campaigns`),
  createCampaign: (id: number, body: CampaignInput) => staffRequest<StaffCampaign>(`${base(id)}/campaigns`, json("POST", body)),
  updateCampaign: (id: number, campaign: number, body: Partial<CampaignInput>) =>
    staffRequest<StaffCampaign>(`${base(id)}/campaigns/${campaign}`, json("PATCH", body)),
  settings: (id: number) => staffRequest<DonationSettings>(`${base(id)}/settings`),
  saveSettings: (id: number, body: Partial<DonationSettings>) =>
    staffRequest<DonationSettings>(`${base(id)}/settings`, json("PUT", body)),
  pledges: (id: number) => staffRequest<StaffPledge[]>(`${base(id)}/pledges`),
  changePledge: (id: number, pledge: number, action: "pause" | "resume" | "cancel") =>
    staffRequest<StaffPledge>(`${base(id)}/pledges/${pledge}`, json("POST", { action })),
  // Decision 242(m): the Donations area.
  donors: (id: number) => staffRequest<StaffDonor[]>(`${base(id)}/donors`),
  exportCsv: (id: number, filters: string) =>
    downloadStaffFile(`${base(id)}/export.csv${filters ? `?${filters}` : ""}`, "donations.csv"),
  reissue: (id: number, gift: number) => staffRequest<StaffDonation>(`${base(id)}/${gift}/receipt/reissue`, json("POST")),
  decideClaim: (id: number, gift: number, confirm: boolean, note = "") =>
    staffRequest<unknown>(`${base(id)}/${gift}/claim/${confirm ? "confirm" : "reject"}`, json("POST", { note })),
  markReceived: (id: number, payment: number, settlement: Settlement) =>
    staffRequest<unknown>(`/admin/makerspace/${id}/payments/${payment}/mark-offline`, json("POST", { settlement })),
};

/** `nonprofit.SCHEMES`: the tax-exemption schemes a non-profit profile can list. */
export const TAX_SCHEMES: Record<string, string> = {
  in_80g: t`India: section 80G`, in_12a: t`India: section 12A/12AB registration`, us_501c3: t`United States: 501(c)(3)`,
  uk_charity: t`United Kingdom: registered charity`, ca_charity: t`Canada: registered charity`,
  au_dgr: t`Australia: deductible gift recipient`, other: t`Other tax-exemption registration`,
};

export const GIFT_STATUS: Record<StaffDonation["status"], { label: string; tone: "success" | "warn" | "neutral" }> = {
  paid: { label: t`Received`, tone: "success" }, pending: { label: t`Waiting for payment`, tone: "warn" },
  cancelled: { label: t`Cancelled`, tone: "neutral" },
};
export const SOURCE_LABELS: Record<StaffDonation["source"], string> = {
  online: t`Given online`, desk: t`Recorded by staff`, pledge: t`Pledge period`,
};
