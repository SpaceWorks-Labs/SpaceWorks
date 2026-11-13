// SPA runtime headers must survive analytics opt-out and index fallback.
import { expect, it } from "vitest";
import nginx from "../../nginx.conf?raw";
import runtimeHeaders from "../../docker-entrypoint.d/40-web-analytics.sh?raw";

it("emits default framing protection before analytics can opt out", () => {
  const disabled = runtimeHeaders.slice(0, runtimeHeaders.indexOf('if [ -z "$script$collect$domain" ]'));
  expect(disabled).toContain('add_header X-Frame-Options "DENY" always;');
  expect(disabled).toContain("frame-ancestors 'none'");
  expect(runtimeHeaders).toContain("script-src");
  expect(runtimeHeaders).toContain("connect-src");
  expect(nginx).toContain("try_files $uri $uri/ /index.html;");
  expect(nginx).toContain("include /etc/nginx/analytics-headers.conf;");
});
