import { httpsOrigin } from '../../shared/security.mjs';

const TICK_PATH = '/api/v1/internal/free/tick';
const RETRYABLE = new Set([429, 502, 503, 504]);
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function readSummary(response) {
  if (!response.body) throw new Error('invalid_tick_response');
  const reader = response.body.getReader();
  const chunks = []; let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 65536) throw new Error('invalid_tick_response');
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  const data = JSON.parse(new TextDecoder().decode(bytes));
  if (!data || !Number.isInteger(data.failed) || data.failed < 0) throw new Error('invalid_tick_response');
  return data;
}

export async function runScheduledTick(env, fetcher = fetch, sleep = wait) {
  if (env.SPACEWORKS_DEPLOYMENT_PROFILE !== 'free') throw new Error('free_profile_required');
  const secret = env.FREE_TICK_SECRET;
  if (typeof secret !== 'string' || !/^[\x21-\x7e]{32,256}$/.test(secret)) throw new Error('tick_secret_required');
  const endpoint = httpsOrigin(env.BACKEND_ORIGIN) + TICK_PATH;
  // Three attempts, <=~4.5 minutes including cold wake-up. No secret-bearing redirects.
  for (let attempt = 0; attempt < 3; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 85000);
    let retry = true;
    try {
      const response = await fetcher(endpoint, { method: 'POST', redirect: 'manual',
        headers: { 'X-Cron-Secret': secret, 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: '{}', signal: controller.signal });
      if (response.status === 200) {
        const summary = await readSummary(response);
        if (summary.failed === 0) return { status: 'completed' };
      } else {
        retry = RETRYABLE.has(response.status);
        await response.body?.cancel();
      }
    } catch { /* Transient transport/cold-start failure; never expose response bodies. */ }
    finally { clearTimeout(timer); }
    if (!retry || attempt === 2) throw new Error('free_tick_failed');
    await sleep(attempt === 0 ? 2000 : 5000);
  }
  throw new Error('free_tick_failed');
}
