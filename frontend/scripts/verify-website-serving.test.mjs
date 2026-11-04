// Protect composition of Lane C website routing and Lane F analytics headers.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { URL, fileURLToPath } from "node:url";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const nginx = read("../nginx.conf");
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

describe("frontend website routing", () => {
  const config = nginx;
  it("protects framing on index fallback and every static location", () => {
    // All SPA policies come from the runtime include. A location's Cache-Control
    // add_header would otherwise discard inherited server-level security headers.
    assert.doesNotMatch(config, /add_header (?:X-Frame-Options|Content-Security-Policy|Referrer-Policy)/);
    assert.ok(runtimeHeaders.includes('add_header X-Frame-Options "DENY" always;'));
    assert.ok(runtimeHeaders.includes("frame-ancestors 'none'"));
    for (const location of ["location /", "location = /index.html", "location /assets/",
      "location = /config.js", "location = /sw.js", "location = /member-sw.js"]) {
      assert.ok(block(config, location).includes("analytics-headers.conf;"));
    }
    assert.ok(block(config, "location /").includes("try_files $uri $uri/ /index.html;"));
  });
  it("leaves embed CSP and framing to Django, with forwarded host and client identity", () => {
    const embed = block(config, "location /embed/");
    assert.ok(embed.includes("proxy_pass http://"));
    // Backend responses own their framing/CSP/referrer policies; nginx passes them through.
    assert.ok(embed.includes('add_header X-Content-Type-Options "nosniff" always;'));
    assert.doesNotMatch(embed, /analytics-headers|frame-ancestors|X-Frame-Options|Referrer-Policy|proxy_hide_header/);
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
  assert.ok(disabled.includes('add_header Referrer-Policy strict-origin always;'));
  assert.ok(disabled.includes('add_header X-Frame-Options "DENY" always;'));
  assert.ok(disabled.includes("frame-ancestors 'none'"));
  assert.ok(runtimeHeaders.includes("script-src"));
  assert.ok(runtimeHeaders.includes("connect-src"));
});

// Execute the real entrypoint as well as checking nginx's include placement.
const shell = process.platform === "win32"
  ? join(process.env.ProgramFiles || "C:/Program Files", "Git/bin/bash.exe")
  : "/bin/sh";
function generatedHeaders(settings) {
  const directory = mkdtempSync(join(tmpdir(), "spaceworks-headers-"));
  const headers = join(directory, "headers.conf");
  try {
    const result = spawnSync(shell, [fileURLToPath(new URL("../docker-entrypoint.d/40-web-analytics.sh", import.meta.url))], {
      encoding: "utf8", timeout: 10_000,
      env: { ...process.env, WEB_ANALYTICS_SCRIPT_URL: "", WEB_ANALYTICS_COLLECT_URL: "",
        WEB_ANALYTICS_DOMAIN: "", WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS: "", ...settings,
        WEB_ANALYTICS_HEADERS_PATH: headers.replaceAll("\\", "/"),
        TENANT_CONFIG_PATH: join(directory, "config.js").replaceAll("\\", "/") },
    });
    assert.equal(result.status, 0, result.stderr || result.error?.message);
    return readFileSync(headers, "utf8");
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

it("generates SPA security headers when analytics is disabled", { skip: !existsSync(shell) }, () => {
  assert.equal(generatedHeaders({}), [
    "add_header Referrer-Policy strict-origin always;",
    'add_header X-Frame-Options "DENY" always;',
    `add_header Content-Security-Policy "frame-ancestors 'none'" always;`, "",
  ].join("\n"));
});

it("composes analytics restrictions with framing and explicit API/storage origins", { skip: !existsSync(shell) }, () => {
  const headers = generatedHeaders({
    WEB_ANALYTICS_SCRIPT_URL: "https://stats.example.org/js/script.manual.js",
    WEB_ANALYTICS_COLLECT_URL: "https://stats.example.org/api/event",
    WEB_ANALYTICS_DOMAIN: "space.example.org",
    WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS: "https://api.example.org https://files.example.org",
  });
  assert.equal((headers.match(/add_header Content-Security-Policy /g) || []).length, 2);
  assert.ok(headers.includes("frame-ancestors 'none'"));
  assert.match(headers, /script-src [^;]+https:\/\/stats\.example\.org;/);
  assert.match(headers, /connect-src [^;]+https:\/\/stats\.example\.org https:\/\/api\.example\.org https:\/\/files\.example\.org/);
});
