// Hand-written types for the member ID card surface. The generated client
// (src/generated/api.ts) is regenerated from the OpenAPI snapshot in a separate
// commit; these mirror the documented shapes until that lands.

export type MemberCard = {
  id: number;
  // A per-makerspace PositiveIntegerField on the backend, not a formatted string.
  card_number: number;
  /** The printed number in the space's pattern (L4), e.g. "TNK-2026-0042". */
  number_display: string;
  printed_name: string;
  membership_id: number | null;
  is_active: boolean;
  photo_set: boolean;
  photo_consent_at: string | null;
  qr_active: boolean;
  print_count: number;
  last_printed_at: string | null;
  issued_at: string;
  /** Already formatted: a date, "No end date", "Expired", or empty for a revoked card. */
  valid_until: string;
  photo_request_open: boolean;
  last_emailed_at: string | null;
  revoked_at: string | null;
  revoked_reason: string;
  created_at: string;
  updated_at: string;
};

export type MemberCardPage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: MemberCard[];
};

export type CardStatus = "active" | "revoked";

export const REISSUE_REASONS = ["lost", "stolen", "damaged", "renewed"] as const;
export type ReissueReason = (typeof REISSUE_REASONS)[number];

/** A scan lookup. Anything but `ok` carries no card detail worth rendering: a
 *  revoked or inactive card must read as refused, not as a member's identity. */
export type CardResolveResult = {
  outcome: "ok" | "revoked" | "inactive";
  card_id?: number;
  card_number?: number;
  printed_name?: string;
  membership_id?: number;
  membership_status?: string;
  photo_url?: string;
};

export type MemberCardSettings = {
  auto_issue: boolean; email_on_issue: boolean; public_verify: boolean; verify_show_plan: boolean;
  design_approval_required: boolean; email_available: boolean; photo_cleanup_available: boolean;
  wallet_platforms: string[];
};

/** Only the fields the issue roster reads. The membership list is shared with the
 *  Users panel, which types more of it; `status` is optional so a backend that omits
 *  it renders a row rather than crashing the roster. */
export type CardMembershipRow = {
  id: number;
  user: { username: string; display_name?: string };
  status?: string;
};
