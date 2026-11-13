# Private saved details provider

This package has no Events import, tenant FK, public-profile writer or login-identity
writer. Its six account models and two encryption models are listed field by field
in `manifest.json`. G owns importing them, migrations, database backstops, route
registration and enablement. The separate tenant evidence model and three subject
adapters are in `apps.events.answer_derivations/manifest.py`.

## Required integration sequence

1. **G, integration step 2:** import the account models in the existing Accounts
   barrel and `account_models` in Encryption. Author migrations from actual leaves.
   Install the manifest's member-kind, stable-owner, ciphertext and source/global/
   account fence database backstops. Preserve keys/owned bytes in deployment backup;
   exclude the entire global vault and key custody from every tenant closure/export.
2. **G/F, steps 2–3:** install `fields.install_profile_fields(provider)` with F's
   authoritative descriptor and normalization functions. Its protocol is
   `descriptors() -> tuple[dict,...]`, `normalize(key,value) -> canonical value`.
   This package deliberately has no alternative standard-key validator. Without
   the adapter writes fail closed. Register checks from `account_checks` and
   readiness from `account_readiness`, independent of tenant PII being enabled.
3. **G/A/C/F, steps 3–4:** install `prefill.install_context_provider(provider)`.
   Resolve every event/posting/subject through live member eligibility, host/source/
   origin/module gates, including the first-use account with no membership or rows.
   Return only F's visibility-filtered, mapping-compatible questions. Values are
   keyed by **standard field key**, as the emergency-contact fixture requires;
   derivation inputs are keyed by question ID. Missing saved rows have no version
   entry (the caller uses base 0); tombstones keep their actual version.
4. F's trusted validation adapter constructs `intents.ValidatedSaveInput` from
   normalized **visible** values, server form descriptor and canonical answers.
   Sensitive choices are explicit false unless opted in; UI/prefill proposes
   default-on nonsensitive choices. An omitted/empty true-choice set creates no
   intent and needs no account key. Check an existing domain operation receipt
   before any preparation. Call `prepare_saved_detail_intent` outside transactions.
5. Install `subject_binding.install_subject_binding(provider)`. The provider must
   recheck the actual typed parent, same event/owner and creation operation receipt,
   then return `VerifiedIntentBinding` with **live** form/answer hashes, reviewed
   date revision and chosen visible field names. It performs no key I/O/account
   row locks. It is an internal provider, never HTTP input.
6. G acquires source boundary then `account_fences(owner_ids, tenant_ids=...)`
   before Event/domain locks. Call the frozen
   `insert_prepared_locked(prepared, subject=..., locks=...)` in that transaction.
   It inserts prepared ciphertext only; a rolled-back event leaves no intent.
   Every age-source insertion also declares the shared owner fence even without
   vault saving. See the derivation README for its separate tenant-key preparation.
7. **G, steps 3–4:** mount `urls.urlpatterns` at
   `/api/v1/member/saved-details/`; register all eleven named paths/thirteen methods
   plus authorized HEAD reads in claim/origin/delegated/API-client/source policies.
   Views reject tenant API clients and nonmember/inactive/stub/walk-in/retired users.
   OpenAPI serializers and errors are in `serializers.py`/`views.py`. Regenerate
   shared generated schema/client only in G.
8. Mount `SavedDetailsPage` inside the member AppShell, outside membership gating.
   A/C/G use `useRegistrationSavedDetails`, controlled save choices, `AgeReview`
   and `SaveIntentNotice`. Suggestions remain reviewable drafts. Never persist
   DOB/answers in local storage or query keys. List tombstones have `value:null`
   and their version so explicit recreation cannot overwrite newer data.
9. **G/B, steps 3–4:** B's §12C from-saved endpoint uses
   `resume_copy.prepare_saved_resume_selection(actor_id, saved_asset_id,
   saved_detail_version)` to validate the current owner selection and obtain
   owner-authorized bounded chunks, never a presigned source or writable ownership
   path. B must create/finalize a fresh independently owned event asset and charge
   event quota. The source gateway checks active owner, key custody/epoch, current
   scan policy and asset version before every chunk. Sharing consent remains D's.
10. G schedules `tasks.process_saved_details` through the existing durable scheduler
    (also in broker-less deployments). It applies pending intents, validates files,
    builds exports, retires replaced/abandoned originals, expires exports/intents/
    receipts and retries all-version cleanup. Postcommit worker failure never turns
    the successful event submission into a failed admission. Known stale epochs
    become safe failed status requiring explicit owner resubmission.

## Storage, erasure and settings

- G provisions/persists `ACCOUNT_SAVED_DETAILS_ENABLED`, `ACCOUNT_PII_KEY_BROKER`,
  independent `ACCOUNT_PII_MASTER_KEY`/`_PREVIOUS` or explicit account KMS key ID.
  Never generate replacement secrets in a request. The local probe and KMS calls
  run outside DB transactions with bounded provider timeouts; no plaintext mode.
- Résumé PDF safety cap is 10 MiB, account pool 50 MiB. Only self-host (blank
  `PLATFORM_DOMAIN_SUFFIX`) can raise `ACCOUNT_SAVED_ASSET_BUDGET_BYTES`. Set
  `ACCOUNT_SAVED_RESUME_SCAN_REQUIRED` and supply the always-present, model-free
  `ACCOUNT_SAVED_RESUME_SCANNER(bytes) -> "clean"` adapter for configured scanning.
  Missing/failing required scanner is 503, never a ready file.
- Each validation/export claim uses a different server-only verification/final
  key. Late workers cannot overwrite winning bytes, including unversioned stores.
  All claim keys are registered before I/O in cleanup metadata. Original/staging/
  verification versions are deleted through durable FK-free receipts, including
  after User deletion; repeat cleanup catches late worker/presign writes.
- Replaced selected résumés retire once unreferenced; abandoned uploads retire
  after 24 hours. Pending résumé intents preserve candidates until resolved. The
  periodic worker bounds work per batch and retains reservations until deletion.
- Account deletion calls `lifecycle.erase_account_vault(user_id, actor=...)` in
  its **account-only phase**, before User deletion, after source-fenced event draft
  erasure. It takes exclusive owner fence, User then key/owned-row locks, removes
  vault/intent/receipt/export rows, destroys keys and retains an erased fence while
  User exists. Independently submitted event answers/copies remain their domain's
  evidence. Compose the derivation owner-export adapter separately from the vault
  archive; a tenant never gains access to the global vault.
- Command receipts retain allowlisted metadata and a keyed request digest only,
  never another copy of deleted values or an upload descriptor. Same-body PUT replay
  returns the normalized value supplied again by its owner; changed-body replay
  returns 409. Intents erase payload immediately on completion or after seven days;
  safe receipts expire after thirty days. Owner ZIP archives expire after 24 hours.

## Tests

The backend tests for this provider live beside the other accounts tests:
`test_http.py` checks every route and its OpenAPI method, `test_prefill_contract.py`
replays the bootstrap and compound emergency payloads, and `test_concurrency.py` uses
real PostgreSQL sessions for intent races and fences.
