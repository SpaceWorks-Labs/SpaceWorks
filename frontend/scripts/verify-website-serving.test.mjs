// Protect composition of Lane C website routing and Lane F analytics headers.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { URL } from "node:url";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const nginx = read("../nginx.conf");
const allInOne = read("../../docker/allinone/nginx.conf");
const caddy = read("../../deploy/Caddyfile");
const saas = read("../../deploy/Caddyfile.saas");
const installer = read("../../deploy/Caddyfile.saas-install");
const runtimeHeaders = read("../docker-entrypoint.d/40-web-analytics.sh");

function block(source, label) {
  const start = source.indexOf(`${label} {`);
  assert.ok(start >= 0, `missing ${label}`);
  const open = source.indexOf("{", start + label.length);
  let depth = 1;
  let end = open + 1;
  for (; depth && end < source.length; end++) {
    if (source[end] === "{") depth++;
    if (source[end] === "}") depth--;
  }
  return source.slice(open + 1, end - 1);
}

for (const [name, config] of [["frontend", nginx], ["single-box", allInOne]]) describe(`${name} website routing`, () => {
  it("protects framing on index fallback and every static location", () => {
    assert.ok(config.includes('add_header X-Frame-Options "DENY" always;'));
    assert.ok(config.includes("frame-ancestors 'none'"));
    for (const location of ["location /", "location = /index.html", "location /assets/",
      "location = /config.js", "location = /sw.js", "location = /member-sw.js"]) {
      assert.ok(block(config, location).includes("analytics-headers.conf;"));
    }
    assert.ok(block(config, "location /").includes("try_files $uri $uri/ /index.html;"));
  });
  it("leaves embed CSP and framing to Django, with forwarded host and client identity", () => {
    const embed = block(config, "location /embed/");
    assert.ok(embed.includes("proxy_pass http://"));
    // A local add_header suppresses nginx server-level header inheritance.
    assert.ok(embed.includes('add_header X-Content-Type-Options "nosniff" always;'));
    assert.doesNotMatch(embed, /analytics-headers|frame-ancestors|X-Frame-Options/);
    assert.ok(!config.includes("add_header Referrer-Policy"));
    assert.ok(embed.includes("proxy_set_header Host $host;"));
    assert.ok(embed.includes("proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"));
    assert.ok(embed.includes("proxy_set_header X-Forwarded-Proto $external_scheme;"));
  });
  it("routes both domains' crawler cards, directory files, uploads and credential feeds", () => {
    assert.ok(config.includes("rewrite ^ /share/events/$event_share_token/ last;"));
    assert.ok(config.includes("rewrite ^ /share/bookings/$booking_share_token/ last;"));
    assert.ok(config.includes("share/|sitemap\\.xml$|robots\\.txt$"));
    assert.ok(config.includes("(events|event-series|spaces)/[0-9]+/website/assets/$"));
    assert.ok(config.includes("client_max_body_size 6m;"));
    assert.ok(config.includes("(event-calendar|bookings/calendar)"));
    assert.ok(config.includes("proxy_buffering off;"));
  });
});

for (const [name, config] of [["self-host", caddy], ["SaaS", saas], ["installer", installer]]) describe(`${name} edge headers`, () => {
  it("adds framing protection while preserving the upstream analytics CSP", () => {
    const frontend = block(config, "reverse_proxy {$SPACEWORKS_WEB_UPSTREAM:frontend:80}");
    assert.ok(frontend.includes('header_down X-Frame-Options "DENY"'));
    assert.ok(frontend.includes("header_down Referrer-Policy strict-origin"));
    assert.doesNotMatch(config, /(?:^|\n)\s*header Referrer-Policy/);
    assert.ok(frontend.includes("header_down +Content-Security-Policy \"frame-ancestors 'none'\""));
    assert.doesNotMatch(frontend, /header_down Content-Security-Policy/);
    assert.ok(config.includes("@backend path /embed/* /share/* /sitemap.xml /robots.txt"));
    assert.ok(config.includes("rewrite * /share/events/{re.event_card.2}/"));
    assert.ok(config.includes("rewrite * /share/bookings/{re.booking_card.2}/"));
  });
});

it("emits default framing protection before analytics can opt out", () => {
  const disabled = runtimeHeaders.slice(0, runtimeHeaders.indexOf('if [ -z "$script$collect$domain" ]'));
  assert.ok(disabled.includes('add_header X-Frame-Options "DENY" always;'));
  assert.ok(disabled.includes("frame-ancestors 'none'"));
  assert.ok(runtimeHeaders.includes("script-src"));
  assert.ok(runtimeHeaders.includes("connect-src"));
});
