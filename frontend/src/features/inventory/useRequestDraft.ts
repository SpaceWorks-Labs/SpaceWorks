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
  return {
    requestedFor, setRequestedFor,
    submitted, setSubmitted,
    website, setWebsite,
  };
}

export type RequestDraft = ReturnType<typeof useRequestDraft>;
