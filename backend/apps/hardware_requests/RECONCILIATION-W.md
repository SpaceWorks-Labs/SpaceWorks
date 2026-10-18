# Lane W handoff

Branch: `lane/recon-W`; implementation base `0579b1b3` (wave 1).
Changes are uncommitted and unstaged. No CLI review, Docker, pytest, migration
execution, schema generation or Git mutation was performed.

## Result

- Equipment, booking, event and device adapters reserve canonical envelopes.
  Reviewed scalar messaging projections accompany their source IDs/revisions;
  email contacts, free text, private bodies and bearer URLs are excluded from
  that projection. The helper is `hardware_requests/notification_projection.py`.
- Event lifecycle intents now have deterministic source/revision/audience keys.
  Existing T intents with random keys are reused by source identity across the
  upgrade. Staff in-app/native-push reservations and campaign email reservations
  retain their deliberate legacy skips. No addressed legacy enqueue was added.
- Booking reminder account eligibility and event owner eligibility use core
  `integrations.recipients_owners`, independently of the optional inbox. Campaign
  authoring gates and existing guest/owner compatibility email paths are retained.
- Event lifecycle/delegate/reminder/certificate sources recheck their source ID,
  owner tenant route, current revision and applicable reminder offset. Hardware
  charge summaries require the same tenant's loan and the matching charge kind;
  the ledger still owns the payer's only charge notice and private amounts.
- Maintenance logs recheck the author's operate permission; schedule notices
  recheck management permission. Recipient machine-type scope stays independent.
  Submitted machine-service sources refuse deleted/retired/stub senders.
- Usage attribution requires a live, unrestricted member account, an active
  membership in this tenant, and no retirement/deletion/purge/stub marker. Public
  presence admission also enforces those account boundaries. Expiry notices check
  live account/membership standing as well as module/source revision.
- A's `_end(session, actor, reason, now)` interface is preserved byte-for-byte in
  `presence/services.py`; account-only cleanup with the module off is covered.
- Renewal charging reloads and locks tenant, membership, term, then User. Stale
  callers cannot charge a cancelled/revoked/deleting account or duplicate the
  linked charge/audit. Tracking remains independent of the online rail. Activation
  locks its driving request before User, matching A's lifecycle order.

Bootstrap's quantity/cost/status analytics hooks, deletion-obligation locks,
evidence/QR/remark/audit workflow, device immutable edge sources, watch pending
index/one-shot dispatch, native organizer exclusions and T source adapters were
reviewed and retained. No lane W bootstrap notes remain (none were present).

## Migrations and fields

No migrations, model fields, HTTP routes or serializer fields were added/changed.
Actual migration directories were listed: bookings 0020, events 0036,
hardware_requests 0029, inventory 0016 merge, machines 0029, devices 0004,
presence 0003, maintenance 0003, procurement 0008, makerspaces 0097 after wave 1.
The inventory merge needs no forward: W changes no final model/index state.

Envelope context gains only catalogue-allowlisted scalar template keys, alongside
existing domain metadata. Event reminder context additionally records
`offset_seconds`. Previously queued reminders lacking that proof fail closed;
they are not replayed or assigned an invented current offset.

## Exact requests to other owners

- **C**: review/register the changed source guards in
  `events/notification_sources.py`, `hardware_requests/notifications_p2_requests.py`,
  `machines/{usage_attribution,notifications_p2_service,notifications_p2_maintenance}.py`,
  `presence/{guard,policy,notifications}.py` and the two changed membership services
  in `tenant_migration/authority_guards.py::AUTHORIZATION_SOURCES`, with the
  account-kind/lifecycle fields classified. No source was moved. C alone updates
  the catalog digest. Review the scalar context references against the existing
  envelope JSON telemetry/export policy; no new model or User-FK edge exists.
- **C**: install the supplied `membership_cases.py.txt` as
  `tests/makerspaces/test_reconciliation_w.py` and own any adjustments there. It
  covers rail-free renewal, stale state/idempotency, deletion and concurrent renewal
  writers; additional admission/revoke assertions are listed at its end. W did not
  write C's test directory and cannot run it under this task's instructions.
- **C/R**: complete reviewed scalar projections for C-owned
  `makerspaces/notifications_p2_members.py::{notify_member,notify_request}` and
  `notifications_p2_terms.py::notify_term`. They currently pass only source-control
  metadata into R-owned `operations/notifications_p2.py::fanout`, so approved WA
  BODY variables from O's catalogue are absent. Use the supplied
  `addressed_context(space, feature, event, audience, template_context)` helper per
  audience (or an equivalent core helper), retaining source metadata, account-only
  eligibility and separate staff/requester contexts. Core SMS must not depend on
  inbox installation. R may enrich its own source adapters via the same seam.
- **G/Claude**: transport the ignored delta and membership proposal, run collection,
  tests, migration graph/upgrades/checks and review. Keep M's durable ingress,
  receipt-only conversion and activation checkpoints; this handoff does not
  authorize sending activation or destructive retirement.

## Tests and evidence

New tests live in the owned bookings, events, hardware_requests, machines,
inventory, devices, presence, maintenance and procurement directories. They cover
private projections, transaction rollback, duplicate/old-key intents, source and
recipient mutation, certificate binding, account-only eligibility, native organizer
denial after User reload, attribution, watch dispatch, repeated outage edges,
operator revocation, procurement scope and audited presence cleanup.

The machine dashboard conflict retains T's account-kind factories/denial assertions
plus O's additive `widgets`/`queue_tiles` response shape. The existing device test
now expects its reviewed scalar device ID instead of an empty context.

Ignored artifacts are under
`backend/tests/hardware_requests/_reconciliation_artifacts/`:
`lane_W_handoff.json`, `lane_W_tests_delta.zip`, `static_verification.json`, original
edited-test hashes, and the C-owned membership test proposal. The handoff manifest
lists every implementation/test path and hash, the verified base bundle and exact
verification status. No runtime test success or collected node IDs are claimed.

Suggested changed-area run, after G supplies the activated-cutover shared fixture:
`./scripts/dev.sh test tests/bookings tests/events tests/hardware_requests tests/machines tests/inventory tests/devices tests/presence tests/maintenance tests/procurement tests/makerspaces`

G must also retain/run cross-lane `tests/accounts`, equipment/personal notification
suites (`tests/p2_n_hw`, `tests/p3_wire`, `tests/notifications_contract`), and source
freeze/portability suites with C/P/M's final changes. W did not edit those unowned
directories. DB races, actual imports, provider behavior and schema/migration
consistency remain unexecuted verification, not a passing result.
