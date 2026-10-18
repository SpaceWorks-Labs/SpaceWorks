import { route, safePath } from './routes.mjs';
import { failure, httpsOrigin, publicConfig, securityHeaders } from './security.mjs';

const STRIP = ['forwarded', 'x-real-ip', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto',
  'x-forwarded-port', 'x-cron-secret', 'x-original-url', 'x-rewrite-url', 'host',
  'connection', 'transfer-encoding', 'upgrade', 'proxy-authorization', 'cf-access-jwt-assertion'];

export async function handleRequest(request, env, assets, fetcher = fetch, clientIp = '') {
  try {
    const url = new URL(request.url);
    if (url.origin !== httpsOrigin(env.PUBLIC_ORIGIN)) return failure(404, 'not_found');
    if (httpsOrigin(env.BACKEND_ORIGIN) === url.origin) return failure(502, 'invalid_upstream');
    const path = safePath(url.pathname);
    if (!path) return failure(404, 'not_found');
    const target = route(path, request.headers.get('user-agent') || '');
    if (target.kind === 'deny') return failure(404, 'not_found');
    if (target.kind === 'config') {
      if (!['GET', 'HEAD'].includes(request.method)) return failure(405, 'method_not_allowed');
      const config = publicConfig(env);
      return new Response(request.method === 'HEAD' ? null : `window.__TENANT__ = ${JSON.stringify(config)};\n`, {
        headers: securityHeaders(env, new Headers({ 'Content-Type': 'application/javascript; charset=utf-8' })),
      });
    }
    if (target.kind === 'asset') {
      if (!['GET', 'HEAD'].includes(request.method)) return failure(405, 'method_not_allowed');
      const response = await assets(request);
      // A missing script, WASM or font must never receive the SPA document.
      const isHtml = response.headers.get('content-type')?.includes('text/html');
      if (isHtml && ((/\.[a-z0-9]+$/i.test(path) && !path.endsWith('.html'))
          || /^\/(?:assets|fonts|brand)(?:\/|$)/.test(path))) return failure(404, 'not_found');
      return new Response(response.body, { status: response.status,
        headers: securityHeaders(env, new Headers(response.headers), { privateResponse: true }) });
    }
    const live = /^\/api\/v1\/live\/?$/.test(path);
    if (live && (env.SPACEWORKS_DEPLOYMENT_PROFILE === 'free' || !env.LIVE_ORIGIN)) {
      return failure(503, 'live_unavailable_use_polling');
    }
    const upstream = new URL(target.path + url.search, httpsOrigin(live ? env.LIVE_ORIGIN : env.BACKEND_ORIGIN));
    const headers = new Headers(request.headers);
    for (const name of (headers.get('connection') || '').split(',')) if (name.trim()) headers.delete(name.trim());
    for (const name of STRIP) headers.delete(name);
    for (const name of [...headers.keys()]) {
      if (/^(?:x-forwarded-|x-middleware-|x-vercel-)/i.test(name)) headers.delete(name);
    }
    headers.set('X-Forwarded-Host', url.host);
    headers.set('X-Forwarded-Proto', 'https');
    if (clientIp) headers.set('X-Forwarded-For', clientIp);
    const response = await fetcher(upstream, { method: request.method, headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      duplex: 'half', redirect: 'manual', signal: request.signal });
    const output = new Headers(response.headers);
    // Host-only Secure auth cookies need no rewrite. Refuse a mismatched Domain.
    const cookies = typeof output.getSetCookie === 'function' ? output.getSetCookie() : [output.get('set-cookie') || ''];
    for (const cookie of cookies) {
      for (const match of cookie.matchAll(/;\s*domain=([^;,\s]+)/ig)) {
        const domain = match[1].replace(/^\./, '').toLowerCase();
        if (domain !== url.hostname) return failure(502, 'cookie_domain_mismatch');
      }
    }
    const location = output.get('location');
    if (location) {
      const redirect = new URL(location, upstream);
      if (redirect.origin === upstream.origin) {
        if (route(safePath(redirect.pathname) || '/control').kind === 'deny') return failure(404, 'not_found');
        output.set('location', url.origin + redirect.pathname + redirect.search + redirect.hash);
      }
    }
    return new Response(response.body, { status: response.status,
      headers: securityHeaders(env, output, { embed: /^\/(?:embed|docs|redoc)(?:\/|$)/.test(path) }) });
  } catch { return failure(502, 'upstream_unavailable'); }
}
