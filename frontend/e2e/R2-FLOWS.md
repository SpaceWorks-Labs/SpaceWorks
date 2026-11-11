# Release-2 flow specs (#134)

These specs cover the seven #134 flows that had no end-to-end test before release 2. Borrow/return is
still covered by `request-lifecycle`, `hard-rules` and `offline-handover`. They live with the rest of `frontend/e2e/` in the repository;
they are committed. Run them before relying on them.

Run them with the rest of the suite: start the dev stack from the combined tree, then run
`./scripts/dev.sh e2e`. To run only these specs, use `./scripts/dev.sh e2e r2-`.

## Shared plumbing: `r2.ts`

- **Seeding through the API.** Every spec seeds what it needs on the fresh `seed_e2e` makerspace through
  the staff API. Names are made unique per run with `unique()`. No spec depends on another spec or on
  the run order.
- **Feature switches.** Each spec turns on, and where it matters off, the exact capability keys it
  depends on (`StaffApi.setFeatures`). Module installs are idempotent.
- **Sign-in and the unusual-sign-in code.** `apiSignIn` / `uiSignIn` handle the unusual-sign-in check
  (`accounts/login_risk.py`). Every non-superadmin password sign-in from a device the server does not
  remember gets an emailed 6-digit code.
  - The dev stack uses the console email backend, so the helper reads the code from
    `docker logs spaceworks-backend`.
  - It then remembers the `sw_device` value, so later sign-ins of the same person in the run are not
    challenged again.
  - Override the container name with `E2E_BACKEND_CONTAINER`.
- **Third-party network block.** `blockThirdParty(page)` aborts every browser request that is not to
  localhost, so no flow can reach a provider, CDN or font host.
- **Programme and judging commands.** `StaffApi.command` sends a fresh `operation_id` UUID together with
  the matching `Idempotency-Key` header and the integer `expected_version` that the programme and
  judging write endpoints require.

## The specs

### `r2-booking.spec.ts`: book a room (bookings, L16)

- **What it covers:**
  - A signed-in member requests a slot on `/m/<slug>/bookings?space=<token>` for a room that needs approval.
  - The Space Manager approves it from the Bookings queue.
  - The booking shows under My bookings.
  - A second test takes a room out of service (block mode). The booking API then refuses with
    409 `booking_conflict`, "This room is out of service for that time.", the public form shows its 409
    alert, and nothing is booked. The room is put back in service at the end.
- **Seed:** `seed_e2e` (manager, member with an active membership). The spec creates its own rooms.
- **Switches:** modules `bookings` and `membership`; feature `bookings.room_maintenance`, needed by the
  service-state endpoint.
- **Not covered:**
  - Out of service for a machine. Booking admission only checks room outages.
  - The Repairs-tab dialog that sets service state. The spec uses the API for that step.

### `r2-event-registration.spec.ts`: event registration (events, L6)

- **Test 1:**
  - The member registers on the event page through the inline form. On the first try it fills
    "Contact phone", because the seeded member has no phone.
  - The member opens the ticket page.
  - The desk finds the check-in code (Check-in tab, "Scan online", find by code), confirms attendance,
    and the registration is `attended`.
- **Test 2 (L6):**
  - The member orders a free ticket through the ticket shop (More, Review order, Confirm order).
  - A paid seat ordered through the member API is held with a future `hold_expires_at` and no checkout
    URL, because there is no online rail.
- **Seed:** `seed_e2e`.
- **Switches:**
  - Modules `events` and `membership`.
  - Test 1 turns `events.orders` off; with it on, the ticket shop replaces the form.
  - Test 2 turns on `events.ticket_types`, `events.orders`, `events.seat_holds`, `charges.enabled` and
    `charges.events`, and turns off `payments.events`.
- **Not covered:**
  - The QR camera scan; the spec types the code instead.
  - The venue check-in station.
  - The paid order through the shop UI, which would hand over to checkout.

### `r2-hackathon.spec.ts`: hackathon and applications (L21a, L21b)

