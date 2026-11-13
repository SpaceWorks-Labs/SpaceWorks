import { spawnSync } from "node:child_process";

import { expect, type APIRequestContext, type APIResponse, type Locator, type Page } from "@playwright/test";

import { API_URL, SEED } from "./helpers";

declare const process: { env: Record<string, string | undefined> };

// Shared plumbing for the release-2 flow specs (#134, see R2-FLOWS.md). Each spec seeds what it
// needs on the fresh `seed_e2e` makerspace through the staff API, with names made unique per run,
// so the specs stay independent of each other and can be re-run against the same seed.

export const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:5100";
const BACKEND_CONTAINER = process.env.E2E_BACKEND_CONTAINER ?? "spaceworks-backend";

export type Account = { username: string; password: string; email: string };
export const MANAGER: Account = { ...SEED.manager, email: `${SEED.manager.username}@e2e.local` };
export const MEMBER: Account = { ...SEED.member, email: `${SEED.member.username}@e2e.local` };

/** A label that is unique to this run, so a re-run never collides with an earlier row. */
export function unique(label: string): string {
  return `${label} ${Date.now().toString(36)}${Math.floor(Math.random() * 1296).toString(36)}`;
}

export function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Local ISO string with offset; the booking and event APIs refuse naive datetimes. */
export function isoIn(hoursFromNow: number, minuteOfHour = 0): string {
  const date = new Date(Date.now() + hoursFromNow * 3_600_000);
  date.setMinutes(minuteOfHour, 0, 0);
  return date.toISOString();
}

/** `datetime-local` input value (local wall time, minutes precision). */
export function localInput(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// ---------------------------------------------------------------------------------------------
// Third-party network guard. The flows must never reach a real provider, CDN or font host: every
// request that is not to the local stack is aborted. A spec that fakes a provider page registers
// its own page.route, which takes precedence over this context route.
export async function blockThirdParty(page: Page) {
  await page.context().route((url) => !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname), (route) => route.abort());
}

// ---------------------------------------------------------------------------------------------
// The unusual-sign-in check (accounts/login_risk.py) emails a 6-digit code to every
// non-superadmin password sign-in from a device the server does not remember. The dev stack
// uses the console email backend, so the code is printed in the backend container's log. The
// suite reads it from there, then remembers the `sw_device` value so later sign-ins of the same
// person (API: X-Device-Trust header; browser: the cookie) are not challenged again.
const deviceTokens = new Map<string, string>();

// Mail is sent by the Celery worker in the dev stack, so its log carries the console email too.
const MAIL_CONTAINERS = [BACKEND_CONTAINER, process.env.E2E_WORKER_CONTAINER ?? "spaceworks-worker"];

function backendLog(since: string): string {
  return MAIL_CONTAINERS.map((container) => {
    const run = spawnSync("docker", ["logs", "--since", since, container], {
      encoding: "utf8", maxBuffer: 64 * 1024 * 1024,
    });
    return [run.stdout ?? "", run.stderr ?? ""].join("\n");
  }).join("\n");
}

function codesFor(log: string, email: string): string[] {
  const codes: string[] = [];
  let at = log.indexOf(`To: ${email}`);
  while (at >= 0) {
    const next = log.indexOf(`To: ${email}`, at + 1);
    const block = log.slice(at, next < 0 ? undefined : next);
    if (/sign-in code|enter this code/.test(block)) {
      const match = block.match(/^\s*(\d{6})\s*$/m);
      if (match) codes.push(match[1]);
    }
    at = next;
  }
  return codes;
}

/** Call BEFORE triggering a sign-in; `code()` then waits for the NEW code mailed to `email`. */
export function watchSignInCode(email: string) {
  // A minute of margin covers clock drift between the host and the Docker VM.
  const since = new Date(Date.now() - 60_000).toISOString();
  const before = codesFor(backendLog(since), email).length;
  return {
    async code(): Promise<string> {
      let latest = "";
      await expect.poll(() => {
        const codes = codesFor(backendLog(since), email);
        latest = codes.length > before ? codes[codes.length - 1] : "";
        return latest;
      }, {
        message: `no sign-in code for ${email} in \`docker logs ${BACKEND_CONTAINER}\` (console email backend expected)`,
        timeout: 20_000,
      }).toMatch(/^\d{6}$/);
      return latest;
    },
  };
}

function rememberDevice(account: Account, response: APIResponse, body: object) {
  const header = response.headersArray().filter((h) => h.name.toLowerCase() === "set-cookie").map((h) => h.value).join("\n");
  const token = (body as { device_trust?: string }).device_trust ?? header.match(/sw_device=([^;\s]+)/)?.[1];
  if (token) deviceTokens.set(account.username, token);
}

