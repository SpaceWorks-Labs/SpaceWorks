# Events programme G1 contract v3

Baseline: `integration/all-2026-10-16` at `01ac3decc0d3f32817cbf8956bf8b26cc5d7e7e7`.
Approved plan: `events-PLAN-FINAL.md`, owner decisions 1–33, §§12/12A–E,
§15 contract checkpoint and integration step 1. The original plan SHA and the
binding contract text are preserved in `contract-source-v3.json`.

These are shared fixture bytes for A/B/C/D/E/F/P/ARTWORK. Consumers import these
files directly; do not copy them into separate frontend fixtures. `fixture-index-v3.json`
pins the bytes. A contract change needs coordinated provider/consumer review and
an updated version/index. No fixture registers an app/model/route or enables a feature.

| File | Contract |
| --- | --- |
| `shared-contract-v3.json` | Errors, envelopes, pagination, commands/replay, permission vocabulary, off defaults, lock order |
| `contract-schemas-v3.json` | Structural JSON Schemas for forms, member/admission input, canonical snapshots, three subjects, photos, key metadata, read purposes and seed layers |
| `form-v2.json` | Exact §12A schema/input/derived snapshot and owner response |
| `application-admission-v3.json` | §12A.1/3 ticket, quote, waiver, separate CoC, ordinary answers/custom_answers, v1, replay and invalid branches |
| `public-url-bootstrap-v3.json` | §12A.2/3 token-only member18, no memberships or saved rows, context/prefill/virtual draft/first submit, ordinary/ineligible/error branches |
| `emergency-contact-v2.json` | §12A.4 schema/raw/canonical/false and true save/prefill/nested errors |
| `profile-fields-v3.json` | F-owned standard-key descriptors, types/bounds, sensitive defaults and encryption/normalization requirements |
| `profile-role-age-v3.json` | Three derivation subjects, role-only mentor, lock/date/source/owner rules; computed age never persisted |
| `key-preparation-v3.json` | P preparation/epoch/deadline/binding/readiness and account-only locking contract |
| `selected-photo-v3.json` | E membership selection, no-photo, separate print/public consent, immutable snapshot and source rules |
| `read-purpose-v3.json` | Closed server-selected purposes, bounded streaming, revocation and expiry |
| `template-seed-v2.json` | E/ARTWORK versioned layer/resource/tag contract, certificate/badge examples, six stocks and exact inventory counts |
| `model-provider-manifest-v3.json` | 66 planned model identities, field/constraint specifications, service owners, D-only consent, required final lane manifests and canonical byte fields |
| `migration-leaves-v3.json` | Actual local migration dependency leaves, captured with stdlib AST; no migrations created |
| `routes-v3.json` | 203 unique named paths / 347 method entries, owners, auth, API-client requirements and literal shared examples |
| `openapi-v3.json` | Inert OpenAPI contract fixture with auth/error/binary/Range/header schemas; **not** the generated application snapshot |
| `contract-source-v3.json` | Verbatim binding decisions/contracts/authority/asset/seed/lifecycle/test requirements |
| `fixture-index-v3.json` | SHA-256 and byte counts of all other JSON files |

`x-schema-scope` in OpenAPI distinguishes literal shared examples from the common
envelope extended by lane-owned domain fields. The coarse §12 inventory does not
specify every domain field. Each owning lane must supply its closed serializer
schemas and expanded domain fixtures; common fixtures cannot be used to authorize
unknown domain inputs. G merges those definitions before generating runtime clients.
Existing route names take precedence: certificate template/preview/artwork and
broadcast cancel retain their current names. The plan's explicit `events-programme-admin-roles`
detail example is preserved; its collection is `events-programme-admin-roles-list`.

G1 adapters:

- `apps.events.contracts.{subjects,providers,services}`: ID/value-only protocols.
- `apps.events.registration_form_adapter`: normalize one raw answer spelling,
  invoke F once, preserve admission members and legacy error paths, return an
  in-process subject-bound result. P preparation remains outside event locks.
- `apps.makerspaces.private_upload_transport`: model-free upload signatures,
  range parsing, minimum expiry and reauthorization before each bounded chunk.
- `GrantAdapter.subset_validator`: optional operation-aware callback requiring
  explicit `True`, including redemption and existing-row revoke/update. Default
  full-manager behavior remains; no Events adapter opts in at G1.
- `apps.events.models_programme` and `urls_programme`: dormant explicit barrels.

No HTTP path accepts a trusted form object, locked context, read purpose or prepared
intent from JSON. Providers recheck ownership, exact scope, current fences and
authority; descriptive flags and the Python types confer no authority.

See `docs/events-programme-G1-handoff.md` for verification, exact rerun files,
cross-lane work and unfinished gates. Backend tests have not been executed in G1.

## Contract v4 (G-final part 4)

v3 bytes stay frozen. `fixture-index-v4.json` pins only the files added afterwards:
`routes-v4.json` is a delta whose rows replace same-named v3/gf1 rows (organizer team and
submission reads; help-type detail without the retired POST), and `public-url-bootstrap-v4.json`
adds the optional emergency-contact question to the bootstrap form.
