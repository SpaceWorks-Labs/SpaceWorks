# Phase 2 profile backend lane

Implemented in `lane/p2-profile-be`, based on `9cc3c9cc`. No staging or commits.
The frozen profile serializers, predicates, activity engine and source-registration
contract remain unchanged. No frontend or integrator-owned documentation was edited.

## Behaviour

GitHub is a separate calendar (`source: "github"`), never a SpaceWorks activity
family. Its public GET performs cache reads only. The existing daily
`apps.makerspaces.tasks.refresh_github_contributions_task` additionally calls
`profile_github_tasks.refresh_public_calendars`; neither a new Celery task nor a
new scheduler entry is necessary. It uses the existing `GITHUB_API_TOKEN` setting.
An unset token makes no request and hides any cached calendar behind an empty
`days` array. A cache miss, expiry or provider failure also returns empty days.
The existing scalar GitHub total's behaviour is unchanged.

The fetch requests GraphQL `contributionsCollection.contributionCalendar.weeks.
contributionDays { date contributionCount }`, with an eight-second timeout and a
128 KiB response limit. Partial GraphQL errors and malformed dates, counts,
duplicate dates and oversized calendars are refused. Logs contain event codes,
never handles, credentials, provider responses or exception messages.

Cache keys hash the claim ID, handle, handle change timestamp, selected profile ID,
profile update timestamp, GitHub username and existing profile cache generation.
The worker reloads current predicates/generation after I/O. A raced worker can
only write its old key, including a change occurring after that final check;
new readers compute a different key. This also covers username changes back to
the original spelling. Bodies live for 25 hours, refresh becomes due after 23
hours (before the existing daily schedule), failure backs off for one hour, and
a 60-second fetch lease suppresses overlapping workers. Withdrawal and graph
consent are checked live before any cache body is read. Existing profile updates
can conservatively invalidate this cache too; it repopulates on the next daily
refresh. GitHub dates are preserved as returned, separately from SpaceWorks'
makerspace-local buckets.

Three additional sources register at app startup with no database queries:

| Family | Module | Consent | Derived records |
|---|---|---|---|
| speaking | events | show_speaking | Lazy `speaker_history.contributions_for(user, makerspace)`; public PUBLISHED events, past session milestone, live host/module |
| loans | request_workflow | show_loans | Explicit requester + tenant; reviewed request issue/return, or physical direct/self-checkout loan checkout/return |
| bookings | bookings | show_bookings | Explicit member + resource tenant; current arrival and/or past completed booking end |

The engine still owns the graph master switch, individual consent, module gates,
120-day window, makerspace timezone and record/day deduplication. Source identities
are model-qualified. A direct/self-checkout loan's backing HardwareRequest is
excluded from reviewed requests, so the same handover is not counted twice.
Multiple milestones for the same loan/booking/event on one local day count once.
ReturnEvent timestamps supply actual partial returns, rather than guessed
`updated_at` timestamps. Live state/ownership is queried on every read: reversing
an arrival, correcting status, unlinking a speaker or purging data changes counts
immediately. No title, link, source ID, remark or exact timestamp is exposed in the
graph response.

The parallel speaker lane owns account linkage and provenance inside
`contributions_for`; this adapter never infers account identity from names/emails
and makes no assumption about the uncontracted `role` vocabulary. Missing imports
or an unavailable seam (`ImportError` / `AttributeError`) yield no contributions.

The events URL now uses a sibling view and the unchanged frozen event serializer.
ATTENDED still uses `attended_registrations` and hence
`events.member_history.registrations_for_space`. HOSTED is an explicit event
creator, authorized organizer-organization membership (the existing
`organizer_event_q` RBAC predicate), or a live personal/series staff grant with
`edit_details` or `publish_schedule`; a speaker-only grant is not host credit.
Hosted history outside the chosen profile's space also requires durable
registration provenance through that space, not current collaboration. Only
public, started PUBLISHED/COMPLETED events appear. Speaking uses the scoped
speaker seam and the stricter PUBLISHED/past-session rule. Host archival/module
withdrawal hides remote history. `show_events` consents attendance/hosting;
`show_speaking` independently consents speaking. One event appears once, with
badge priority SPOKE > HOSTED > ATTENDED, because the frozen serializer has one
badge field. Event payloads stay in a lazy queryset so PostgreSQL paginates before
serializing a page. Every response uses the frozen public gate, no-store, Origin/Host
variation and public-read throttle.

## Routes / API fields

| Method + path | Request | Response |
|---|---|---|
| GET `/api/v1/public/profiles/<handle>/github` | No body | `{source: "github", days: [{date: "YYYY-MM-DD", count: nonnegative integer}]}` |
| GET `/api/v1/public/profiles/<handle>/events?page=` | Existing page query | Existing `{count, next, previous, results: [{title, starts_at, ends_at, badge, host}]}`; now fills HOSTED and SPOKE |
| GET `/api/v1/public/profiles/<handle>/activity?from=&to=` | Existing bounded dates | Frozen counts-only response, now with consented speaking/loans/bookings families |

