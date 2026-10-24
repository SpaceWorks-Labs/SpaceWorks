import { useCallback, useEffect, useRef, useState } from "react";

/** No query/mutation cache, error payload, URL storage or late response survives dismissal. */
export function usePrivateRequest<T>(identity: string) {
  const controller = useRef<AbortController | null>(null);
  const [result, setResult] = useState<{ identity: string; value: T } | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const clear = useCallback(() => {
    controller.current?.abort(); controller.current = null;
    setResult(null); setPending(false); setFailed(false);
  }, []);
  useEffect(() => {
    const hidden = () => { if (document.visibilityState !== "visible") clear(); };
    window.addEventListener("blur", clear); document.addEventListener("visibilitychange", hidden);
    return () => { clear(); window.removeEventListener("blur", clear); document.removeEventListener("visibilitychange", hidden); };
  }, [identity, clear]);
  const run = async (request: (signal: AbortSignal) => Promise<T>) => {
    clear();
    const active = new AbortController(); controller.current = active;
    setPending(true);
    try {
      const value = await request(active.signal);
      if (!active.signal.aborted && document.visibilityState === "visible") setResult({ identity, value });
    } catch { if (!active.signal.aborted) setFailed(true); }
    finally { if (!active.signal.aborted) setPending(false); }
  };
  return { data: result?.identity === identity ? result.value : null, pending, failed, run, clear };
}
