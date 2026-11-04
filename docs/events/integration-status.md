# Events integration closure ledger

GF4, `lane/events-g2`, 2026-10-18. The six EV2/EV3 handoffs are reconciled in this
worktree. This is authored integration, without PostgreSQL, storage or browser
acceptance. **Keep all five programme capabilities and per-event hackathon config
off.** Account Saved details and UI delight controls also default off. Generated
OpenAPI/client files and the catalogue digest remain unchanged.

Paths below are relative to `backend/apps/`; test paths are relative to `backend/`.
The local GF4 handoff supplies exact changed-file and combined rerun manifests.

| Item | Integrated source | Runtime verification |
| --- | --- | --- |
| Prepared admission/forms | `events/contracts/admission_registration.py`, `programme/prepared_forms.py`, `programme/admission_forms.py`, `programme/role_forms.py`, canonical registration/invite bridge | `tests/events/programme/integration/test_gf4_prepared_admission.py`, `test_gf4_registration_closure.py`, admission/contracts/teams suites |
| Source/key/account boundary | `services_write_boundary.py`, `programme_locks.py`, `credentials/boundary.py`, programme/C/D commands and `encryption/preparation.py` | Actual freeze, key rotation, account erasure and last-seat races; no key provisioning under Event locks |
| Private registration/project JSON | `models_registration.py`, `submissions/pii.py`, encrypted TEXT mappings and scoped maintenance commands | Migrations/backfill/strict-read rollout, all A/C/F/P subjects, immutable maintenance and import AAD tests |
| Dates and closure | Canonical event/series date-review and close hooks; durable date notices | G2A date lifecycle and P/C subject-date/reopen suites |
| Live contributor authority | `contributions/authority.py`, `grant_sources.py`, complete runtime ports and all central authority readers | Grant/discovery/entitlement, issuer/window/track/conflict and imported-inert denials |
| Contributor admission | Explicit purpose/capacity ticket pools, canonical bridge, posting-digest-bound requirement completion and exact overrides | FIFO/last-seat/waiver/payment and stale-definition tests |
| Attendance/feedback | Canonical already-locked scanner writer and feedback's pre-transaction certificate preparation | Credential rotation/revoke/confirm races and existing post-event feedback/API suites |
| Source deletion/erasure | Ordered outer purge discovery, paired presentation clearing, owner draft-source hooks; submitted evidence remains independent | Source/account erasure rollback, permanent fences, freeze and deletion races |
| Uploads/readers | Production B boundary, closed maker-policy adapter, A/C/F/D integrations and opaque gallery stream authorization | Quota/concurrency/storage/scanner/probe faults and old-URL/regrant/HEAD/range/stream races |
| Portable answers/assets | Authenticated typed descriptor remap, target AAD, verified journal publication and dedicated provider accounting | Object-backed portable/raw-dump round trips, target allowance and expired-history tests |
| Recovery/purge | Permanent asset obligations and print receipts; bounded workers and beat-less mirrors; custody reserves keys after graph deletion | Late writes/version/multipart cleanup, purged tenant, frozen/MIGRATED_OUT and quarantine tests |
| Certificate/default designs | C/D eligibility, immutable work proofs, owned seed resources, image renderer and server preview/install | Six certificate/36 badge-stock PDF matrices, correction/revocation and photo/resource races; physical QR scans |
| Read contracts/UI | Organizer team/project indexes, requirements/budget, safe topics/sponsor scopes, released programme sections/options, own organization leave and staff Next up | Mounted schema/routes and complete light/dark/mobile/keyboard/privacy journeys |
| Setup/deployment | Events area excludes five explicit opt-ins; shared Compose anchors forward eleven account/credential settings without generating keys; scanner/UI settings explicit | Setup regression, effective manifests and fresh install/upgrade continuity |

## Separate programmes and external prerequisites

Decisions 34/35 are the separately approved reimbursement/staged-forms programme.
Its finance/core-encryption/migration changes are absent from this Events merge;
six existing editor keys do not implement staged forms. Its integration must land
before claiming the complete combined owner programme. The separate Pages programme
owns shared handles and full maker/org builders; event short links (`/e/<code>`) shipped in release 2 L1
(`events.short_links`, see MODULES.md "Public event surface"). Events sections do not
substitute for those domains.

The five maker-preview dependencies require reachable package-registry installation
and a reviewed lock before real vendor/WASM acceptance. A blocked package download
is not a passing vendor build; metadata and mocked tests prove neither exports nor
parser safety.

## Evidence before enablement

Run the combined GF4 rerun manifest with `./scripts/dev.sh test` in this exact tree,
using disposable PostgreSQL 16, Redis and private storage. Check mounts before trusting
shared-container results. Apply the complete graph; run `makemigrations --check`,
forward/reverse/reapply and expected downgrade refusals, raw SQL backstops, model/field/
User/JSON/object/authority/source/task/audit totality and full resolver/OpenAPI coverage.
Generated artifacts require their separate authorized refresh.

Then execute approved plan section 16, the AO checklist and integrated owner QA with
real browser/vendor/media/provider and physical-print evidence. Syntax/type/jsdom
checks alone do not authorize programme enablement, commit, merge or push.
