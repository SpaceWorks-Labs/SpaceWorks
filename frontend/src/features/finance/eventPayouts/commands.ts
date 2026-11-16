/** Request spellings match the closed core DRF command serializers. */
type Version = { expected_version: number };
type Reason = { reason_code: string };
type PayeeReview = Version & { payee_revision_id: string; expected_payee_version: number };
type Recording = Version & { amount_minor: number; currency: string; method: string; reference: string;
  paid_at: string; payee_revision: string | null; expected_payee_version: number; eligibility_revision: number; reason_code?: string };
type Hold = Version & Reason & { eligibility_revision: number; kind: "eligibility" | "retention";
  note: string; evidence_refs: number[]; hold_until: string | null };
type Commands = {
  record: Recording;
  cancel: Version & Reason & { expected_revision_sequence: number; expected_pool_version: number | null; note: string };
  hold: Hold;
  "release-hold": Hold & { hold_id: string };
  "acknowledge-eligibility": Version & Reason & { eligibility_revision: number };
  "payee/verify": PayeeReview & { reason_code?: string };
  "payee/request-correction": PayeeReview & Reason & { note: string };
};
export type PayoutCommand = keyof Commands | `entries/${string}/amend`;
export type CommandData<Action extends PayoutCommand> = Action extends `entries/${string}/amend`
  ? Recording & Reason & { is_void: boolean } : Action extends keyof Commands ? Commands[Action] : never;