- **L21a (self-contained):**
  - Staff open applications in batch-review mode with a code of conduct.
  - The member applies on `/m/<slug>/events/<token>/programme/application`, agreeing to the code of
    conduct.
  - The application appears in the staff console under "Hackathon applications".
  - Staff stage an offer in a private decision batch and release it.
  - The member accepts the place.
  - Switches: modules `events` and `membership`; feature `events.applications` (and `events.orders` off).
- **L21b (showcase):**
  - Judge `sara_haddad`, who has made no comparisons in the showcase seed, works through the pairwise
    round `finals`.
  - The manager closes and finalizes the round. If coverage is short, the manager gives a recorded
    coverage exception.
  - The top 2 advance into the draft round `grand-final` and are published.
  - The Finalists panel in the console lists them.
  - Steps that are already done are skipped, so a re-run without a reseed still passes. A reseed
    exercises everything.
- **Seed:**
  - L21a uses `seed_e2e`.
  - L21b needs `manage.py seed_showcase --reset --password <pw>` (Tinkerspace) and `E2E_SHOWCASE_PASSWORD=<pw>`
    in the Playwright environment. Without it, the test is skipped.
- **Not covered:**
  - The multi-reviewer review panel (stages and reviewer assignment). It needs several reviewer accounts,
    so a staff decision with a `review_override_code` stands in for it.
  - The judge comparisons go through the API, not the pairwise UI.
  - Scored (1 to 5) rounds, prizes and payouts.

### `r2-payment.spec.ts`: payment (L5 ledger, payments rail)

- **Offline:**
  - A priced event registration raises a pending charge with no gateway.
  - Staff click "Mark paid" on the Payments screen and record a Cash receipt with a reference and a
    received date.
  - The API shows `paid_offline` with that settlement.
  - A receipt document is issued and its PDF downloads, both through the API and from the member's
    "Show documents" list.
  - The member row reads "Received … by cash".
- **Online (gateway mocked):**
  - The `payments` module is installed with `payments.enabled` and `payments.events`.
  - Placeholder Razorpay credentials are saved. They are format-checked only and are not secrets; this
    step needs a password re-auth.
  - The member clicks "Generate payment link".
  - The spec answers our own `POST /member/makerspaces/<id>/payments/<pid>/checkout` with a fake
    hosted-page URL and serves that page itself.
  - Coming back with `?checkout=success` settles nothing. The charge stays pending, because only a signed
    provider webhook settles it.
  - At the end the spec turns `payments.events` off again.
- **Seed:** `seed_e2e`.
- **Switches:**
  - `events` and `membership`.
  - `charges.enabled`, `charges.events` and `billing.documents`; `billing.maker_checker` and
    `payments.events` stay off while the charge is raised.
  - The online test also installs `payments`.
- **Not covered:**
  - A real provider round trip. The checkout session is created server-side (Stripe SDK, or a POST to
    `api.razorpay.com`), so it cannot be mocked from the browser. There is no fake provider mode, and a
    webhook only settles a payment that already holds a provider session id, which only a real provider
    call writes.
  - An online settlement would need real test-mode keys, or a backend stub provider. Both are out of scope.

### `r2-refund.spec.ts`: refund through a refund case (L24, L5)

- **What it covers:**
  - A priced event charge is settled in person through the API.
  - The member clicks "Request refund" and the row shows "Refund under review".
  - Staff open the case in Refunds, approve it, and record the cash going back (method, reference,
    returned at).
  - The case is `approved` for the full amount and `refunded_amount` matches.
  - The member sees "Refund approved".
- **Seed:** `seed_e2e`.
- **Switches:** the same as the offline payment test.
- **Not covered:**
  - Online refunds through a provider.
  - Price-drop cases (`charges.price_drop_refunds`).
  - Cancellation-opened `due` cases.
  - Refund policies.

### `r2-shop.spec.ts`: shop (L22)

- **Online order and pickup:**
  - The member adds the item to the basket and clicks "Place order, pay at the desk". The pickup code is
    shown.
  - Staff open the order, take payment (UPI, without handing over), mark it ready, then hand it over
    against the pickup code.
  - The order is `collected`, and the member's order page shows it.
