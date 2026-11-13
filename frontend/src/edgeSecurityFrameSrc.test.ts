// @vitest-environment node
import { describe, expect, it } from 'vitest';
// @ts-ignore security.mjs ships without a declaration file; the checks below pin its behaviour.
import { securityHeaders } from '../../deploy/static/shared/security.mjs';

type Env = Record<string, string | undefined>;
const csp = (env: Env, options?: { embed?: boolean }) => String(securityHeaders(env, new Headers(), options).get('Content-Security-Policy'));
const directive = (policy: string, name: string) => policy.split('; ').find(part => part.startsWith(`${name} `));

describe('edge Content-Security-Policy frame-src (AN-5, decision 263)', () => {
  it('trusts only the page itself while FRAME_ORIGINS is unset', () => {
    expect(directive(csp({}), 'frame-src')?.trim()).toBe("frame-src 'self'");
  });

  it('adds each configured https origin for embedded Metabase or Grafana dashboards', () => {
    const policy = csp({ FRAME_ORIGINS: 'https://metabase.example.com  https://grafana.example.com:3000' });
    expect(directive(policy, 'frame-src')).toBe("frame-src 'self' https://metabase.example.com https://grafana.example.com:3000");
  });

  it('keeps frame-ancestors none so SpaceWorks itself cannot be framed', () => {
    const policy = csp({ FRAME_ORIGINS: 'https://metabase.example.com' });
    expect(directive(policy, 'frame-ancestors')).toBe("frame-ancestors 'none'");
    expect(directive(policy, 'default-src')).toBe("default-src 'self'");
  });

  it.each([
    'http://metabase.example.com',
    'https://metabase.example.com/dashboards',
    'https://user:pw@metabase.example.com',
    'https://metabase.example.com?x=1',
    '*',
    'not a url',
  ])('refuses the unsafe frame origin %s', value => {
    expect(() => csp({ FRAME_ORIGINS: value })).toThrow();
  });

  it('does not use FRAME_ORIGINS to widen script, connect or image trust', () => {
    const policy = csp({ FRAME_ORIGINS: 'https://metabase.example.com' });
    for (const name of ['script-src', 'connect-src', 'img-src', 'media-src']) {
      expect(directive(policy, name)).not.toContain('metabase.example.com');
    }
  });

  it('sets no CSP on embed responses (they carry their own framing policy)', () => {
    const headers = securityHeaders({ FRAME_ORIGINS: 'https://metabase.example.com' }, new Headers(), { embed: true });
    expect(headers.get('Content-Security-Policy')).toBeNull();
    expect(headers.get('X-Frame-Options')).toBeNull();
  });
});
