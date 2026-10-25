import { useState } from "react";

import { useContactRequest } from "./useContactRequest";
import { useRequestDraft } from "./useRequestDraft";

/**
 * Account-less self-checkout for a makerspace without member accounts (owner decision #91).
 *
 * Everyone there names themselves with name, phone and an email confirmed by a one-time
 * code, exactly like a borrow request. Each photo upload returns a grant bound to that
 * email, which the checkout or return must send back; a code is single-use, so it is
 * cleared after every handover while the typed details stay.
 */
export function useToolContact(makerspaceSlug: string, enabled: boolean) {
  const draft = useRequestDraft();
  const contact = useContactRequest(makerspaceSlug, draft, enabled);
  const [grants, setGrants] = useState<Record<number, string>>({});
  const email = draft.contactEmail.trim();
  return {
    enabled,
    details: contact.details,
    ready: contact.ready,
    /** `undefined` off the contact path; "" means "type your email before the photo". */
    uploadEmail: enabled ? email : undefined,
    remember: (evidenceId: number | null, grant?: string) => {
      if (evidenceId !== null && grant) setGrants((current) => ({ ...current, [evidenceId]: grant }));
    },
    body: (evidenceId: number | null) =>
      enabled ? { ...contact.payload, evidence_grant: evidenceId !== null ? grants[evidenceId] ?? "" : "" } : {},
    afterHandover: () => draft.setEmailCode(""),
  };
}

export type ToolContact = ReturnType<typeof useToolContact>;
