#!/usr/bin/env node
// Tiny load smoke for the dev stack (NOT part of CI).
//   node scripts/perf/load-smoke.mjs [baseUrl] [makerspaceSlug] [concurrency=20]
// Fires `concurrency` simultaneous GETs at each hot public endpoint and prints status mix + latency.
// Exits 1 on any 5xx or if the slowest request exceeds SLOW_MS (default 3000). 429 is reported, not failed.
const [base = "http://localhost:8000", slug = "makerspace", n = "20"] = process.argv.slice(2);
const concurrency = Number(n);
const slowMs = Number(process.env.SLOW_MS ?? 3000);
const paths = [
  "/api/v1/public/makerspaces/",
  `/api/v1/public/${slug}/inventory/`,
  `/api/v1/public/${slug}/events/`,
  `/api/v1/public/${slug}/spaces/`,
  `/api/v1/public/${slug}/stats/`,
];
let failed = false;
for (const path of paths) {
  const runs = await Promise.all(Array.from({ length: concurrency }, async () => {
    const t0 = performance.now();
    try { const r = await fetch(base + path); await r.arrayBuffer(); return { s: r.status, ms: performance.now() - t0 }; }
    catch { return { s: 0, ms: performance.now() - t0 }; }
  }));
  const mix = {}; runs.forEach((r) => { mix[r.s] = (mix[r.s] ?? 0) + 1; });
  const ms = runs.map((r) => r.ms).sort((a, b) => a - b);
  const p50 = ms[Math.floor(ms.length / 2)], max = ms[ms.length - 1];
  const bad = runs.some((r) => r.s === 0 || r.s >= 500) || max > slowMs;
  failed ||= bad;
  console.log(`${bad ? "FAIL" : "ok  "} ${path} status=${JSON.stringify(mix)} p50=${p50.toFixed(0)}ms max=${max.toFixed(0)}ms`);
}
process.exit(failed ? 1 : 0);
