# Phase 2 n-hw implementation report

Branch: `lane/p2-n-hw`, worktree `p2-n-hw`, integration base `9cc3c9cc`.

The domain adapters and lane tests are implemented. **This is an integration
handoff, not a claim that every coverage row is TRUE on this isolated tree.** The
shared transport/policy changes below are required before the coverage table can
be signed off. Frozen files, frontend files and integrator-owned documentation
were not edited. Nothing was staged, committed, merged or pushed.

## Behavior

- Hardware lifecycle transitions create explicit owner and staff envelopes through
  `notification_outbox.emit()` inside their domain transaction. Requester content
  never becomes a staff-room body. Account-only owners remain supported; the
  anonymous-request system principal is never a personal recipient.
- The legacy and policy-ladder return reminders retain stream `hardware`, event
  `return_reminder`, mandatory email and immediate timing. Selected personal chat
  accompanies mandatory email. Escalations are staff-only. Durable scheduling is
  distinguished from provider acknowledgement; no adapter fabricates delivery counts.
- Machine jobs emit submitted/accepted/rejected/started/completed/failed/collected
  notices for printers and generic types. Reprint creation now emits `reprinted`.
  Envelope creation moved out of `on_commit`; enqueue and provider I/O still wait
  until commit. Source checks reload ownership, status/revision, sender authority
  and recipient machine-type authority on every attempt.
- Certification grant/revoke notices include the affected owner. Expiring/expired
  notices stay personal; the daily staff summary re-renders live counts. Staff
  notices carry machine/type scope.
- Reorder, consumable/procurement and maintenance adapters retain separate staff
  sources, scopes and bodies. The automatic consumable low-stock call site is wired.
  Maintenance and procurement's other entry points need the two barrel edits below.
- Watches reuse the existing `InventoryWatch`. Subscription requires an active
  member and an out-of-stock public item with visible availability. Hidden
  availability is refused. A zero-to-positive availability transition latches the
  watch; its reminder transaction persists one personal intent and closes it.
  Unsubscribe, rearm, loss of visibility, stock depletion or revoked membership
  invalidate queued delivery. No count, borrower detail or room delivery is added.
- Anonymous verified-contact email keeps an email-only, source-validated path;
  it never creates an envelope addressed to the shared anonymous principal.

## Files changed

All paths below are relative to the repository root.

New production files:

```text
backend/apps/hardware_requests/notifications_p2.py
backend/apps/hardware_requests/notifications_p2_contact.py
backend/apps/hardware_requests/notifications_p2_email.py
backend/apps/hardware_requests/notifications_p2_reminders.py
backend/apps/hardware_requests/notifications_p2_reports.py
backend/apps/hardware_requests/notifications_p2_requests.py
backend/apps/hardware_requests/notifications_p2_rooms.py
backend/apps/inventory/notifications_p2.py
backend/apps/inventory/migrations/0015_watch_pending_index.py
backend/apps/machines/notifications_p2_certifications.py
backend/apps/machines/notifications_p2_maintenance.py
backend/apps/machines/notifications_p2_service.py
backend/apps/machines/notifications_p2_stock.py
```

Edited production files:

```text
backend/apps/hardware_requests/apps.py
backend/apps/hardware_requests/loan_reminder_notifications.py
backend/apps/hardware_requests/loan_reminders.py
backend/apps/hardware_requests/notifications.py
backend/apps/hardware_requests/self_checkout_returns.py
backend/apps/hardware_requests/services_return_reminders.py
backend/apps/inventory/apps.py
backend/apps/inventory/availability_stock.py
backend/apps/inventory/models_watch.py
backend/apps/inventory/notify_me.py
backend/apps/inventory/views_watch.py
backend/apps/machines/apps.py
backend/apps/machines/low_stock.py
backend/apps/machines/notifications_certifications.py
backend/apps/machines/reminders_certification_digest.py
backend/apps/machines/service_emails.py
backend/apps/machines/service_printing_emails.py
backend/apps/machines/service_workflow_actions.py
backend/apps/machines/service_workflow_helpers.py
```

New tests (gitignored, intentionally unstaged):

```text
backend/tests/p2_n_hw/__init__.py
backend/tests/p2_n_hw/conftest.py
backend/tests/p2_n_hw/test_hardware.py
backend/tests/p2_n_hw/test_service.py
backend/tests/p2_n_hw/test_watch.py
backend/tests/p2_n_hw/test_certifications_maintenance.py
backend/tests/p2_n_hw/test_stock_reports_charges.py
```

This report is the only added documentation file.

## Routes / APIs

No routes or request/response fields added.

The existing watch route remains:

| Method | Path | Fields / behavior |
|---|---|---|
| POST | `/api/v1/public/{makerspace_slug}/inventory/{pk}/watch/` | Empty object only; returns `{subscribed: true}`. Now refuses already available items and hidden availability with 400. Existing authenticated member/tenant/throttle guards remain. |
| DELETE | Same path | No fields; 204. |

