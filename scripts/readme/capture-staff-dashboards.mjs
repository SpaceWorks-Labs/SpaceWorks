#!/usr/bin/env node
// Captures the README staff-dashboard gallery: one screen per console area, light AND dark,
// plus the public TV screen. NOT part of CI; run it by hand against the dev stack once the
// showcase seed is loaded.
//
//   cd frontend && node ../scripts/readme/capture-staff-dashboards.mjs [--only a,b] [--dry-run]
//
// Needs `manage.py seed_showcase --reset --password ...` (the Tinkerspace space) and:
//   E2E_SHOWCASE_PASSWORD   the showcase password (never printed)
//   E2E_BASE_URL            default http://localhost:5100 (the dev frontend)
//   E2E_API_URL             default http://localhost:8100 (only used for the TV setup)
//   E2E_BACKEND_CONTAINER   default spaceworks-backend (the sign-in code is read from its log)
// Output: docs/readme/screens/<area>-light.webp and <area>-dark.webp (1280x800), and for the
// TV: staff-tv-light/-dark.webp at 1920x1080. Conversion to WebP uses `sharp` when installed,
// else the `cwebp` binary; without either the PNGs are kept and the script says so.
import { spawnSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, request as pwRequest } from "@playwright/test";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const OUT = join(ROOT, "docs", "readme", "screens");
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:5100";
const API = process.env.E2E_API_URL ?? "http://localhost:8100";
const CONTAINER = process.env.E2E_BACKEND_CONTAINER ?? "spaceworks-backend";
const SLUG = "tinkerspace";
const USER = { username: "tinker_manager", email: "tinker.manager@example.org", password: process.env.E2E_SHOWCASE_PASSWORD ?? "" };
const THEME_KEY = "makerspace.theme";
const args = process.argv.slice(2);
const only = args.includes("--only") ? new Set(args[args.indexOf("--only") + 1].split(",")) : null;
const dry = args.includes("--dry-run");

// area -> the console tab path (see TAB_PATHS in frontend/src/features/staff/staffTabs.ts) and
// the seeded data that makes it worth a picture. One route per area, chosen for populated rows.
export const AREAS = [
  ["staff-home", "dashboard", "What needs the manager today"],
  ["staff-requests", "requests", "Borrow requests waiting for a decision"],
  ["staff-direct", "direct-handout", "Direct handout at the counter"],
  ["staff-pickups", "handover", "Machine-job pickups"],
  ["staff-items", "inventory", "Item list with stock and QR state"],
  ["staff-ledger", "ledger", "Stock movement ledger"],
  ["staff-scanner", "scanner", "Scan-first lookup"],
  ["staff-repair-shelf", "to-be-fixed", "Damaged units and repairs"],
  ["staff-to-buy", "to-buy", "Shopping list"],
  ["staff-consumables", "consumables", "Consumables stock"],
  ["staff-stocktake", "stocktake", "Stocktake sessions"],
  ["staff-transfers", "transfers", "Stock transfers"],
  ["staff-containers", "containers", "Container hierarchy"],
  ["staff-qr", "qr-tools", "QR print batches"],
  ["staff-accountability", "accountability", "Lost and damaged follow-up"],
  ["staff-machines-registry", "machines", "Machine registry and usage"],
  ["staff-repairs", "repairs", "Repairs and issue reports"],
  ["staff-devices", "devices", "Connected printers and label devices"],
  ["staff-schedule", "schedule", "Staff schedule across bookings, events and jobs"],
  ["staff-events", "events", "Events list"],
  ["staff-bookings", "bookings", "Booking queue"],
  ["staff-members", "members", "Members and the join queue"],
  ["staff-cards", "member-cards", "Member ID cards"],
  ["staff-payments", "payments", "Payments and dues"],
  ["staff-refunds", "refunds", "Refunds"],
  ["staff-finance", "finance", "Finance ledger"],
  ["staff-donations", "donations", "Gifts and sponsors"],
  ["staff-shop", "shop", "Shop sales and stock"],
  ["staff-reports", "reports", "Reports and exports"],
  ["staff-analytics", "analytics", "Metabase dashboards"],
  ["staff-audit", "audit", "Audit log"],
  ["staff-inbox", "notifications", "Notification inbox"],
  ["staff-incidents", "incidents", "Incident register"],
  ["staff-organizations", "organizations", "Organizations across venues"],
  ["staff-roles", "users", "Staff and roles"],
  ["staff-settings", "settings", "Space settings"],
  ["staff-modules", "modules", "Modules and capabilities"],
  ["staff-email-templates", "email-templates", "Email templates"],
  ["staff-api", "api-access", "API clients"],
  ["staff-backups", "backup-restore", "Backups"],
];
// The public TV screen is its own area: it has no console chrome and renders at 1920x1080.
const TV = "staff-tv";