/** Bearer token for API setup calls, completing the emailed-code step when it is asked for. */
export async function apiSignIn(request: APIRequestContext, account: Account): Promise<string> {
  const token = deviceTokens.get(account.username);
  const headers: Record<string, string> = token ? { "X-Device-Trust": token } : {};
  const watch = watchSignInCode(account.email);
  const response = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { username: account.username, password: account.password }, headers,
  });
  expect(response.ok(), `login ${account.username}: ${response.status()} ${await response.text()}`).toBeTruthy();
  const body = await response.json() as { access?: string; mfa_required?: boolean; purpose?: string; challenge?: string };
  if (!body.mfa_required) {
    rememberDevice(account, response, body);
    return body.access!;
  }
  expect(body.purpose, "only the emailed unusual-sign-in code can be completed by the suite").toBe("risk");
  const verify = await request.post(`${API_URL}/api/v1/auth/mfa/verify`, {
    data: { challenge: body.challenge, code: await watch.code(), factor: "email_code" }, headers,
  });
  expect(verify.ok(), `sign-in code for ${account.username}: ${verify.status()} ${await verify.text()}`).toBeTruthy();
  const done = await verify.json() as { access: string; device_trust?: string };
  rememberDevice(account, verify, done);
  return done.access;
}

/** Fills the visible sign-in form and submits it, completing the "Check your email" step if asked. */
export async function submitSignIn(page: Page, account: Account) {
  const watch = watchSignInCode(account.email);
  await page.getByLabel("Email", { exact: true }).fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const codeStep = page.getByRole("heading", { name: "Check your email" });
  const wait = page.waitForTimeout(3_000);
  await Promise.race([codeStep.waitFor({ timeout: 3_000 }).catch(() => undefined), wait]);
  if (await codeStep.isVisible()) {
    await page.getByLabel("Emailed code").fill(await watch.code());
    await page.getByRole("button", { name: "Verify" }).click();
  }
  const cookie = (await page.context().cookies()).find((row) => row.name === "sw_device");
  if (cookie) deviceTokens.set(account.username, cookie.value);
}

/**
 * Sign in through the real panel (the staff console and the member area share MemberAuthPanel:
 * "Member sign in", Email, Password, "Sign in"), then the "Check your email" code step if the
 * server asks for it. `signedIn` is what the caller expects to see once it is through.
 */
export async function uiSignIn(page: Page, account: Account, path: string, signedIn: Locator) {
  const token = deviceTokens.get(account.username);
  if (token) await page.context().addCookies([{ name: "sw_device", value: token, url: BASE_URL }]);
  await page.goto(path);
  const heading = page.getByRole("heading", { name: /^(Member sign in|Sign in to the staff console)$/ });
  const opener = page.getByRole("button", { name: /^Sign in to (join|your account)$/ });
  await expect(heading.or(opener).or(signedIn).first()).toBeVisible({ timeout: 15_000 });
  if (await signedIn.isVisible()) return;
  if (await opener.first().isVisible()) await opener.first().click();
  await expect(heading).toBeVisible();
  const watch = watchSignInCode(account.email);
  await page.getByLabel("Email", { exact: true }).fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const codeStep = page.getByRole("heading", { name: "Check your email" });
  await expect(codeStep.or(signedIn).first()).toBeVisible({ timeout: 20_000 });
  if (await codeStep.isVisible()) {
    await page.getByLabel("Emailed code").fill(await watch.code());
    await page.getByRole("button", { name: "Verify" }).click();
  }
  await expect(signedIn).toBeVisible({ timeout: 20_000 });
  const cookie = (await page.context().cookies()).find((row) => row.name === "sw_device");
  if (cookie) deviceTokens.set(account.username, cookie.value);
}

/**
 * Staff console at `/m/<slug>/admin/<tab>` (tab may carry a query string), signed in as the
 * seeded Space Manager by default. The console shell carries `data-app-shell` once signed in.
 */
export async function staffConsole(page: Page, tab = "", account = MANAGER, slug = SEED.slug) {
  const path = `/m/${slug}/admin${tab ? `/${tab}` : ""}`;
  const shell = page.locator("[data-app-shell]");
  await uiSignIn(page, account, path, shell);
  if (!page.url().includes(path)) await page.goto(path);
  await expect(shell).toBeVisible({ timeout: 15_000 });
}