The watch POST's `extend_schema` description documents the tightened eligibility.
No new callback, webhook, claim route, CSRF exemption or task was added.

## Models / migrations / registries

No new model or field. Existing `InventoryWatch` fields and unique product/user
constraint are unchanged. Migration `inventory/0015_watch_pending_index.py` follows
the actual leaf `0014_public_terms_and_watch` and adds `inv_watch_pending_idx` on
`(makerspace, ready_at)` where `notified_at IS NULL`.

Query-free `AppConfig.ready()` registrations add these `NotificationSource` keys:

```text
hardware.request
hardware.charge
hardware.loan_reminder
hardware.problem_report
inventory.threshold
inventory.watch
machines.service
machines.certification
machines.certification_summary
machines.maintenance
machines.procurement
```

`hardware.verified_contact` additionally registers with the existing email
`DeliverySource` registry. No provider registration is needed in this lane.

The watch already has classification (`classification_wp4.py`), User reference
classification (`references_core.py`), tenant field catalog (`catalog_wp4.py`),
authority disposition (`authority_wp4.py`) and DROP projection (`projection_wp4.py`).
The new index needs no field/model/export/PII registry additions. Envelopes and
endpoint bindings keep Phase 1a's encryption and DROP-on-import treatment. The
portable catalog digest was not changed.

## Integrator requests

Phase 3 status (2026-10-17), verified in the merged code; no runtime test claim:

1. **DONE:** `maintenance/notifications.py` explicitly re-exports
   `machines.notifications_p2_maintenance.notify` as `notify_maintenance_lifecycle`.
   Schedule/log, calendar and usage-meter callers reach the source-backed adapter.
2. **DONE:** `procurement/notifications.py` explicitly re-exports
   `machines.notifications_p2_stock.notify` as `notify_stock`; automatic low-stock and
   procurement-received paths now reach the adapter.
3. **DONE:** `integrations/dispatch_channels_delivery._deliver_notification` calls
   `hardware_requests.notifications_p2_rooms.eligible_room` before timing/provider delivery.
   Equipment room queuing no longer waits for an installation marker.
4. **OPEN:** shared machine-module eligibility and equipment email policy/render hooks below.
   `hardware.owner_mailbox` separately preserves the same owner's verified contact email.
5. **DONE:** hardware charge summaries are staff-only. The ledger's `payments.ledger`
   charge_raised intent owns the single borrower notice; the earlier proposed shared hardware
   owner key is superseded, not an additional dedup contract.
6. **DONE:** `notification_catalog.FEATURE_EVENTS[HARDWARE_REQUESTS]` includes
   `problem_report.filed` for editor/provider bindings; no new feature/module key.
7. Regenerate OpenAPI and the frontend client on the Django host after integration
   (the only lane schema wording change is watch eligibility). Update
   `SOURCE-MAP.md` with the adapter/source modules, `INVARIANTS.md` with transactional
   equipment sources/live room checks, and `PROJECT-HISTORY.md` with the merged
   behavior and actual test results. No README/MODULES change is required.
8. Run the lane tests and existing hardware/machine/email/notification suites.
   Existing implementation-level tests such as
   `test_notification_payload_adapters_w0.py` patch `notify_lifecycle` and inspect
   `LifecyclePayload`; those hardware/printing cases must be migrated to inspect
   persisted envelopes and explicit recipients. `test_inventory_notify_me.py`
   likewise patches the retired bridge and expects subscriptions to hidden/already
   available items; reconcile those cases with the out-of-stock/public-availability
   requirement. These older test files are outside this lane's allowed test folder.

## Contract change requests

No frozen signature or field was changed. These are concrete deficiencies in the
shared seams that prevent signing off all rows on this tree:

1. **Generic machine-service module eligibility.** The frozen
   `notification_resolution.eligible()` calls `feature_available(..., "printing")`
   for every service envelope. That refuses generic jobs when `machine_service`
   is enabled and `printing` is off. Keep category `printing` for preference
   compatibility, but after successful `source_eligible`, let source kind
   `machines.service` supply domain-module eligibility. Its live source already
   requires `machines` + `machine_service`, and additionally `printing` for actual
   built-in printer types. Other source kinds retain the existing feature gate.
   The room hook already handles this distinction.
