# Events programme — G1 checkpoint handoff

Worktree: `ev-g`; branch: `lane/events-g`; baseline:
`01ac3decc0d3f32817cbf8956bf8b26cc5d7e7e7`.
Scope: approved plan §15 **Contract checkpoint** and integration sequence **step 1 only**.
Owner decisions 1–33 and §§12/12A–E are preserved in the versioned contract source fixture.
No domain lane, migration, runtime route mounting or capability enablement was implemented.
Nothing was staged or committed.

## Built per plan

| Plan | Delivered |
| --- | --- |
| §4 / §12 | Permission vocabulary/off defaults, command/list/job/error envelopes, replay rules, source/fence/domain lock ordering, model/provider/route manifests |
| §12A / §10A | Form-v2/member-input/canonical/response fixtures; F-owned profile descriptors; three typed age subjects; account key preparation/epoch/deadline signatures and structural schemas |
| §12A.1 / .3 | A/G ticket/contact/quote/opaque-string host-waiver/CoC fixture, ordinary `answers` and `custom_answers` compatibility, v1 branch, invalid/replay/account-contact-wins branches; single-normalization adapter |
| §12A.2 / .3 | Exact token context, member18 with zero memberships or existing domain/vault rows, prefill, virtual draft and first submit; ordinary/ineligible/error branches |
| §12A.4 | Compound emergency-contact schema/raw/canonical/prefill/save defaults/explicit save/nested errors |
| §12B–E | Named route/method inventory, literal shared examples, auth/error/OpenAPI contracts, role-only age, D-only sponsor consent, selected-photo/no-photo and print/public scopes |
| §8 / §9A / §15 | Closed read-purpose vocabulary; model-free upload/range/expiry/stream transport; typed photo/subject/intent/service seams; dormant model/URL barrels |
| §15 / ARTWORK | E/ARTWORK layer/resource/tag/stock seed schemas and dummy examples; 58+12 SVG, 35 twins, 6 certificate and 36 badge-stock render requirements |
| §15 tombstone fix | Explicit `cadence="daily"` fixture; production weekly default and no-mutation assertion preserved |

## Exact adapter/type files

- `backend/apps/events/contracts/__init__.py`
- `backend/apps/events/contracts/subjects.py`
- `backend/apps/events/contracts/providers.py`
- `backend/apps/events/contracts/services.py`
- `backend/apps/events/registration_form_adapter.py`
- `backend/apps/events/models_programme.py`
- `backend/apps/events/urls_programme.py`
- `backend/apps/makerspaces/private_upload_transport.py`
- `backend/apps/makerspaces/resource_grants_services.py` (existing shared lifecycle)
- `frontend/src/features/events/contracts/types.ts`
- `frontend/src/features/events/contracts/parsers.ts`

The DRF-facing form adapter preserves admission members while normalizing exactly one
raw answer spelling, invokes F once, preserves legacy nested errors and binds its internal
result to a typed subject. This protects against discarded answers and revalidating a canonical
snapshot as raw browser input. It is not yet installed in existing registration views/services.

The shared grant lifecycle has an optional, operation-aware `subset_validator` returning
explicit `True`. It sees the existing row for update/revoke and rechecks the inviter at
redemption under authority locks. Authority locks now precede child credential locks.
Inactive/missing creators fail closed. Neither current Events nor Bookings opts in at G1;
their full-manager rule and existing audit writes remain. `can_manage_grants` is unchanged.

The transport has no Django/Events dependency. Subject providers own authorization and
storage clients; range parsing permits one range, expiry takes the shortest finite deadline,
and streaming rechecks policy before storage and before releasing each ≤1 MiB chunk.
Readers must honor the supplied two-second SDK timeout. No download redirect is provided.

## Exact fixture files

All files are under `backend/tests/events/programme/contracts/fixtures/`:

```text
README.md
application-admission-v3.json
contract-schemas-v3.json
contract-source-v3.json
emergency-contact-v2.json
fixture-index-v3.json
form-v2.json
key-preparation-v3.json
migration-leaves-v3.json
model-provider-manifest-v3.json
openapi-v3.json
profile-fields-v3.json
profile-role-age-v3.json
public-url-bootstrap-v3.json
read-purpose-v3.json
routes-v3.json
selected-photo-v3.json
shared-contract-v3.json
template-seed-v2.json
```

The fixture README describes each contract. Frontend tests import the same backend JSON
bytes; the index pins all 17 other JSON fixtures. No generated application schema/client
snapshot or `CATALOG_SCHEMA_SHA256` was edited. The `.gitignore` change exposes only these
checkpoint tests/fixtures, the requested tombstone fixture and the new frontend contract test;
the repository otherwise ignores backend tests. No index/staging operation was performed.

## Model manifest and migration leaves

**No new ORM models or migrations.** `model-provider-manifest-v3.json` publishes 66 planned
model identities with plan field/constraint requirements and provider ownership, including
all three `EventAnswerDerivation` subjects, P account models, E presentation/print subjects,
and the sole D `ParticipantSponsorResumeConsent`. `ParticipantSponsorConsent` is prohibited.
Event asset canonical size is `actual_bytes`; account saved asset size is `size_bytes`.