function emailedCode(since) {
  const run = spawnSync("docker", ["logs", "--since", since, CONTAINER], { encoding: "utf8", maxBuffer: 64 << 20 });
  const log = `${run.stdout ?? ""}\n${run.stderr ?? ""}`;
  const codes = [...log.matchAll(/^\s*(\d{6})\s*$/gm)].map((m) => m[1]);
  return codes.at(-1) ?? "";
}

async function signIn(page) {
  const since = new Date(Date.now() - 60_000).toISOString();
  await page.goto(`${BASE}/m/${SLUG}/admin`);
  await page.getByLabel("Email", { exact: true }).fill(USER.email);
  await page.getByLabel("Password", { exact: true }).fill(USER.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const step = page.getByRole("heading", { name: "Check your email" });
  const shell = page.locator("[data-app-shell]");
  await step.or(shell).first().waitFor({ timeout: 20_000 });
  if (await step.isVisible()) {
    await page.waitForTimeout(2_000);
    await page.getByLabel("Emailed code").fill(emailedCode(since));
    await page.getByRole("button", { name: "Verify" }).click();
  }
  await shell.waitFor({ timeout: 20_000 });
}

async function toWebp(png, target) {
  try {
    const sharp = (await import("sharp")).default;
    await sharp(png).webp({ quality: 82 }).toFile(target);
  } catch {
    const run = spawnSync("cwebp", ["-q", "82", png, "-o", target]);
    if (run.status !== 0) { console.warn(`no webp encoder; kept ${png}`); return; }
  }
  rmSync(png, { force: true });
}

async function shoot(page, area, theme, size) {
  await page.addInitScript(([key, value]) => { try { localStorage.setItem(key, value); } catch { /* private mode */ } }, [THEME_KEY, theme]);
  await page.setViewportSize(size);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const png = join(OUT, `${area}-${theme}.png`);
  await page.screenshot({ path: png });
  await toWebp(png, join(OUT, `${area}-${theme}.webp`));
}

/** Pairs a TV the way a space does: switches the screen feature on, issues an address, sets a banner. */
async function provisionTv(theme) {
  const api = await pwRequest.newContext();
  const login = await api.post(`${API}/api/v1/auth/login`, { data: { username: USER.username, password: USER.password } });
  const { access } = await login.json();
  const headers = { Authorization: `Bearer ${access}` };
  const spaces = await (await api.get(`${API}/api/v1/admin/makerspaces?search=${SLUG}`, { headers })).json();
  const space = (spaces.results ?? spaces).find((row) => row.slug === SLUG);
  const features = [...new Set([...space.enabled_features, "presence.public_display"])];
  await api.patch(`${API}/api/v1/admin/makerspaces/${space.id}`, { headers, data: { enabled_features: features } });
  const shown = await api.post(`${API}/api/v1/admin/makerspace/${space.id}/presence-displays/link`, {
    headers, data: { name: "Workshop TV", panels: ["announcement", "here_now", "calendar", "machines"], layout: "grid", theme,
      announcement: "Open night this Thursday, 6 pm. Bring a project." },
  });
  const row = await shown.json();
  return row.url; // carries the secret in the #k= fragment; never logged
}

const browser = await chromium.launch();
mkdirSync(OUT, { recursive: true });
const picked = AREAS.filter(([area]) => !only || only.has(area));
if (dry) {
  for (const [area, path, why] of picked) console.log(`${area}: /m/${SLUG}/admin/${path} (${why})`);
  console.log(`${TV}: /display#k=<issued secret> at 1920x1080 (needs Presence + Machines + Events on, members checked in)`);
  await browser.close();
  process.exit(0);
}
if (!USER.password) { console.error("Set E2E_SHOWCASE_PASSWORD."); process.exit(1); }
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await context.newPage();
await signIn(page);
for (const [area, path] of picked) {
  await page.goto(`${BASE}/m/${SLUG}/admin/${path}`, { waitUntil: "networkidle" });
  for (const theme of ["light", "dark"]) await shoot(page, area, theme, { width: 1280, height: 800 });
  console.log(`captured ${area}`);
}
if (!only || only.has(TV)) {
  // The TV takes its look from the screen's own Theme setting, so each look gets its own screen.
  for (const theme of ["light", "dark"]) {
    const url = await provisionTv(theme);
    const tv = await (await browser.newContext()).newPage();
    await tv.goto(url.startsWith("http") ? url : `${BASE}${url}`);
    await shoot(tv, TV, theme, { width: 1920, height: 1080 });
  }
  console.log(`captured ${TV}`);
}
await browser.close();
