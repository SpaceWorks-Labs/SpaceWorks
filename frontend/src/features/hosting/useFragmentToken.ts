import { useCallback, useEffect, useRef, useState } from "react";

/** Read the bearer token from `#token=…` once, then clear it from the address bar and history. */
export function useFragmentToken() {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "");
  useEffect(() => {
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
  }, []);
  return token;
}

type TokenCall<T> = { data?: T; error?: unknown; pending: boolean };

/**
 * Run a token call exactly once on mount. StrictMode mounts twice, and a mutation observer that is
 * unsubscribed in between never hears the result, so the outcome is kept in local state instead.
 * `call` must be stable (a mutation's `mutateAsync` is).
 */
export function useTokenCall<T>(token: string, call: (token: string) => Promise<T>) {
  const [state, setState] = useState<TokenCall<T>>({ pending: Boolean(token) });
  const started = useRef(false);
  const settle = useCallback((promise: Promise<T>) => promise.then(
    (data) => setState({ data, pending: false }),
    (error: unknown) => setState({ error, pending: false }),
  ), []);
  useEffect(() => {
    if (started.current || !token) return;
    started.current = true;
    void settle(call(token));
  }, [call, settle, token]);
  const retry = () => {
    setState({ pending: true });
    void settle(call(token));
  };
  return { ...state, retry };
}
