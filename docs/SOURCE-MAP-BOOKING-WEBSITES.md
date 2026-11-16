# Booking resource websites (BK-F)

`bookings/models_website.py` owns the concrete `BookingResourcePage`, page section and
private asset models. A page's tenant follows its one-to-one `BookableSpace`; children
cannot be moved across pages. Migrations `0017_resource_website` and
`0018_website_integrity` create the graph and SQL ownership backstops.

`website_visibility.py` owns the unchanged active/public resource query extracted from
`views_public.py`, live resolution, release gating and directory query adapter.
`website_projection.py` allow-lists core detail, public rule summaries and published
sections, emitting backend image paths rather than object URLs. `website_adapter.py`
registers the typed Bookings adapter in the shared makerspaces serving registry and
registers `website_copy.py` with the existing clone extension registry.

`services_website.py` handles resource locks, live authority, optimistic revisions and
audited saves/releases. `services_website_assets.py` delegates upload, sniffing, bounded
WebP conversion, ownership, quota and rollback cleanup to `makerspaces/website_assets.py`.
Public byte reads use the shared no-store image response after the domain visibility
and published-reference checks. `serializers_website.py`, `views_website_admin.py`,
`views_website_public.py` and `urls_website.py` own the strict HTTP contracts.

Always-present `makerspaces/website_visibility.py`, `website_directory.py`,
`website_serving.py`, `website_views.py` and `website_urls.py` serve embeds, crawler share
HTML, discovery and sitemaps through domain adapters. Booking embeds supply the “Book a
time” action label; Events retains its registration label. Framing configuration remains
the existing makerspace setting. Caddy variants and frontend nginx route booking crawlers
to the shared `/share/bookings/<uuid>/` surface while retaining SPA framing denial.

Retention uses the literal `tenant_migration/catalog_website.py` fields and existing
classification/model/snapshot composition, explicit datasets, private object ownership,
portable unique keys and release-reset policy. `module_purge_collectors_booking_website.py`
supplies key sizes and private keys; page rows cascade from the existing resource purge.
`storage_key_collectors.py` and `recompute_storage` include gallery objects for whole-tenant
cleanup, migration/backup capture and reconciliation. There are no User FKs or JSON fields
in the three editorial models and no new encryption registration.

Frontend `bookings/bookingWebsiteTypes.ts` and `bookingWebsiteApi.ts` define resource/tenant
query keys and mutation invalidation. `PublicBookingResourcePage.tsx` combines public core
detail, rule summaries, `BookingResourceWebsite.tsx` and ordinary self-booking.
`BookingDiscoverPage.tsx` consumes paginated shared discovery. Staff
`BookingWebsiteEditor.tsx` uses the existing drawer tab shell, separate private previews,
restricted Markdown and shared image transport. `AppRoutes.tsx` supports tenant-prefixed
and single-site resource details plus `/discover/bookings`.

Ignored tests live in `backend/tests/bookings/website_helpers.py`, `test_website_*.py`,
`bk_f_catalog_pin.py`, `bk_f_schema_snapshot.py` and frontend website test files. Backend
tests require the supported isolated Django/Postgres runner; the standalone catalog and
schema helpers also run on the Windows host.