- **Till and cash-up:**
  - Staff open the drawer with a 500.00 float.
  - They sell the item at the till for cash (SKU, then Enter, then Sell).
  - They count 580.00 and close the drawer: "Drawer closed", Balanced, variance 0.
  - If an earlier interrupted run left a drawer open, the spec closes it first.
- **Seed:** `seed_e2e`. The spec creates and restocks its own products.
- **Switches:**
  - Module `shop`.
  - On: `shop.online`, `shop.holds`, `shop.public_stock`, `shop.receipts`, `charges.enabled` and
    `charges.shop`; the till test also needs `shop.cash_up`.
  - Off: `shop.guest_checkout`, `payments.shop` and `billing.maker_checker`.
- **Not covered:**
  - Guest checkout (the email code).
  - Online payment for shop orders.
  - Returns.
  - The two-person cash-up check (`billing.maker_checker`).

### `r2-id-card.spec.ts`: member ID card (L3, GAP3)

- **What it covers:**
  - Public check is turned on before issuing, because the check token is minted at issue time.
  - Staff issue the card from Member cards, on the Issue tab, with a unique printed name.
  - Staff email it from the Cards tab ("Card emailed to …").
  - The print PDF renders.
  - The member uploads a card photo with consent ("Photo uploaded.").
  - My cards shows the card as Valid and links to its check page.
  - `/verify/c/<token>` shows "This card is valid".
  - After a revoke, "Check again" shows "This card is not valid".
  - A card left over from an earlier run is revoked first.
- **Seed:** `seed_e2e`.
- **Switches:** module `membership`, and `email`, which is already in the RECOMMENDED profile.
- **Not covered:**
  - A member-initiated card request with approval. The member card has no request step: staff issue it,
    or it is issued automatically. Request and approve exist only for organisation ID programmes
    (`membership.id_programmes`), which need an organisation that the e2e seed lacks.
  - The photo crop UI does not exist in the frontend.

## Before the test phase runs them

1. **Dev stack and runner.** Bring the dev stack up from `int-stage-r2final` and check that the backend
   container mounts that tree (DEV-WORKFLOW). `./scripts/dev.sh e2e` runs `seed_e2e` and writes
   `.seed.json`; every spec fails fast without it.
2. **The host can read the backend log.** The sign-in helper runs `docker logs spaceworks-backend`, so the
   Docker CLI must be on the PATH of the shell that runs Playwright.
   - The dev stack must keep the console email backend, which is the default. Keep
     `security.login_risk_check` at its default; the helper completes the step-up rather than turning it
     off.
3. **MinIO is reachable from the browser** (`AWS_S3_PUBLIC_ENDPOINT_URL`) for the card photo upload, as it
   already must be for the evidence uploads.
4. **For the L21b test:**
   - Run `docker compose exec backend python manage.py seed_showcase --reset --password <pw>`.
   - Export `E2E_SHOWCASE_PASSWORD=<pw>` for the Playwright run. `dev.sh e2e` passes the environment
     through to `npx playwright test`.
   - Use a throwaway password, never a real one.
5. **The existing specs need refreshing** (TEST-PLAN 6b, "refresh them for the U-B sign-in").
   `helpers.ts` `staffLogin` still fills a "Username" field. The staff console now signs in through the
   shared member panel ("Email" and "Password"), and the first sign-in is challenged with the emailed
   code. `uiSignIn` and `staffConsole` in `r2.ts` show the current way to do it. The new specs do not use
   `staffLogin`.
6. **Expect a first-run selector pass.** The selectors were taken from the combined-tree source at the
   time of writing (roles and accessible names wherever possible), but nothing has been run. These are
   the most likely to need a touch-up on the first run:
   - Booking queue rows are found as `li` by room name.
   - Shop order rows are found by `#<id> ·`.
   - The till's Payment panel landmark role.
   - The L21a member page wording after release ("A place is on offer").
