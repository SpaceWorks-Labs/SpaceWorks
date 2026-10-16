# Booking integration reads (BK-H)

| Files | Responsibility |
| --- | --- |
| `backend/apps/bookings/views_integration.py` | Five scope-authorized reads, live tenant/module/feature gates, disclosure audits through the source fence |
| `backend/apps/bookings/serializers_integration.py` | Explicit resource/reservation fields, released public-page projection and separately scoped current arrival |
| `backend/apps/bookings/urls_integration.py` | Dedicated `/api/v1/booking-integration/` routes; root registration in `config/urls.py` |
| `backend/apps/bookings/integration_targets.py` | Typed BookableSpace/Booking targets registered from live `BookingsConfig.ready` |
| `backend/apps/apiclients/scope_registry_booking_reads.py` | Core scope constants, runtime-independent catalogue and ten explicit GET/HEAD entries |
| `backend/apps/apiclients/read_schema.py` | Domain-neutral HMAC headers, pagination parameters and typed OpenAPI errors |
| `backend/apps/apiclients/read_contract.py` | Existing verified-signature permission, per-client throttle, typed target resolver and signed keyset cursor |
| `backend/apps/apiclients/read_prefixes.py`, `scope_registry_reads.py`, `scope_grants.py` | Compose domain prefixes/scopes/routes/catalogue; enforce operator-only grant policy and arrival prerequisites |
| `frontend/src/lib/bookingAnalyticsRoutes.ts` | Public booking list/detail route templates consumed by shared manual analytics |
| `frontend/openapi-schema.json`, `frontend/src/generated/api.ts` | GET/HEAD snapshot and regenerated API types |

`views_staff_grants.py` already inherits Lane F's `RecentReauthenticationMixin`;
the existing staff request client handles step-up and TanStack Query grant hooks
invalidate resource/access lists. No additional staff screen is needed for machine reads.
BK-E already calls BK-C's arrival metric adapter; BK-G already uses core pass layout primitives.

Ignored backend coverage lives under `backend/tests/bookings/` in
`integration_read_helpers.py`, `test_integration_reads.py`,
`test_integration_read_policy.py` and `test_integration_reauthentication.py`.
Frontend coverage is `frontend/src/lib/bookingAnalyticsRoutes.test.ts` and
`bookingGrantReauthentication.test.ts` (real shared HTTP client, no second retry mechanism).

Signed resource reads compose BK-F's canonical public visibility and release projection
through a nested explicit allow-list. Private, inactive, disabled or unreleased resources
keep their signed descriptive fields but expose no public-page content. Public image
references point to backend endpoints that recheck release and ownership. The public
detail/image/discovery routes use public scopes, independently of signed booking scopes.
No retention/portability/object graph changes are needed for the reads themselves.
