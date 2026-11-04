# Booking printable passes (BK-G)

- `bookings/pass_templates.py`: strict four-field binding policy, default card and bounded
  version-2 geometry, using core `operations/printable_layout.py`.
- `bookings/serializers_passes.py`: typed request/response contract and field vocabulary.
- `bookings/pass_rendering.py`: encrypted name accessor, resource/local window/noncredential
  reference projection and fixed sample values; delegates to core `printable_pdf.py`.
- `bookings/services_passes.py`: locked live editor/scanner/owner authorization, arrival
  requirements, template writes and render/download audit. No stored PDF or artwork.
- `bookings/views_passes.py`, `urls_passes.py`: private OpenAPI staff routes and shared
  30/hour render throttle. `urls_confirmation.py` mounts the owner PDF route.
- `BookableSpace.pass_template`: JSON configuration, migration
  `0015_bookablespace_pass_template` follows the actual BK-C `0014` leaf.
  `services_clone.py` independently copies the layout through core `copy_fields`.
- Existing classification/JSON-reference/authority/field-snapshot registries retain the
  field independently of runtime module availability; existing resource datasets,
  module purge and whole-tenant purge remain sufficient. No new User/object edges.
- `makerspaces/confirmation_privacy.py`, origin registries, API-client scope registry
  and explicit claim-session refusal cover the new owner/staff paths and errors.
- `staff/BookingPassDesigner.tsx`, `bookingPassApi.ts`, `BookingPassPrint.tsx`: shared
  positioned editor, tenant/resource TanStack keys, mutation invalidation, direct PDF
  download and loading/errors. `BookingDrawer.tsx` adds the authorized designer tab;
  `BookingArrivalScanner.tsx` uses the current server print-eligibility projection.
- `bookings/BookingConfirmation.tsx`, `bookingConfirmationApi.ts`: owner PDF action,
  distinct from private QR PNG and calendar downloads.
- Ignored tests: `backend/tests/bookings/pass_helpers.py`, `test_pass_templates.py`,
  `test_pass_api.py`, `test_pass_rendering.py`, `test_pass_registries.py`,
  `test_pass_portability.py`; frontend
  `BookingPassDesigner.test.tsx`, `bookingPassApi.test.tsx`, `BookingPassPrint.test.tsx`.
  `bk_g_catalog_pin.py` reconstructs the reviewed graph; `bk_g_schema_snapshot.py`
  records the reviewed OpenAPI delta for this Django-free host.
