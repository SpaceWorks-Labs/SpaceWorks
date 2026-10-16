# Setup areas: Stage 2 handoff

Implementation is unstaged on `dev`. No commits, merges, pushes, Docker calls, nested Codex calls or
VERSION changes were made.

The [operator question flow and defaults](setup-for-makerspaces.md#area-follow-up-questions) and
[area ? modules ? features table](MODULES.md#areas-used-by-setup) describe the shipped flow.
Questionnaire configuration is applied from private stdin through `apply_setup_areas`; charge, ticket and checkout defaults share the actual
space currency field, so later integration questions cannot overwrite it. Stripe credentials use
the validated, audited settings writer and tenant write gate. Module
install/uninstall and capability validation remain the existing mechanisms. Optional uninstalls retain
all data. Existing area settings and intentional feature choices survive menu changes; newly satisfied
prerequisites activate the corresponding features (including online payments for existing domains).
Hiding Inventory preserves core retained-loan policy/charge switches and only disables new lending.
Deployment editions reflect the union of live makerspaces, preserving organization labels; an edition
change refreshes the host configuration and restarts application services.

Staff editors added:

- Event default registration audience (new field; existing events keep their own audience).
- Daily digest default (new field; saved member preferences override it, safety mail stays immediate).
- Borrow request access (existing anonymous-request flag, exposed through its audited service). The
  server-derived members-only policy stays fixed while Membership is installed.

Setup asks for the existing makerspace timezone before quiet hours so local schedule values have
an explicit interpretation. Existing editors cover loan limits/renewals, loan charges/currency, membership join/vouch/form/plan
settings, feature switches/MFA and per-machine-type reminder leads. Bookings has no space-level buffer
or cancellation fields; these remain in the resource editor. Machine reminder answers apply to existing
built-in/local types, as explained in the prompt; later types retain their existing default policy.

Local verification:

- 12 standalone host tests passed; default/API-only/platform vectors in the existing host questionnaire
  harness also passed using its stubs.
- Registry-only checks passed for all eight areas, exact module bundles, satisfiable features, payment
  dependencies, edition derivation and registry coverage. No model/database code was imported for these.
- Full frontend suite: 219 files / 908 tests passed before adding the new settings tests. Final focused
  verification: four files / 19 tests passed, including the new four settings tests and affected editors.
- Final TypeScript build passed. Changed Python files compile; changed shell files pass `bash -n`.
- LF, 300-line source ceilings, `git diff --check`, an empty index, and byte-identical AGENTS/CLAUDE passed.

Django/pytest are unavailable on this Windows host and Docker was unavailable by task constraint, so
real database/service/API tests and backend drift gates remain for the coordinator. The OpenAPI
snapshot was synchronized to the source declarations and the TypeScript API client regenerated with
the repository generator; check canonical drf-spectacular regeneration in the pinned backend toolchain.

Suggested coordinator checks (each dev.sh test invocation owns disposable infrastructure):

```bash
./scripts/dev.sh test tests/makerspaces/test_setup_areas.py tests/makerspaces/test_setup_area_settings_api.py tests/test_host_setup_areas_behavior.py tests/test_host_setup_questions_behavior.py tests/test_host_installer_behavior.py tests/test_host_updater_behavior.py tests/test_host_bundle_behavior.py
./scripts/dev.sh test tests/makerspaces/test_module_registry.py tests/makerspaces/test_module_install.py tests/makerspaces/test_module_purge.py tests/test_capabilities.py tests/test_environment_reference_drift.py tests/test_env_surface_drift.py tests/hardware_requests/test_loan_policy_schema.py tests/makerspaces/test_profile_schema.py
# Regenerate OpenAPI using the pinned Django/drf-spectacular environment:
# python manage.py spectacular --format openapi-json --file <frontend/openapi-schema.json>
cd frontend
node scripts/generate-api-client.mjs
npx tsc -b
npx vitest run
```

Changed files (including new files; the backend tests below are intentionally local/gitignored):

- [README.md](../README.md)
- [backend/apps/admin_api/serializers_makerspace_mutations.py](../backend/apps/admin_api/serializers_makerspace_mutations.py)
- [backend/apps/admin_api/serializers_makerspaces.py](../backend/apps/admin_api/serializers_makerspaces.py)
- [backend/apps/admin_api/views_machine_type_policy.py](../backend/apps/admin_api/views_machine_type_policy.py)
- [backend/apps/data_export/classification.py](../backend/apps/data_export/classification.py)
- [backend/apps/events/serializers_admin.py](../backend/apps/events/serializers_admin.py)
- [backend/apps/events/serializers_series.py](../backend/apps/events/serializers_series.py)
- [backend/apps/events/services.py](../backend/apps/events/services.py)
- [backend/apps/events/services_series.py](../backend/apps/events/services_series.py)
- [backend/apps/events/views_admin_event_list.py](../backend/apps/events/views_admin_event_list.py)
- [backend/apps/integrations/digests.py](../backend/apps/integrations/digests.py)
- [backend/apps/integrations/migrations/0031_daily_digest_default.py](../backend/apps/integrations/migrations/0031_daily_digest_default.py)
- [backend/apps/integrations/models_timing.py](../backend/apps/integrations/models_timing.py)
- [backend/apps/integrations/serializers_timing.py](../backend/apps/integrations/serializers_timing.py)
- [backend/apps/integrations/timing_settings.py](../backend/apps/integrations/timing_settings.py)
- [backend/apps/integrations/views_timing.py](../backend/apps/integrations/views_timing.py)
- [backend/apps/machines/policy_settings.py](../backend/apps/machines/policy_settings.py)
- [backend/apps/makerspaces/management/commands/apply_setup_areas.py](../backend/apps/makerspaces/management/commands/apply_setup_areas.py)
- [backend/apps/makerspaces/management/commands/setup_instance.py](../backend/apps/makerspaces/management/commands/setup_instance.py)
- [backend/apps/makerspaces/migrations/0088_setup_event_audience.py](../backend/apps/makerspaces/migrations/0088_setup_event_audience.py)
- [backend/apps/makerspaces/models_public_site.py](../backend/apps/makerspaces/models_public_site.py)
- [backend/apps/makerspaces/settings_validation.py](../backend/apps/makerspaces/settings_validation.py)
- [backend/apps/makerspaces/setup_area_application.py](../backend/apps/makerspaces/setup_area_application.py)
- [backend/apps/makerspaces/setup_areas.py](../backend/apps/makerspaces/setup_areas.py)
- [backend/apps/makerspaces/setup_defaults.py](../backend/apps/makerspaces/setup_defaults.py)
- [backend/apps/makerspaces/setup_settings.py](../backend/apps/makerspaces/setup_settings.py)
- [backend/apps/notifications/preferences.py](../backend/apps/notifications/preferences.py)
- [docs/INVARIANTS.md](../docs/INVARIANTS.md)
- [docs/MODULES.md](../docs/MODULES.md)
- [docs/SOURCE-MAP.md](../docs/SOURCE-MAP.md)
- [docs/self-hosting.md](../docs/self-hosting.md)
- [docs/setup-for-makerspaces.md](../docs/setup-for-makerspaces.md)
- [frontend/openapi-schema.json](../frontend/openapi-schema.json)
- [frontend/src/features/staff/BorrowRequestAccessSettings.tsx](../frontend/src/features/staff/BorrowRequestAccessSettings.tsx)
- [frontend/src/features/staff/EventDefaultsSettings.tsx](../frontend/src/features/staff/EventDefaultsSettings.tsx)
- [frontend/src/features/staff/EventsPanel.tsx](../frontend/src/features/staff/EventsPanel.tsx)
- [frontend/src/features/staff/MakerspaceSettingsPanel.tsx](../frontend/src/features/staff/MakerspaceSettingsPanel.tsx)
- [frontend/src/features/staff/NotificationTimingSettings.tsx](../frontend/src/features/staff/NotificationTimingSettings.tsx)
- [frontend/src/features/staff/eventsApi.ts](../frontend/src/features/staff/eventsApi.ts)
- [frontend/src/generated/api.ts](../frontend/src/generated/api.ts)
- [scripts/install-host-bundle.sh](../scripts/install-host-bundle.sh)
- [scripts/module-area-selection.sh](../scripts/module-area-selection.sh)
- [scripts/module-legacy-selection.sh](../scripts/module-legacy-selection.sh)
- [scripts/module-selection.sh](../scripts/module-selection.sh)
- [scripts/setup-area-questions.sh](../scripts/setup-area-questions.sh)
- [scripts/setup-areas-json.sh](../scripts/setup-areas-json.sh)
- [scripts/setup-question-input.sh](../scripts/setup-question-input.sh)
- [scripts/setup-questions.sh](../scripts/setup-questions.sh)
- [scripts/update.sh](../scripts/update.sh)
- [setup.sh](../setup.sh)

- [scripts/setup-host-orchestration.sh](../scripts/setup-host-orchestration.sh)
- [docs/setup-areas-handoff.md](setup-areas-handoff.md)

Local backend tests changed/added:

- [backend/tests/test_host_setup_areas_behavior.py](../backend/tests/test_host_setup_areas_behavior.py)
- [backend/tests/makerspaces/test_setup_areas.py](../backend/tests/makerspaces/test_setup_areas.py)
- [backend/tests/makerspaces/test_setup_area_settings_api.py](../backend/tests/makerspaces/test_setup_area_settings_api.py)
- [backend/tests/test_host_setup_questions_behavior.py](../backend/tests/test_host_setup_questions_behavior.py)
- [backend/tests/test_host_installer_behavior.py](../backend/tests/test_host_installer_behavior.py)
- [backend/tests/test_host_updater_behavior.py](../backend/tests/test_host_updater_behavior.py)

## Review fixes

- Registered both new settings in the tenant-dump field catalog. The event audience default
  preserves portable admission policy like event/series audiences; the digest default is dropped
  like the other notification timing fields, so source mail policy cannot authorize target delivery.
- Change modules preserves existing feature choices, including standalone debt/geofence switches
  and notification switches. Newly installed prerequisites still activate their features, explicit
  answers still apply, and enabling Inventory still turns on lending.
- Events uses USD only when no currency is stored; existing shared currencies survive automation
  unless a currency answer explicitly replaces them.
- Added focused catalog, feature preservation and currency regressions in the local/gitignored
  `backend/tests/makerspaces/test_setup_areas.py`.
- Local Python syntax, currency-default behavior, LF/line ceilings and `git diff --check` passed.
  Django/pytest remain unavailable on this host; database regressions were not run here.

**Coordinator required:** repin `CATALOG_SCHEMA_SHA256` for the two new fields, then run the
Docker/database checks (including `tests/tenant_migration/test_tenant_dump_catalog_d1.py`) and
the re-review. The digest was intentionally left unchanged; the catalog regression requires that repin.
