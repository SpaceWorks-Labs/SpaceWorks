import type { TelemetryAdapter } from "../controller";
import { TELEMETRY_CLIENT } from "../client";

const errorTypes = new Set(["Error", "TypeError", "ReferenceError", "RangeError", "SyntaxError", "URIError", "EvalError"]);
function safePath(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  try { const url = new URL(raw, location.origin); return url.origin === location.origin && /^\/(?:assets|src)\//.test(url.pathname) ? url.pathname : undefined; } catch { return undefined; }
}
function safeNumber(value: number | undefined): number | undefined {
  return Number.isInteger(value) && value! >= 0 && value! <= 10000000 ? value : undefined;
}
function safeFunction(value: string | undefined): string | undefined {
  return value && /^[A-Za-z_$][A-Za-z0-9_$.]{0,79}$/.test(value) ? value : undefined;
}
/** Preserve only same-origin code locations and known exception classes. */
export function sanitizeSentryEvent(event: import("@sentry/browser").ErrorEvent): import("@sentry/browser").ErrorEvent {
  const values = (event.exception?.values ?? []).slice(0, 3).map(value => ({
    type: errorTypes.has(value.type ?? "") ? value.type : "Error",
    stacktrace: { frames: (value.stacktrace?.frames ?? []).slice(-30).flatMap(frame => {
      const filename = safePath(frame.filename); if (!filename) return [];
      return [{ filename, lineno: safeNumber(frame.lineno), colno: safeNumber(frame.colno), function: safeFunction(frame.function) }];
    }) },
  }));
  return { type: undefined, event_id: event.event_id, timestamp: event.timestamp, platform: "javascript", level: "error", tags: { client: TELEMETRY_CLIENT }, exception: { values } };
}
export function sentry(dsn: string, sampleRate: number): TelemetryAdapter {
  let client: import("@sentry/browser").BrowserClient | undefined;
  let onError: ((event: ErrorEvent) => void) | undefined, onRejection: ((event: PromiseRejectionEvent) => void) | undefined;
  return { purpose: "diagnostics", async start(signal, admitted) {
    const sdk = await import("@sentry/browser"); if (signal.aborted || !admitted()) return;
    client = new sdk.BrowserClient({ dsn, sampleRate, transport: sdk.makeFetchTransport, integrations: [], stackParser: sdk.defaultStackParser,
      beforeSend(event) { return admitted() ? sanitizeSentryEvent(event) : null; } });
    client.init(); if (signal.aborted || !admitted()) { void client.close(0); return; }
    onError = event => { if (!admitted()) return; const error = event.error instanceof Error ? event.error : new Error();
      if (!(event.error instanceof Error)) { const path = safePath(event.filename); error.stack = path ? `Error\n    at ${path}:${safeNumber(event.lineno) ?? 0}:${safeNumber(event.colno) ?? 0}` : "Error"; }
      client?.captureException(error); };
    onRejection = event => { if (admitted()) client?.captureException(event.reason instanceof Error ? event.reason : new Error()); };
    window.addEventListener("error", onError); window.addEventListener("unhandledrejection", onRejection);
  }, stop() { if (onError) window.removeEventListener("error", onError); if (onRejection) window.removeEventListener("unhandledrejection", onRejection); void client?.close(0); } };
}
