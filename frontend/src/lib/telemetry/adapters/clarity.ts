import type { TelemetryAdapter } from "../controller";
import { TELEMETRY_CLIENT } from "../client";

type ClarityCommand = ((command: string, ...values: unknown[]) => void) & { q?: unknown[][] };
declare global { interface Window { clarity?: ClarityCommand } }
/** Confined to an isolated, consented anonymous About document. */
export function clarity(projectId: string): TelemetryAdapter {
  let script: HTMLScriptElement | undefined;
  let stopped = false;
  return { purpose: "replay", async start(signal, admitted) {
    if (signal.aborted || !admitted()) return;
    document.documentElement.setAttribute("data-clarity-mask", "True");
    const queue: ClarityCommand = (command, ...values) => { (queue.q ??= []).push([command, ...values]); };
    window.clarity = queue;
    queue("consentv2", { ad_Storage: "denied", analytics_Storage: "granted" });
    queue("set", "client", TELEMETRY_CLIENT);
    script = document.createElement("script"); script.async = true; script.referrerPolicy = "no-referrer";
    script.src = `https://www.clarity.ms/tag/${encodeURIComponent(projectId)}`;
    if (!signal.aborted && admitted()) document.head.append(script);
  }, stop() {
    if (stopped || !script) return;
    stopped = true;
    // Denied consent still tracks, and stop flushes. Seal this document before
    // vendor teardown; the telemetry runtime then replaces the document.
    const policy = document.createElement("meta");
    policy.httpEquiv = "Content-Security-Policy";
    policy.content = "connect-src 'self'; script-src 'self'; img-src 'self' data: blob:";
    document.head.prepend(policy);
    try { window.clarity?.("consentv2", { ad_Storage: "denied", analytics_Storage: "denied" }); } catch { /* the outbound barrier remains */ }
    try { window.clarity?.("stop", undefined); } catch { /* document replacement remains mandatory */ }
    script?.remove();
  } };
}
