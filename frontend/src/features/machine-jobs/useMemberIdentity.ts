import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getAccessToken, memberRequest, refreshAccessToken, StructuredApiError } from "../../lib/api";

/** Restore the member session once, then read who is signed in. `signedOut` is a definite 401. */
export function useMemberIdentity() {
  const [restoring, setRestoring] = useState(() => !getAccessToken("person"));
  useEffect(() => {
    if (restoring) void refreshAccessToken("person").finally(() => setRestoring(false));
  }, []); // one restore per mount
  const identity = useQuery({ queryKey: ["member", "profile"], queryFn: () => memberRequest<{ username?: string; email_verified?: boolean }>("/auth/me"),
    enabled: !restoring, retry: false });
  const signedOut = identity.error instanceof StructuredApiError && identity.error.status === 401;
  return { restoring, identity, signedOut, loading: restoring || identity.isPending };
}
