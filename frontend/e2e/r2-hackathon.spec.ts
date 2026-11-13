import { expect, test } from "@playwright/test";

import { SEED } from "./helpers";
import {
  type Account, E2E_PHONE, StaffApi, blockThirdParty, memberApi, memberArea, publishedEvent, rowsOf, staffConsole, unique,
} from "./r2";

declare const process: { env: Record<string, string | undefined> };

// #134 flow 3, hackathon / applications.
//  - L21a: a member applies to an event, staff stage and release an offer in a decision batch,
//    and the member accepts the place. Self-contained on the seed_e2e makerspace.
//  - L21b: a judge works through the pairwise round of the showcase hackathon, the round is
//    finalized and finalists advance into the draft round. Needs `seed_showcase` (Tinkerspace) and
//    its shared password in E2E_SHOWCASE_PASSWORD; skipped without it.

type Config = { version: number; enabled: boolean };
type Application = { id: number; version: number; state?: string };
type Batch = { id: number; version: number; state: string };

test.beforeEach(async ({ page }) => { await blockThirdParty(page); });

test("L21a: a member applies, staff release an offer, the member accepts the place", async ({ page, browser, request }) => {
  const staff = await StaffApi.open(request);
  await staff.installModules("events", "membership");
  await staff.setFeatures(["events.applications"], ["events.orders", "events.seat_holds"]);
  const event = await publishedEvent(staff, unique("E2E Studio Residency"), { capacity: 6 }, 10);

  await test.step("staff open applications with a batch review", async () => {
    const config = await staff.get<Config>(`/admin/events/${event.id}/hackathon/`);
    await staff.command(`/admin/events/${event.id}/hackathon/`, config.version, {
      enabled: true, review_mode: "batch", team_mode: "solo", rsvp_days: 3,
      // Batch review needs a rubric: a revision and anchored 1-5 criteria.
      review_rubric: { revision: 1, criteria: [{ key: "impact", label: "Impact", anchors: { 1: "Weak", 2: "Fair", 3: "Good", 4: "Strong", 5: "Outstanding" } }] },
      application_opens_at: new Date(Date.now() - 3_600_000).toISOString(),
      application_closes_at: new Date(Date.now() + 5 * 86_400_000).toISOString(),
      coc_body: "Be kind, share tools, and clean your bench. (E2E code of conduct.)",
    }, "PATCH");
  });

  const applicationPage = `/m/${SEED.slug}/events/${event.public_token}/programme/application`;

  await test.step("member submits an application", async () => {
    await memberArea(page);
    await page.goto(applicationPage);
    await expect(page.getByRole("heading", { name: "Apply to make something together" })).toBeVisible();
    await page.getByLabel("I agree to this code of conduct.").check();
    // The seeded member has no phone on the account; the admission form asks for one.
    await page.getByLabel("Contact phone").fill(E2E_PHONE);
    await page.getByRole("button", { name: "Submit application" }).click();
    await expect(page.getByRole("heading", { name: "Application progress" })).toBeVisible();
  });

  let application: Application | undefined;
  await expect.poll(async () => {
    application = rowsOf(await staff.get<Application[] | { results: Application[] }>(`/admin/events/${event.id}/applications/`))[0];
    return application?.id ?? 0;
  }, { message: "the submitted application reaches the staff list" }).toBeGreaterThan(0);

  await test.step("the staff console lists it for review", async () => {
    const desk = await browser.newContext();
    const deskPage = await desk.newPage();
    await blockThirdParty(deskPage);
    await staffConsole(deskPage, `events?event=${event.id}&eventTab=applications`);
    await expect(deskPage.getByRole("heading", { name: "Hackathon applications" })).toBeVisible();
    await expect(deskPage.getByRole("region", { name: "Decision batch" })).toBeVisible();
    await desk.close();
  });

  await test.step("staff stage an offer in a private batch and release it", async () => {
    // A staff decision with an override code stands in for the reviewer panel, which needs
    // several reviewer accounts the e2e seed does not have.
    const staged = await staff.command<Batch>(`/admin/events/${event.id}/application-decisions/stage/`, 0, {
      decisions: [{
        application_id: application!.id, expected_version: application!.version, outcome: "offer",
        reason_code: "strong_application", review_override_code: "staff_decision",
      }],
    });
    expect(staged.status).toBe(201);
    await staff.command(`/admin/events/${event.id}/application-decisions/release/`, staged.body.version, { batch_id: staged.body.id });
  });

  await test.step("member accepts the offered place", async () => {
    await page.goto(applicationPage);
    await expect(page.getByText("A place is on offer").first()).toBeVisible();
    await page.getByRole("button", { name: "Accept offer" }).click();
    await expect(page.getByText("Your place is confirmed").first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------------------------
const SHOWCASE_PASSWORD = process.env.E2E_SHOWCASE_PASSWORD ?? "";
const SHOWCASE = "tinkerspace";
const showcaseAccount = (username: string): Account => ({
  username, password: SHOWCASE_PASSWORD, email: `${username.replace(/_/g, ".")}@example.org`,
});

type Round = { id: number; key: string; mode: string; state?: string; version: number; allowed_actions: string[] };
type PairwiseState = { version: number; finished: boolean; compared: number; allowed_actions: string[] };
type Advance = { id: number; target_round_id: number; published_at: string | null; current: boolean; finalists: Array<{ title: string }> };

test("L21b: a judge compares projects, the round is finalized and finalists advance", async ({ page, request }) => {
  test.skip(!SHOWCASE_PASSWORD, "Set E2E_SHOWCASE_PASSWORD and run `manage.py seed_showcase --reset --password ...` first.");
  test.setTimeout(180_000);
  const manager = await StaffApi.openFor(request, showcaseAccount("tinker_manager"), SHOWCASE);
  const events = rowsOf(await manager.get<Array<{ id: number; title: string }> | { results: Array<{ id: number; title: string }> }>(
    `/admin/makerspaces/${manager.makerspaceId}/events/?search=${encodeURIComponent("Canal Street Build Weekend")}`));
  const event = events.find((row) => row.title === "Canal Street Build Weekend");
  expect(event, "showcase hackathon missing; reseed with seed_showcase --reset").toBeTruthy();
  const base = `/admin/events/${event!.id}`;
  const rounds = async () => {
    // Pairwise rounds may be listed apart from the scored ones; read both and match by key.
    const list = (body: unknown): Round[] => Array.isArray(body) ? body
      : Array.isArray((body as { results?: Round[] } | null)?.results) ? (body as { results: Round[] }).results : [];
    const all = [
      ...list(await manager.get<unknown>(`${base}/judging-rounds/`)),
      ...list((await manager.call<unknown>("GET", `${base}/pairwise-rounds/`, undefined, false)).body),
    ];
    const byKey = (key: string) => all.find((row) => row.key === key);
    return { finals: byKey("finals")!, grandFinal: byKey("grand-final")! };
  };
  const before = await rounds();
  expect(before.finals, "pairwise round `finals`").toBeTruthy();
  expect(before.grandFinal, "draft round `grand-final`").toBeTruthy();

  await test.step("judge sara_haddad (no comparisons yet) works through her pairwise queue", async () => {
    const judge = await memberApi(request, showcaseAccount("sara_haddad"), manager.makerspaceId);
    const statePath = `${base}/judging-rounds/${before.finals.id}/pairwise/`;
    let state = await judge.get<PairwiseState>(statePath);
    const start = state.compared;
    for (let step = 0; step < 12 && !state.finished; step += 1) {
      if (state.allowed_actions.includes("compare")) {
        await judge.command(`${statePath}compare/`, state.version, { outcome: step % 2 ? "previous" : "current", notes: "" });
      } else if (state.allowed_actions.includes("next")) {
        await judge.command(`${statePath}next/`, state.version);
      } else break;
      state = await judge.get<PairwiseState>(statePath);
    }
    // Already finished on a re-run without a reseed; otherwise at least one comparison landed.
    expect(state.finished || state.compared > start).toBeTruthy();
  });

  await test.step("the manager closes and finalizes the round", async () => {
    let { finals } = await rounds();
    if (finals.allowed_actions.includes("close")) {
      await manager.command(`${base}/judging-rounds/${finals.id}/close/`, finals.version);
      ({ finals } = await rounds());
    }
    if (finals.allowed_actions.includes("finalize")) {
      const plain = await manager.command(`${base}/judging-rounds/${finals.id}/finalize/`, finals.version, {}, "POST", false);
      if (plain.status >= 400) {
        // Three judges on four projects can leave coverage short; record why it is accepted.
        ({ finals } = await rounds());
        await manager.command(`${base}/judging-rounds/${finals.id}/finalize/`, finals.version, {
          coverage_exception_reason: "E2E: showcase field of four projects judged by three judges.",
        });
      }
    }
  });

  const current = async () => rowsOf(await manager.get<Advance[] | { results: Advance[] }>(`${base}/finalists/`)).find((row) => row.current);
  let advance = await current();

  await test.step("the top two advance into the draft round and are published", async () => {
    if (!advance) {
      const { finals, grandFinal } = await rounds();
      const preview = await manager.get<{ fingerprint: string; finalists: Array<{ title: string }> }>(
        `${base}/finalists/preview/?source_round_id=${finals.id}&target_round_id=${grandFinal.id}&selection=top_n&top_n=2`);
      expect(preview.finalists.length).toBeGreaterThanOrEqual(2);
      await manager.command(`${base}/finalists/apply/`, grandFinal.version, {
        source_round_id: finals.id, target_round_id: grandFinal.id, selection: "top_n", top_n: 2, fingerprint: preview.fingerprint,
      });
      advance = await current();
    }
    expect(advance, "a current finalist advance").toBeTruthy();
    if (!advance!.published_at) {
      const { grandFinal } = await rounds();
      await manager.command(`${base}/finalists/publish/`, grandFinal.version, { advance_id: advance!.id });
      advance = await current();
    }
    expect(advance!.published_at).toBeTruthy();
  });

  await test.step("the Finalists panel shows the advanced projects", async () => {
    await staffConsole(page, `events?event=${event!.id}&eventTab=judging`, showcaseAccount("tinker_manager"), SHOWCASE);
    const panel = page.getByRole("region", { name: "Finalists" });
    await expect(panel).toBeVisible({ timeout: 15_000 });
    for (const finalist of advance!.finalists) await expect(panel.getByText(finalist.title).first()).toBeVisible();
  });
});
