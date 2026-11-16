// Shapes of the staff ID card routes (apps/card_designs/serializers_staff_cards.py).

export type StaffCardSummary = {
  id: number; number: string; status: "valid" | "revoked"; issued_at: string; revoked_at: string | null;
  revoked_reason: string; print_count: number; check_url: string; roles_changed_since_issue: boolean;
};

export type StaffCardHolder = {
  membership_id: number; name: string; roles: { slug: string; name: string }[]; roles_text: string;
  machine_scope: string; eligible: boolean; card: StaffCardSummary | null;
};

export type StaffCardPage = { count: number; next: string | null; previous: string | null; results: StaffCardHolder[] };

export type StaffCardFilter = "all" | "none" | "live";

export type SkipReason = "not_found" | "quota" | "already_issued" | "not_eligible";
export type BulkIssueResult = { issued: StaffCardSummary[]; skipped: { membership_id: number; reason: SkipReason }[] };

export type StaffCardSettings = { prefix: string; pattern: string; preview: string[]; auto_issue: boolean; desk_print: boolean };