/** Member area at `/m/<slug>/member[/<tab>]`, signed in as `account` (the seeded member by default). */
export async function memberArea(page: Page, tab = "", account = MEMBER, slug = SEED.slug) {
  const path = `/m/${slug}/member${tab ? `/${tab}` : ""}`;
  // The portal's user menu button is named after the signed-in username.
  const userMenu = page.getByRole("button", { name: new RegExp(escapeRegExp(account.username)) }).first();
  await uiSignIn(page, account, `/m/${slug}/member`, userMenu);
  if (tab) await page.goto(path);
}

// ---------------------------------------------------------------------------------------------
// Staff API (Bearer). Paths are relative to /api/v1.
type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export class StaffApi {
  constructor(readonly request: APIRequestContext, readonly token: string, readonly makerspaceId: number) {}

  /** The seeded Space Manager on the seed_e2e makerspace. */
  static async open(request: APIRequestContext, account = MANAGER): Promise<StaffApi> {
    expect(SEED.makerspaceId, "frontend/e2e/.seed.json is missing; run ./scripts/dev.sh e2e").toBeTruthy();
    return new StaffApi(request, await apiSignIn(request, account), SEED.makerspaceId);
  }

  /** Any staff account on the makerspace with this slug (the showcase uses `tinkerspace`). */
  static async openFor(request: APIRequestContext, account: Account, slug: string): Promise<StaffApi> {
    const token = await apiSignIn(request, account);
    const probe = new StaffApi(request, token, 0);
    const spaces = rowsOf(await probe.get<Array<{ id: number; slug: string }> | { results: Array<{ id: number; slug: string }> }>(
      `/admin/makerspaces?search=${encodeURIComponent(slug)}`));
    const space = spaces.find((row) => row.slug === slug);
    expect(space, `makerspace ${slug} is not visible to ${account.username}`).toBeTruthy();
    return new StaffApi(request, token, space!.id);
  }

  async call<T = unknown>(method: Method, path: string, data?: unknown, ok = true, extra: Record<string, string> = {}): Promise<{ status: number; body: T }> {
    const response = await this.request.fetch(`${API_URL}/api/v1${path}`, {
      method, headers: { Authorization: `Bearer ${this.token}`, ...extra }, data,
    });
    const text = await response.text();
    if (ok) expect(response.ok(), `${method} ${path} -> ${response.status()} ${text}`).toBeTruthy();
    let body: unknown = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
    return { status: response.status(), body: body as T };
  }

  async get<T>(path: string) { return (await this.call<T>("GET", path)).body; }
  async post<T>(path: string, data: unknown = {}) { return (await this.call<T>("POST", path, data)).body; }
  async patch<T>(path: string, data: unknown) { return (await this.call<T>("PATCH", path, data)).body; }
  async put<T>(path: string, data: unknown) { return (await this.call<T>("PUT", path, data)).body; }

  /**
   * Programme and judging commands (events/hackathons, events/judging): the body carries a fresh
   * `operation_id` UUID that must equal the `Idempotency-Key` header, plus the integer
   * `expected_version` of the row the command acts on.
   */
  async command<T>(path: string, expectedVersion: number, data: Record<string, unknown> = {}, method: Method = "POST", ok = true) {
    const operationId = crypto.randomUUID();
    return this.call<T>(method, path, { ...data, operation_id: operationId, expected_version: expectedVersion }, ok,
      { "Idempotency-Key": operationId });
  }

  /** Idempotent: an installed module is simply not listed in `installed`. */
  async installModules(...keys: string[]) {
    for (const key of keys) await this.post(`/admin/makerspace/${this.makerspaceId}/modules/install`, { key });
  }

  async features(): Promise<string[]> {
    return (await this.get<{ enabled_features: string[] }>(`/admin/makerspaces/${this.makerspaceId}`)).enabled_features;
  }

  /**
   * Sets capability keys on or off. `enabled_features` is replaced wholesale by the PATCH, so the
   * current list is read first. Installing a module does not re-add its default features, and the
   * RECOMMENDED profile seed_e2e applies pruned every feature whose module was missing then. Each
   * spec states the switches it depends on, so the specs do not depend on their run order.
   */
  async setFeatures(on: string[], off: string[] = []) {
    const current = await this.features();
    const wanted = [...new Set([...current.filter((key) => !off.includes(key)), ...on])];
    const changed = wanted.length !== current.length || wanted.some((key) => !current.includes(key));
    if (changed) await this.patch(`/admin/makerspaces/${this.makerspaceId}`, { enabled_features: wanted });
  }

  async enableFeatures(...keys: string[]) { await this.setFeatures(keys); }

  /** `id` is the membership id, `user.id` the account id. */
  async membershipOf(account = MEMBER): Promise<MembershipRow> {
    const rows = rowsOf(await this.get<MembershipRow[] | { results: MembershipRow[] }>(`/admin/makerspaces/${this.makerspaceId}/memberships`));
    const row = rows.find((item) => item.user?.username === account.username || item.user?.email === account.email);
    expect(row, `membership for ${account.username} not found`).toBeTruthy();
    return row!;
  }

  /** Re-confirms the password, which credential changes (payment settings) require. */
  async reauth(account = MANAGER) {
    await this.post("/auth/reauth", { password: account.password });
  }
}

