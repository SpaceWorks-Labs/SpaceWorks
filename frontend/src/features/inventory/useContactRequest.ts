import { useMutation } from "@tanstack/react-query";

import { requestContactCode } from "./api";
import type { ContactDetails } from "./ContactFields";
import type { RequestDraft } from "./useRequestDraft";

/**
 * Account-less borrowing for a makerspace without member accounts (owner decision #80).
 *
 * Server state is just the code-send mutation; the typed details live in the page-owned draft
 * so they survive the phone sheet closing. `ready` gates the submit button: all three fields
 * and a 6-digit code are required by the backend, which consumes the code with the request.
 */
export function useContactRequest(makerspaceSlug: string, draft: RequestDraft, enabled: boolean) {
  const sendCode = useMutation({
    mutationFn: () => requestContactCode(makerspaceSlug, draft.contactEmail.trim()),
  });
  const details: ContactDetails = {
    name: draft.contactName,
    email: draft.contactEmail,
    phone: draft.contactPhone,
    code: draft.emailCode,
    onNameChange: draft.setContactName,
    onEmailChange: (value) => { draft.setContactEmail(value); sendCode.reset(); },
    onPhoneChange: draft.setContactPhone,
    onCodeChange: (value) => draft.setEmailCode(value.replace(/\D/g, "").slice(0, 6)),
    onSendCode: () => sendCode.mutate(),
    codePending: sendCode.isPending,
    codeSent: sendCode.isSuccess,
    codeError: sendCode.error?.message,
  };
  const ready = !enabled || (
    draft.contactName.trim().length > 0 && draft.contactPhone.trim().length > 0
    && draft.contactEmail.trim().length > 0 && /^\d{6}$/.test(draft.emailCode)
  );
  const payload = enabled ? {
    contact_name: draft.contactName.trim(),
    contact_phone: draft.contactPhone.trim(),
    contact_email: draft.contactEmail.trim(),
    email_code: draft.emailCode,
  } : {};
  const clear = () => {
    draft.setContactName(""); draft.setContactEmail(""); draft.setContactPhone(""); draft.setEmailCode("");
    sendCode.reset();
  };
  return { details: enabled ? details : undefined, ready, payload, clear };
}
