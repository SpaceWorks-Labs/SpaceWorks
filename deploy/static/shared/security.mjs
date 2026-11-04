export function httpsOrigin(value) {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/'
      || url.search || url.hash) throw new Error('invalid_origin');
  return url.origin;
}

function origins(value = '') {
  return value.split(/\s+/).filter(Boolean).map(httpsOrigin).join(' ');
}

export function publicConfig(env) {
  const apiUrl = env.PUBLIC_API_URL || '/api';
  if (apiUrl !== '/api') {
    const url = new URL(apiUrl);
    httpsOrigin(url.origin);
    if (url.pathname !== '/api' || url.username || url.password || url.search || url.hash) throw new Error('invalid_api_url');
  }
  const config = { apiUrl, originBootstrap: env.ORIGIN_BOOTSTRAP === 'true' };
  if (env.PUBLIC_TENANT_TOKEN) {
    if (env.PUBLIC_TENANT_TOKEN.length > 4096 || /[\u0000-\u0020\u007f]/.test(env.PUBLIC_TENANT_TOKEN)) throw new Error('invalid_public_tenant_token');
    config.tenantToken = env.PUBLIC_TENANT_TOKEN;
  }
  return config;
}

export function securityHeaders(env, headers = new Headers(), { embed = false, privateResponse = true } = {}) {
  headers.set('X-Content-Type-Options', 'nosniff');
  headers.set('Referrer-Policy', 'no-referrer');
  headers.set('Strict-Transport-Security', 'max-age=31536000');
  headers.set('Permissions-Policy', 'camera=(self), microphone=(), geolocation=(self)');
  if (!embed) {
    headers.set('X-Frame-Options', 'DENY');
    // Explicit origin lists only; no wildcard storage, preview or analytics trust.
    headers.set('Content-Security-Policy', [
      "default-src 'self'", `script-src 'self' 'wasm-unsafe-eval' ${origins(env.ANALYTICS_SCRIPT_ORIGINS)}`,
      "style-src 'self' 'unsafe-inline'", "font-src 'self'", "worker-src 'self' blob:",
      `connect-src 'self' ${origins(env.CONNECT_ORIGINS)}`,
      `img-src 'self' data: blob: ${origins(env.IMAGE_ORIGINS)}`,
      `media-src 'self' blob: ${origins(env.MEDIA_ORIGINS)}`, "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
    ].join('; '));
  }
  if (privateResponse) {
    headers.set('Cache-Control', 'no-store');
    headers.set('CDN-Cache-Control', 'no-store');
    headers.set('Vercel-CDN-Cache-Control', 'no-store');
    headers.set('Netlify-CDN-Cache-Control', 'no-store');
    headers.delete('Expires'); headers.delete('ETag');
  }
  return headers;
}

export function failure(status, code) {
  return new Response(JSON.stringify({ code }), { status, headers: {
    'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
  } });
}