export type MembershipRow = { id: number; status: string; user: { id: number; username: string; email: string; display_name: string } };

/** A member-side Bearer session for API reads and setup the flow under test does not cover. */
export async function memberApi(request: APIRequestContext, account = MEMBER, makerspaceId = SEED.makerspaceId): Promise<StaffApi> {
  return new StaffApi(request, await apiSignIn(request, account), makerspaceId);
}

/** Pages are DRF-paginated (`{count, results}`) or plain lists, depending on the endpoint. */
export function rowsOf<T>(body: T[] | { results: T[] }): T[] {
  return Array.isArray(body) ? body : body.results;
}

// ---------------------------------------------------------------------------------------------
// Fixtures shared by more than one flow.

export type EventRow = { id: number; title: string; public_token: string; status: string };

/** A public event, published, starting `daysAhead` days from now. */
export async function publishedEvent(staff: StaffApi, title: string, extra: Record<string, unknown> = {}, daysAhead = 5): Promise<EventRow> {
  const startsAt = isoIn(daysAhead * 24, 0);
  const event = await staff.post<EventRow>(`/admin/makerspaces/${staff.makerspaceId}/events/`, {
    title, description: "Seeded by the release-2 e2e flows.", starts_at: startsAt,
    ends_at: new Date(new Date(startsAt).getTime() + 2 * 3_600_000).toISOString(),
    is_public: true, capacity: 20, ...extra,
  });
  await staff.post(`/admin/events/${event.id}/publish/`, {});
  // The staff row no longer carries the public token; the public listing does.
  let publicToken = event.public_token;
  if (!publicToken) {
    const listed = rowsOf(await staff.get<EventRow[] | { results: EventRow[] }>(`/public/${SEED.slug}/events/`));
    publicToken = listed.find((row) => row.title === title)?.public_token as string;
    expect(publicToken, `public listing has "${title}"`).toBeTruthy();
  }
  return { ...event, public_token: publicToken, status: "published" };
}

/** The seeded member has no phone on the account; registration forms ask for one. */
export const E2E_PHONE = "+15550100123";

/** Registers the member for an event through the public API (setup, not the flow under test). */
export async function registerByApi(member: StaffApi, event: EventRow) {
  const path = `/public/${SEED.slug}/events/${event.public_token}/register/`;
  let result = await member.call<{ status: string }>("POST", path, { website: "" }, false);
  if (result.status === 400 && JSON.stringify(result.body).includes("phone")) {
    result = await member.call<{ status: string }>("POST", path, { website: "", phone: E2E_PHONE }, false);
  }
  expect(result.status, `register -> ${result.status} ${JSON.stringify(result.body)}`).toBe(201);
  return result.body;
}

export type MemberPayment = {
  id: number; subject_type: string; subject_label: string; status: string; amount: string; currency: string;
  online_payment_available?: boolean; checkout_url?: string | null; refund_case?: { id: number; status: string } | null;
};

/** The member's charge for one event registration (newest first when the label is ambiguous). */
export async function memberChargeFor(member: StaffApi, title: string): Promise<MemberPayment> {
  let found: MemberPayment | undefined;
  await expect.poll(async () => {
    const rows = rowsOf(await member.get<MemberPayment[] | { results: MemberPayment[] }>(`/member/makerspaces/${member.makerspaceId}/payments`));
    const forEvents = rows.filter((row) => row.subject_type === "event_registration").sort((a, b) => b.id - a.id);
    found = forEvents.find((row) => row.subject_label.includes(title)) ?? forEvents[0];
    return found?.id ?? 0;
  }, { message: `no event_registration charge for ${title}` }).toBeGreaterThan(0);
  return found!;
}

/** A priced, published event the member is registered for, with its pending charge. */
export async function pendingEventCharge(staff: StaffApi, member: StaffApi, label: string, amount = "15.00") {
  await staff.installModules("events", "membership");
  // The online rail stays off while registering, so the backend never reaches out to a provider.
  await staff.setFeatures(["charges.enabled", "charges.events", "billing.documents"], ["billing.maker_checker", "payments.events"]);
  const event = await publishedEvent(staff, unique(label), { payment_amount: amount });
  await registerByApi(member, event);
  const charge = await memberChargeFor(member, event.title);
  expect(charge.status).toBe("pending");
  return { event, charge };
}
