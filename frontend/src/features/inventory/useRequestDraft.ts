import { useRef, useState } from "react";

// The header is required for account-less submissions, and it is what makes a retry
// idempotent: the same key with the same payload returns the original request. Held for
// the lifetime of one composed request and rotated only after a successful submit, so a
// network retry of the SAME attempt cannot create a second request.
export function newIdempotencyKey() {
  const cryptoRef = globalThis.crypto;
  if (cryptoRef && typeof cryptoRef.randomUUID === "function") {
    return cryptoRef.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

/**
 * Everything a requester types or receives while composing a borrow request.
 *
 * Owned by the page, not the panel: on phones the panel lives in a sheet whose content is unmounted
 * when it closes, so state kept inside the panel (the draft, the contact fields, the account-less
 * reference token -- their only route back to the request) would vanish on every close.
 */
export function useRequestDraft() {
  const [requestedFor, setRequestedFor] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [publicToken, setPublicToken] = useState("");
  const idempotencyKey = useRef(newIdempotencyKey());
  return {
    requestedFor, setRequestedFor,
    submitted, setSubmitted,
    contactName, setContactName,
    contactEmail, setContactEmail,
    contactPhone, setContactPhone,
    website, setWebsite,
    publicToken, setPublicToken,
    idempotencyKey,
  };
}

export type RequestDraft = ReturnType<typeof useRequestDraft>;
