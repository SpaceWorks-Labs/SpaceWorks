# Phase 1d Part B handoff

Implemented in `lane/mobile-1d`, building on the existing unstaged Part A. No staging,
commits, stashes, merges, rebases, Docker or pytest. The four shared hot-spot files are
untouched. No module key changed, so `docs/MODULES.md` needs no update.

## Behavior

- Daily Stage B is registered in beat, the 1440-minute beat-less scheduler, and tenant
  gate participation. Each tenant scrub commits separately; gated tenants retry later.
  All mutable copies in the plan are scrubbed through model saves. Global identity
  removal waits for tenant/object completion and terminal Apple revocation work.
- The random `User.deletion_username` coordinates the same placeholder across tenant
  scrubs before changing the global username. The encrypted `deletion_email_ciphertext`
  records the address at Stage A for address-only email-log copies. Both are internal,
  omitted from portable exports and cleared at final purge.
- Profile/project removal first commits an object journal with key, bucket and size.
  Byte deletion commits before quota release; the quota decrement and its completion
  stamp are atomic. Storage failures preserve retry state, and HEAD failures roll back
  the owning-row deletion so its key remains available.
- Apple sign-in keeps verified `aud`, accepts an optional authorization code, verifies
  the exchanged subject, and stores an encrypted token per identity/client. Code
  exchange failure does not fail sign-in. Stage A commits revocation work before its
  on-commit queue attempt. Daily recovery, durable backoff, no-credential handling and
  the day-80 unavailable audit prevent permanent blocking. A sign-in exchange finishing
  after Stage A is also sent through this durable revocation path.
- Portable imports keep deletion-requested identities inactive with their timestamps;
  purged identities are anonymous. A deleted source cannot be LINK_EXISTING to an
  unrelated live target identity: that decision is refused, requiring separate inactive
  identity creation. Deployment backup projections already carry concrete User columns.
- The web account deletion section remains reachable without membership self-service,
  including after leaving a space. It supports all Part A proof methods, phone-code
  restart and provider second factors, typed confirmation, refreshed blockers, a result
  receipt, and clearing session/private/offline caches. Fix links use verified tenant
  domains or the configured central application URL.
- INVARIANTS and the new privacy note disclose the exact retained-record list.

