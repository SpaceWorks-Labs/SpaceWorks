// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { handleRequest } from '../../deploy/static/shared/edge.mjs';

const secret = 'protected-server-edge-secret-123456789';
const environment = { PUBLIC_ORIGIN: 'https://app.example.com', BACKEND_ORIGIN: 'https://api.example.com',
  TRUSTED_EDGE_INGRESS_SECRET: secret };
const assets = async () => new Response('asset', { headers: { 'content-type': 'text/plain' } });

describe('protected edge proof', () => {
  it('replaces caller proof and forwarded authority on every backend proxy', async () => {
    const upstream = vi.fn<typeof fetch>().mockResolvedValue(new Response('ok'));
    const request = new Request('https://app.example.com/api/v1/inventory/', { headers: {
      'X-SpaceWorks-Edge-Secret': 'browser-spoof', 'X-Forwarded-Host': 'evil.example',
      'X-Forwarded-For': '203.0.113.77', 'X-Forwarded-Proto': 'http',
    } });
    expect((await handleRequest(request, environment, assets, upstream, '198.51.100.7')).status).toBe(200);
    const [url, options] = upstream.mock.calls[0];
    expect(String(url)).toBe('https://api.example.com/api/v1/inventory/');
    const headers = new Headers(options?.headers);
    expect(headers.get('X-SpaceWorks-Edge-Secret')).toBe(secret);
    expect(headers.get('X-Forwarded-Host')).toBe('app.example.com');
    expect(headers.get('X-Forwarded-Proto')).toBe('https');
    expect(headers.get('X-Forwarded-For')).toBe('198.51.100.7');
    expect(options?.redirect).toBe('manual');
  });

  it('refuses proxy work if the server secret is missing', async () => {
    const upstream = vi.fn<typeof fetch>();
    const response = await handleRequest(new Request('https://app.example.com/api/v1/inventory/'),
      { ...environment, TRUSTED_EDGE_INGRESS_SECRET: '' }, assets, upstream);
    expect(response.status).toBe(502);
    expect(upstream).not.toHaveBeenCalled();
  });

  it('keeps secrets out of browser config and denies internal scheduler routes', async () => {
    const upstream = vi.fn<typeof fetch>();
    const config = await handleRequest(new Request('https://app.example.com/config.js'), environment, assets, upstream);
    expect(await config.text()).not.toContain(secret);
    const internal = await handleRequest(new Request('https://app.example.com/api/v1/internal/free/tick', { method: 'POST' }), environment, assets, upstream);
    expect(internal.status).toBe(404);
    expect(upstream).not.toHaveBeenCalled();
  });
});


it.each(['/inventory', '/inventory/', '/m/lab/inventory'])('keeps the Inventory app route out of profile crawler proxying: %s', async path => {
  const upstream = vi.fn<typeof fetch>();
  const response = await handleRequest(new Request(`https://app.example.com${path}`, { headers: { 'User-Agent': 'Twitterbot' } }), environment, assets, upstream);
  expect(await response.text()).toBe('asset');
  expect(upstream).not.toHaveBeenCalled();
});