`migration-leaves-v3.json` records all local app dependency leaves by stdlib AST, including:
Events `0036_event_speakers`; accounts `0037_governance_recovery_context`;
encryption `0007_tenant_import_fence_operation`; makerspaces `0096_enable_existing_presence`;
integrations `0039_bd_r2_notification_media`; operations `0013_stocktake_discipline`;
organizations `0004_organization_is_discoverable`; bookings `0020_p2_bookings`.
Django's migration loader/application still needs validation in G integration.

## Routes

`routes-v3.json` and `openapi-v3.json` publish **203 unique named paths / 347 method entries**.
New routes remain inert. Context is exactly GET/HEAD `events-programme-public-context`;
authentication requires an active member account without a membership prerequisite.
Existing ticket, QR, registration, certificate/artwork and broadcast names are retained.
No member approve/verify-hours alias is introduced. D exclusively owns §12C consent routes.

OpenAPI `x-schema-scope` distinguishes literal shared fixtures from shared envelopes whose
domain fields the owning lanes must supply. These contract artifacts do not claim that
all domain serializers or endpoint authorization implementations already exist. G must
install exact origin/claim/delegated/API-client/source policies before mounting any provider.

## Tests and outcomes

- `python` + `py_compile.compile(..., doraise=True)` over all **14 touched Python files: passed**.
- Stdlib fixture checks: **passed** (unique names/paths/operation IDs, named-plan coverage,
  local schema references, canonical compound equality, HEAD without content, schema keys,
  source leaves, file ceilings and CLAUDE/AGENTS equality).
- `frontend: npx tsc -b`: **passed**.
- `frontend: npx vitest run --config vitest.local-junction.config.ts --configLoader runner src/features/events/contracts/contracts.test.ts`:
  **1 file / 10 tests passed**.
- `git diff --check`: **passed**; staging index is empty.
- **No Docker/Django/pytest execution**, as required by this lane's environment constraint.
- `codex doctor`: configuration/home resolution and required endpoint connectivity failed;
  a separate CLI code-review gate was not available. No independent code-review pass claimed.

New backend tests: `contracts/test_frozen_fixtures.py`, `test_grant_subset_hook.py`,
`test_private_upload_transport.py`, `test_registration_adapter.py`. These include real-DB
grant redemption refusal after policy changes, alongside pure compatibility/fixture tests.
Frontend: `frontend/src/features/events/contracts/contracts.test.ts`.

The LF rerun list is at the requested scratch path:
`scratchpad/ev/G1-rerun-files.txt` (nine actual backend test files, relative to `backend/`).
Run the tombstone file separately under the plan's ten-app tombstone startup profile;
all three patch/run-now/delete parameters are required. The other eight files run normally.

## CROSS-LANE needs

| Owner | Required next work / scheduled point |
| --- | --- |
| A + F + P | Replay admission/bootstrap/emergency bytes through actual serializers/services; F is the sole validator/profile registry, P prepares encrypted derivations/intents before event locks; A owns application answer source. Before G integration step 4. |
| B + P | Implement subject-owned upload clients/lifecycle on `private_upload_transport`; honor exact bytes/timeouts and live policy, no account import of Events. B supplies complete storage model/field/User/object manifests before G step 2. |
| C | Supply entitlement and delegation scope predicates for the opt-in hook, including old-row scope and redemption; no promotion of `can_manage_grants`. Role-only subject integration uses P. Before G steps 2–3. |
| D + B + C | D alone implements consent writer/effective read predicate; C supplies eligibility only, B invalidates on asset replacement/deletion. Replay pre-revocation sponsor URL denial at G step 4. |
| E + ARTWORK | Consume selected-photo/resource/layer/stock schemas; E validates runtime/render policy, ARTWORK supplies actual branded seeds/checksums/geometry. Dummy fixtures contain no real photo/credential. Before G step 4. |
| Every domain lane | Supply literal final ORM fields/FKs/User edges/objects/encryption/portability/uniqueness plus closed domain OpenAPI schemas and provider/consumer tests, preserving frozen shared names/shapes. No lane authors app migrations. Before G steps 2–4. |
| G2 | Install provider imports/URLs, replace raw public-view answer reassignment through the trusted adapter, wire ordinary/collaborative/staff boundaries and all route/retention/source registries; centrally author migrations with gates off. Integration steps 2–4. |

## UNFINISHED — required before integration acceptance

1. **G verification owner, integration step 5:** execute all nine files in
   `G1-rerun-files.txt`; the tombstone file needs its separate actual startup profile.
   This includes JSON Schema validation in `test_frozen_fixtures.py` and the real-DB
   hook regression in `test_grant_subset_hook.py`. Backend correctness is not certified
   by syntax/fixture checks.
2. **Orchestrator/G review owner, before accepting the checkpoint/integration:** perform
   independent review of the exact adapter/type/test/fixture files above. The separate
   CLI review was unavailable here; resolve findings before enabling any feature.
3. The explicitly assigned G2/provider work in CROSS-LANE remains scheduled under the
   approved integration sequence; G1 does not report those domain or runtime tasks complete.

Pre-existing untracked `frontend/src/test/staffActor.ts` was left untouched. No UI was
built in this checkpoint; the final Space Works visual/Impeccable audit remains the
integrated programme's required acceptance gate.
