import { safePage, type Consent, type Purpose } from "./policy";

export type TelemetryAdapter = { purpose: Purpose; start: (signal: AbortSignal, admitted: () => boolean) => Promise<void>; stop: () => void; pageView?: (path: string) => void };
export type AdapterFactory = { purpose: Purpose; load: () => Promise<TelemetryAdapter> };
/** Every admission change aborts pending imports and invalidates the old configuration. */
export class TelemetryController {
  private epoch = 0;
  private abort?: AbortController;
  private active: TelemetryAdapter[] = [];
  stop() { this.epoch++; this.abort?.abort(); this.abort = undefined; for (const item of this.active.splice(0)) { try { item.stop(); } catch { /* best effort; isolation remains mandatory */ } } }
  pageView(path: string) { for (const item of this.active) { try { item.pageView?.(path); } catch { /* provider errors do not affect navigation */ } } }
  async start(url: URL, consent: Consent, factories: AdapterFactory[], stillCurrent: () => boolean) {
    this.stop();
    if (!safePage(url) || !stillCurrent()) return;
    const epoch = this.epoch, abort = new AbortController(); this.abort = abort;
    const admitted = () => epoch === this.epoch && !abort.signal.aborted && stillCurrent() && Boolean(safePage(new URL(window.location.href)));
    for (const factory of factories) {
      if (!admitted() || !consent[factory.purpose]) continue;
      let adapter: TelemetryAdapter;
      try { adapter = await factory.load(); } catch { continue; }
      if (!admitted() || adapter.purpose !== factory.purpose || !consent[adapter.purpose]) continue;
      this.active.push(adapter);
      try { await adapter.start(abort.signal, admitted); } catch { try { adapter.stop(); } catch { /* best effort */ } this.active = this.active.filter(item => item !== adapter); }
      if (!admitted()) { try { adapter.stop(); } catch { /* best effort */ } }
    }
  }
}