GitHub additionally requires `show_activity_graph`, with the same single 404 as
the public profile gate. A retired handle redirects only while the current
profile and graph consent remain eligible. 200, 302, 404 and 429 are documented
through drf-spectacular; authentication is anonymous. No write endpoints added.

## Files changed

New production modules, all under `backend/apps/makerspaces/`:

- `profile_activity_p2.py`
- `profile_github.py`
- `profile_github_fetch.py`
- `profile_github_tasks.py`
- `profile_github_urls.py`
- `profile_github_views.py`
- `profile_history_public.py`
- `profile_history_speaking.py`
- `profile_history_views.py`

Small composition/registry edits:

- `backend/apps/makerspaces/apps.py`: register additional sources.
- `backend/apps/makerspaces/profile_contract_urls.py`: compose GitHub URL sibling
  and switch the existing events URL to its completed sibling view.
- `backend/apps/makerspaces/tasks.py`: compose the calendar sweep into the existing
  daily task, preserving its return shape.
- `backend/apps/apiclients/scope_registry_routes.py`: classify GET/HEAD for
  `public-profile-github` as `public:read` / `public:*`, tenant-token target mode,
  no legacy admission or tenant-app widening, same as existing profile reads.
- `backend/apps/apiclients/scope_registry.py`: resolve that route's target through
  the existing frozen `resolve_public_profile` predicate.
- `backend/apps/accounts/claim_routes_profiles.py`: anonymous GET/HEAD/OPTIONS;
  a claim proof grants no profile authority.
- `backend/apps/tenant_migration/gate_policy_tasks.py`: declare the calendar fanout
  helper, which uses `fanout_tenant_write` for each tenant. The existing task
  declaration/scheduler remain in use. The GET creates no tenant state and needs
  no mutation-gate or CSRF exemption.

New tests (gitignored as requested), under `backend/tests/p2_profile_be/`:
`__init__.py`, `conftest.py`, `test_github.py`, `test_activity.py`,
`test_history.py`, `test_access_tasks.py`. Copy/collect these explicitly during
integration; a normal tracked diff does not include them.

This document: `docs/p2-profile-be.md`.

## Models / migrations / retention

None. All history is query-derived and GitHub data is a bounded, disposable cache.
No new User FKs, PII fields, object keys, export datasets, subject selectors,
tenant-import dispositions or encryption registrations. No catalog schema pin
was changed. Reads/cache refreshes do not mutate domain state, so they create no
domain audit entries.

## Validation

Python AST syntax and file-size checks and `git diff --check` passed locally.
The new suite has 37 test functions, 67 statically enumerated parameterized cases.
Docker, Django, pytest and schema generation are deliberately not run in
this lane. Claude must run the new tests and relevant frozen profile, scheduler,
source-gate, route-registry and module-variation suites on the integrated tree.
The standalone `codex doctor` check reported unavailable local config and provider
connectivity; no standalone CLI review result is claimed.

## Integrator requests

1. Regenerate OpenAPI on the Django host with
   `python manage.py spectacular --format openapi-json --file ../frontend/openapi-schema.json`,
   then run `npm run generate:api` from `frontend/`. This lane cannot edit frontend
   artifacts or run Django. The route already has complete serializer/schema decorators.
2. Update `docs/INVARIANTS.md` in the maker-profile section with the separate
   calendar behaviour above: cache-only public reads, per-generation keys, live
   graph consent, empty on calendar failure, background refresh through the
   existing daily GitHub task. Keep the legacy scalar total's last-known-value
   rule distinct. Also record model-qualified loan identity/dedup and the event
   badge precedence/provenance rules.
3. Add the new profile GitHub/activity/history sibling modules to the makerspaces
   entry in `docs/SOURCE-MAP.md`; add the Phase-2 profile backend completion to
   `docs/PROJECT-HISTORY.md`. No new module key requires MODULES/README edits.
4. Adapt `backend/tests/profiles_contract/test_activity.py`'s
   `test_future_lanes_use_registration_and_never_run_without_consent` to isolate
   its fake speaking source: replace the `_sources` copy with
   `{family: source for family, source in sources._sources.items() if family != "speaking"}`.
   Phase 2 now legitimately registers speaking during startup, so its old fake
   registration otherwise trips the intentional duplicate-source guard. No
   production registration semantics should change.
5. Verify the merged speaker lane's `contributions_for(user, makerspace)` provides
   the promised account linkage/provenance and aware session timestamps. These
   tests use a fake seam because the implementation is in a parallel lane.
6. Collect the ignored lane tests, run the final integrated variation matrix, and
   perform the owner-managed review/QA gates. No commits, merge or push performed.

## Contract change requests

None. The single badge field is respected through documented precedence; the
unchanged serializers/predicates and source registry suffice. The events handler
is composed at the URL barrel without changing the frozen projection functions.

## Deferred

Runtime tests, OpenAPI/generated frontend artifacts, integration documentation,
parallel speaker implementation verification and final integrated review/QA are
left to the named Claude/integrator lanes. No backend feature in this brief is
intentionally deferred.
