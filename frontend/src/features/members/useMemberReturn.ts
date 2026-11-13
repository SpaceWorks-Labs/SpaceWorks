import { useEffect } from "react";

import { takeSocialReturnPath } from "../auth/socialSdk";
import { safeReturnPath } from "../inventory/publicInventory/cartHandoff";

/**
 * 0.12.0 row 29: `member?next=<path>` (for example "Sign in to borrow") opens sign-in at once and,
 * after any sign-in (password, passkey, Google/Apple popup or an identity-provider redirect), goes
 * back to `next`. A visitor who is already signed in goes straight there. `next` is only ever a
 * same-origin relative path (`safeReturnPath`), so this can never become an open redirect.
 */
export function useMemberReturn(search: URLSearchParams, { unauthenticated, signedIn, openSignIn }: {
  unauthenticated: boolean; signedIn: boolean; openSignIn: () => void;
}) {
  const returnTo = safeReturnPath(search.get("next"));
  useEffect(() => { if (returnTo && unauthenticated) openSignIn(); }, [returnTo, unauthenticated, openSignIn]);
  useEffect(() => {
    const here = window.location.pathname + window.location.search + window.location.hash;
    if (returnTo && signedIn && returnTo !== here) window.location.replace(returnTo);
  }, [returnTo, signedIn]);
  /** Where to go once sign-in succeeds: this page's `next`, else one carried across a provider redirect. */
  return { returnTo, afterSignIn: () => returnTo ?? takeSocialReturnPath() };
}