2. **Legacy email policy at channel resolution.** In
   `notification_resolution.email_eligible()`, combine the existing rules with
   `notifications_p2_email.allowed(envelope)`: `False` refuses email, `None` leaves
   another lane untouched. The current resolver otherwise ignores requester
   `EmailNotificationMute` (including hardware's `request_accepted` etc. key mapping)
   and the existing verified-contact gate. Do not apply this email-only policy to
   selected chat. Mandatory reminders and closed-with-issue keep their exceptions.
   Import this callback at module level as `EQUIPMENT_EMAIL_POLICY` and use that
   alias for the check. It is also an installation marker: until wired, sources
   with a blocking legacy email rule refuse the whole personal intent, preventing
   an unwanted email. After wiring, chosen chat can continue while email is refused.
3. **Existing proof of the owner's mailbox.** The same resolver currently insists
   on `User.email_verified_at`; `hardware.owner_mailbox` separately preserves reminders
   for an equal, verified loan contact. The shared-resolver request remains: accept `user.email_verified_at OR
   notifications_p2_email.proven_address(envelope)` while retaining nonempty address,
   suppression and module checks. The hook only recognizes proof of the SAME
   explicitly owned account mailbox. A legacy verified contact differing from the
   account's mailbox cannot be represented by the current personal email transport;
   preserve such rows on a separately source-validated email-only path if the
   integrator needs that compatibility. Never infer a personal endpoint from it.
4. **Email-specific rendering.** Personal envelope bodies intentionally contain
   authenticated navigation and no public tracking bearer. To preserve existing
   printer EMAIL tracking content, call
   `notifications_p2_email.render_email(envelope, rendered)` immediately before
   builtin email dispatch in `notification_builtin.send_builtin`, and in
   `notification_email_source.prepare` on email retry. It rebuilds existing printer
   templates at the transport boundary; chat/in-app/push must retain safe envelope
   content. New failed/collected/reprinted owner messages retain generic content.

These changes do not require new envelope/endpoint fields or provider signatures.

## Validation and deferred work

No Docker, Django, pytest, migration execution, network delivery or runtime review
was run, per lane instructions. Local Python compilation/AST checks and the
300-line production-file check passed; `git diff --check` passed. Test files are
present on disk despite their expected gitignore status.

The five test modules cover each converted equipment coverage family, parameterized
hardware/machine transitions, explicit audiences and selected channels, mandatory
email with chat, suppression, dedup, rollback, live scope narrowing, room-source
invalidation and the watch lifecycle. They use an explicitly registered fake
personal provider and stub builtin delivery/enqueue; no real provider is contacted.
Room adapter tests install the guard marker explicitly; the separate missing-guard
test verifies that the isolated lane refuses to queue unguarded room messages.

Claude must run at least `./scripts/dev.sh test tests/p2_n_hw
tests/notifications_contract tests/machines tests/maintenance
tests/hardware_requests/test_loan_reminder_ladder.py tests/test_return_reminders.py
tests/test_inventory_notify_me.py tests/test_notification_fanout.py
tests/test_email_notification_mutes.py`, then the required integration/module matrix
and full baseline checks. Do not treat static checks as a runtime test pass.

Deferred to integration: the explicit shared edits above, runtime verification,
existing-test migration, OpenAPI generation and the final combined coverage audit.
No unrelated feature work is deferred by this lane.

## Claude verification changes (2026-10-17)

- **Room guard wired** (integrator request 3 done): `integrations/dispatch_channels_delivery._deliver_notification`
  now calls `hardware_requests.notifications_p2_rooms.eligible_room` (lazy import) after the module/config
  gates and before timing/provider delivery; stale equipment rows are SKIPPED with
  `equipment_source_no_longer_eligible`. The fail-closed marker in `queue_rooms` is removed, so hardware,
  machine-service and stock staff room alerts are no longer silently disabled on this tree.
- **Hardware room text restored**: rooms keep the existing staff-authored text (`_build_submitted_request_message`
  with contact, items and the "Contact NOT verified" warning; the per-event one-liners otherwise). The
  requester's own body still never reaches a room.
- **Loan charge dedup** (integrator request 5 replaced): `notify_charge` is now staff-summary only. The owner's
  single `charge_raised` notice belongs to the ledger, because `payments.services.create_payment` already
  raises it for every loan charge (lane n-other's `payments.ledger` source). No second owner intent.
- **Mandatory reminder mail for owners without `email_verified_at`**: new `hardware.owner_mailbox` email-only
  `DeliverySource` (`notifications_p2_contact.notify_owner/prepare_owner`). When the resolver cannot email the
  owner only because `email_verified_at` is empty but the request's verified contact snapshot proves the SAME
  mailbox (the pre-Phase-2 rule), the reminder/lifecycle mail is still sent once; it re-checks at send/retry
  and stops as soon as the envelope itself can email. Contract change request 3 remains the proper fix.
- **Savepoint fail-safe**: equipment adapters use `hardware_requests.notifications_p2.safe_adapter`, which wraps
  the adapter in `transaction.atomic()` so a failed query inside the domain transaction cannot poison it.
- `loan_reminders.dispatch_reminder` only raises for an adapter failure or failed counts, not for "nobody
  reachable" (restores the previous failure accounting).
