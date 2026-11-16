import { expect, test } from "@playwright/test";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import ts from "typescript";

// Isolated browser-network regressions: no application stack or real vendor account.
// Compile the production loader, rather than copying its script creation logic.
const source = ts.transpileModule(readFileSync(new URL("../src/lib/telemetry/adapters/mixpanelSdk.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const app = "https://app.example.test", sdk = "https://sdk.example.test";

test("SDK request omits existing cookies, authorization and referrer, and ignores Set-Cookie", async ({ page, context }) => {
  await context.addCookies([{ name: "sdk_session", value: "existing-identity", url: sdk, secure: true, httpOnly: true, sameSite: "Strict" }]);
  await page.route(`${app}/**`, route => route.fulfill({ contentType: "text/html", body: "<!doctype html><title>SDK privacy</title>" }));
  let headers: Record<string, string> | undefined;
  await page.route(`${sdk}/**`, async route => {
    const control = route.request().url().endsWith("/control.js");
    if (!control) headers = await route.request().allHeaders();
    await route.fulfill({ contentType: "application/javascript", headers: {
      "Access-Control-Allow-Origin": app, "Access-Control-Allow-Credentials": "true",
      "Set-Cookie": `${control ? "control" : "tracking"}=response-identity; Path=/; Secure; SameSite=Strict`,
    }, body: "window.mixpanel = { init: function () {} };" });
  });
  await page.goto(`${app}/about`);
  const loaded = await page.evaluate(async ({ source, sdk }) => {
    const exports = {} as { loadMixpanel: (host: string, signal: AbortSignal) => Promise<unknown> };
    new Function("exports", source)(exports);
    return Boolean(await exports.loadMixpanel(sdk, new AbortController().signal));
  }, { source, sdk });
  expect(loaded).toBe(true); expect(headers).toBeDefined();
  expect(headers!["cookie"]).toBeUndefined(); expect(headers!["authorization"]).toBeUndefined();
  expect(headers!["referer"]).toBeUndefined(); expect(headers!["sec-fetch-mode"]).toBe("cors");
  expect((await context.cookies(sdk)).map(cookie => cookie.name)).toEqual(["sdk_session"]);

  // Positive control: the fixture/browser really can send and set cookies on this host.
  const controlRequest = page.waitForRequest(`${sdk}/control.js`);
  await page.evaluate(async sdk => {
    const script = document.createElement("script"); script.crossOrigin = "use-credentials";
    await new Promise<void>((resolve, reject) => {
      script.onload = () => resolve(); script.onerror = () => reject(new Error("control_load_failed"));
      script.src = `${sdk}/control.js`; document.head.append(script);
    });
  }, sdk);
  expect((await (await controlRequest).allHeaders())["cookie"]).toBe("sdk_session=existing-identity");
  expect((await context.cookies(sdk)).map(cookie => cookie.name).sort()).toEqual(["control", "sdk_session"]);
});

test("same-origin loader refuses the SDK without making a request", async ({ page }) => {
  const requested: string[] = [];
  await page.route(`${app}/**`, route => {
    if (route.request().url().startsWith(`${app}/libs/`)) requested.push(route.request().url());
    return route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Mirror refusal</title>" });
  });
  await page.goto(`${app}/about`);
  const loaded = await page.evaluate(async ({ source, app }) => {
    const exports = {} as { loadMixpanel: (host: string, signal: AbortSignal) => Promise<unknown> };
    new Function("exports", source)(exports);
    return exports.loadMixpanel(app, new AbortController().signal);
  }, { source, app });
  expect(loaded).toBeNull(); expect(requested).toEqual([]);
  await expect(page.locator("#spaceworks-mixpanel")).toHaveCount(0);
});

for (const mirror of [app, "https://APP.example.test:443", sdk]) {
  test(`shell-generated config refuses same-origin mirror and preserves CSP: ${mirror}`, async ({ page }) => {
    test.skip(Boolean(spawnSync("sh", ["-c", "exit 0"]).error), "sh is required to exercise the real entrypoint");
    const directory = mkdtempSync(join(tmpdir(), "cx15-mirror-"));
    try {
      const config = join(directory, "config.js"), headers = join(directory, "headers.conf");
      const env = { ...process.env,
        WEB_ANALYTICS_SCRIPT_URL: "", WEB_ANALYTICS_COLLECT_URL: "", WEB_ANALYTICS_DOMAIN: "",
        WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS: "", WEB_TELEMETRY_ALLOWED_ORIGINS: "", TURNSTILE_SITE_KEY: "",
        WEB_TELEMETRY_MIXPANEL_TOKEN: "public-token", WEB_TELEMETRY_MIXPANEL_API_HOST: "https://api.mixpanel.com",
        WEB_TELEMETRY_MIXPANEL_SDK_HOST: mirror, WEB_ANALYTICS_HEADERS_PATH: headers, TENANT_CONFIG_PATH: config,
      };
      const entrypoint = fileURLToPath(new URL("../docker-entrypoint.d/40-web-analytics.sh", import.meta.url));
      const result = spawnSync("sh", [entrypoint.replace(/\\/g, "/")], { env, encoding: "utf8" });
      expect(result.status).toBe(0); expect(result.stderr).toBe("");
      await page.route(`${app}/**`, route => route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Config</title>" }));
      await page.goto(`${app}/about`);
      await page.addScriptTag({ content: readFileSync(config, "utf8") });
      const selected = await page.evaluate(() => (window as Window & { __MIXPANEL__?: unknown }).__MIXPANEL__ ?? null);
      expect(selected).toEqual(mirror === sdk ? { token: "public-token", apiHost: "https://api.mixpanel.com", sdkHost: sdk } : null);
      const csp = readFileSync(headers, "utf8");
      expect(csp.match(/script-src ([^;]+)/)![1].split(/\s+/).filter(Boolean)).toEqual([
        "'self'", "'wasm-unsafe-eval'", "https://accounts.google.com", "https://appleid.cdn-apple.com", mirror,
      ]);
      expect(csp.match(/connect-src ([^;]+)/)![1].split(/\s+/).filter(Boolean)).toEqual([
        "'self'", "https://accounts.google.com", "https://oauth2.googleapis.com", "https://appleid.apple.com", "https://api.mixpanel.com",
      ]);
    } finally { rmSync(directory, { recursive: true, force: true }); }
  });
}
