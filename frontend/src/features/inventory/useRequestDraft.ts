import { useState } from "react";

/**
 * Everything a requester types or receives while composing a borrow request.
 *
 * Owned by the page, not the panel: on phones the panel lives in a sheet whose content is unmounted
 * when it closes, so state kept inside the panel (the draft and the submitted banner) would vanish
 * on every close.
 */
export function useRequestDraft() {
  const [requestedFor, setRequestedFor] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [website, setWebsite] = useState("");
  // Account-less contact details (#80), used only where the space has no member accounts.
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [emailCode, setEmailCode] = useState("");
  return {
    requestedFor, setRequestedFor,
    submitted, setSubmitted,
    website, setWebsite,
    contactName, setContactName,
    contactEmail, setContactEmail,
    contactPhone, setContactPhone,
    emailCode, setEmailCode,
  };
}

export type RequestDraft = ReturnType<typeof useRequestDraft>;