Apple protocol references checked: [token validation](https://developer.apple.com/documentation/signinwithapplerestapi/generate-and-validate-tokens)
and [token revocation](https://developer.apple.com/documentation/signinwithapplerestapi/revoke-tokens).

## Validation and integration limits

- Component Vitest: **10 passed**, including axe checks. Local npm installation was
  blocked by registry EACCES; dependencies were copied into this worktree from the
  existing main-checkout installation. No changes were made to that installation.
- TypeScript reports only missing `lucide-react` imports from that existing dependency
  set. The one task-specific layout prop error it found was fixed. A complete typecheck
  and build remain unverified until the dependency is available.
- Account modules, new tests and migration parse; touched production files stay under
  300 lines (the existing settings exception remains). `git diff --check` passes.
- Task/fanout/object AST declarations pass (45/16/117 entries) with the pre-existing
  syntax-invalid `backend/apps/operations/org_report_scope.py:22` excluded **in memory
  only**. The unchanged file has an import inside another import's parentheses. The
  unmodified full source-gate check therefore remains blocked.
- Docker/pytest were not run, as instructed. Backend tests, migration execution and
  runtime projection checks need the coordinator's normal environment after re-pinning
  the shared catalog/schema files. The CLI review gate is unavailable: `codex doctor`
  reports inaccessible configuration/home and unreachable provider endpoints.
- Test files are ignored by the existing `.gitignore`; retain them explicitly during
  integration. Nothing was staged to bypass that rule.

## Files changed by Part B

Backend:

- `backend/apps/accounts/account_deletion.py`
- `backend/apps/accounts/account_deletion_blockers.py`
- `backend/apps/accounts/account_deletion_discovery.py`
- `backend/apps/accounts/account_purge.py` (new)
- `backend/apps/accounts/account_purge_objects.py` (new)
- `backend/apps/accounts/account_purge_scrub.py` (new)
- `backend/apps/accounts/apple_credentials.py` (new)
- `backend/apps/accounts/apple_revocation.py` (new)
- `backend/apps/accounts/migrations/0036_account_purge.py` (new)
- `backend/apps/accounts/models.py`
- `backend/apps/accounts/models_account_purge.py` (new)
- `backend/apps/accounts/models_email.py` (new, schema-neutral split)
- `backend/apps/accounts/serializers_account_deletion.py`
- `backend/apps/accounts/serializers_social.py`
- `backend/apps/accounts/social_apple.py`
- `backend/apps/accounts/tasks.py`
- `backend/apps/accounts/views_social_login.py`
- `backend/apps/audit/presentation_catalog_accounts.py`
- `backend/apps/data_export/classification_platform.py`
- `backend/apps/data_export/fields.py`
- `backend/apps/data_export/references_core.py`
- `backend/apps/makerspaces/storage_key_collectors.py`
- `backend/apps/operations/management/commands/run_scheduled_tasks.py`
- `backend/apps/tenant_migration/gate_policy_tasks.py`
- `backend/apps/tenant_migration/identity_resolution.py`
- `backend/apps/tenant_migration/target_projection_fields.py`
- `backend/apps/tenant_migration/tenant_dump_authority_supplement.py`
- `backend/apps/tenant_migration/tenant_dump_user_rows.py`
- `backend/config/settings.py`

Frontend:

- `frontend/src/features/auth/reauthenticationApi.ts`
- `frontend/src/features/auth/reauthenticationSocial.ts`
- `frontend/src/features/auth/socialSdk.ts`
- `frontend/src/features/members/AccountDeletionBlockers.tsx` (new)
- `frontend/src/features/members/AccountDeletionReauthentication.tsx` (new)
- `frontend/src/features/members/MemberAccountDeletion.tsx` (new)
- `frontend/src/features/members/accountDeletionApi.ts` (new)
- `frontend/src/features/members/MemberAccountPage.tsx`
- `frontend/src/features/members/MemberArea.tsx`

Documentation:

- `docs/INVARIANTS.md`
- `docs/SOURCE-MAP.md`
- `docs/privacy-account-deletion.md` (new)
- `docs/account-deletion-part-b-handoff.md` (this file)

Tests (ignored by git):

- `backend/tests/accounts/test_account_purge.py` (new)
- `backend/tests/accounts/test_account_purge_import.py` (new)
- `backend/tests/accounts/test_apple_deletion.py` (new)
- `backend/tests/accounts/test_apple_token_conditions.py` (updated audience/claim contract)
- `frontend/src/features/members/MemberAccountDeletion.test.tsx` (new)

## Exact model-field hot-spot list

Migration `accounts/0036_account_purge` depends on the listed actual accounts leaf,
`0035_account_deletion`. These are the complete **Part B** additions, using Django field
names (not FK column attnames):

| Model label | New fields |
| --- | --- |
| `accounts.User` | `account_purged_at` (nullable datetime), `deletion_email_ciphertext` (blank TextField, default empty), `deletion_username` (blank CharField, max 150, default empty) |
| `accounts.AccountPurgeProgress` | `id`, `user`, `makerspace`, `done_at` |
| `accounts.AccountPurgeObject` | `id`, `user`, `makerspace`, `bucket`, `object_key`, `size_bytes`, `deleted_at`, `quota_released_at`, `attempts`, `last_error` |
| `accounts.AppleRefreshCredential` | `id`, `social_identity`, `client_id`, `token_ciphertext`, `updated_at` |
| `accounts.AppleRevocation` | `id`, `user`, `client_id`, `attempts`, `last_error`, `done_at`, `next_attempt_at` |

Inherited Part A additions still requiring the same shared-snapshot integration:
`accounts.User.deletion_requested_at`, `accounts.User.deletion_purge_after` (nullable
datetimes); `accounts.PhoneVerificationChallenge.purpose` adds the `reauth` choice.
The schema-neutral `models_email.py` split changes no EmailVerificationChallenge or
DailyOtpEmailCounter fields.

## Exact API hot-spot list

**Part B adds no routes.** These operations have changed schemas:

- `GET /api/v1/auth/account/deletion`: blockers add nullable `makerspace_slug`,
  `makerspace_member_url` and `organization_url` fix-link fields.
- `POST /api/v1/auth/account/deletion`: the 409/403 blocker schema adds those fields.
- `POST /api/v1/auth/social/apple`: optional write-only `authorization_code` and optional
  `redirect_uri` on SocialLoginSerializer; Apple exchanges the code after sign-in.
- `POST /api/v1/auth/social/google`: the shared SocialLoginSerializer exposes the same
  optional fields; Google behavior is unchanged.
- `POST /api/v1/auth/social/oidc/{slug}`: the same shared serializer change; OIDC behavior
  is unchanged.

The full inherited Part A route list remains in
[`account-deletion-part-a-handoff.md`](account-deletion-part-a-handoff.md), including the
new reauthentication/deletion routes and obligation-writer error behavior. Regenerate
OpenAPI and both generated artifacts for the combined A+B tree at integration.
