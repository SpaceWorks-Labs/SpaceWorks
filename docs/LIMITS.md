# Limits

Space Works supports a fully free space and spaces that charge for selected services. Limits protect
capacity, storage and shared services; setting a price does not increase a limit. See
[Free and paid](../README.md#free-and-paid) for the money switches and [features](FEATURES.md) for the areas.

## Who sets a limit

On a fresh managed or self-hosted installation, resource quotas are **unlimited until configured**.
The built-in fair-use numbers are suggestions in the console, not automatic restrictions. Fixed input,
file-format and security bounds still apply on both kinds of installation.

Only the platform superadmin changes resource quotas: use the platform limits/defaults screens or the
space's limits controls in `/control/`. Space Managers and area managers can read their scoped usage.
A Space Manager can configure an area's ordinary rules, such as a booking's longest duration or a shop
product's per-order maximum, within its fixed validation bounds.

For a resource quota, resolution is: **space override → hosted plan → platform default → unlimited**.
An explicit `null` or `-1` override means unlimited and overrides an inherited cap. Zero allows no new
usage. A hosted plan is consulted only when managed plans are enabled and the space is hosted.
Explicit overrides and platform defaults apply to self-hosted and own spaces too.
Sources: `backend/apps/makerspaces/limits_core.py:115`,
`backend/apps/managed_hosting/space_quotas.py:63`,
`backend/apps/managed_hosting/limit_defaults.py:1`.

A resource or payment quota normally refuses starting something new. It preserves stored data,
existing workflows and debt settlement, refunds and privacy requests. Required issue/return evidence
must still fit the configured upload and storage allowances. If evidence does not fit, the handover
is refused until the operator raises the allowance; required evidence is never waived. The report-download quota can refuse a new report
file; the separate full data export remains available subject to its concurrent-job/storage safeguards.
Calendar-month quotas use UTC month boundaries; daily counters use the period implemented by their
counter. Payment amount quotas apply separately to each currency and compare the exact amount,
including cents. No cross-currency conversion is performed.

## Reading an error

Web and native clients call the same server gates. A refused request includes the HTTP status and the
stable code below. Its display message explains the limit; translations may change the wording.

| Family | Status and code | Display message |
| --- | --- | --- |
| Ordinary resource count | 400 `limit_reached` | “You've reached the free … limit for this space — ask the operator to raise it or self-host.” This is legacy wording; configured caps also apply on self-hosts. |
| Hosted-plan count | 400 `plan_limit_reached` | “This space has reached the … included in its … plan (…). Ask the platform operator to change the plan.” |
| Event / booking monthly quota | 409 `event_quota_reached` / `booking_quota_reached` | “This space has reached its monthly allowance of … (…). Ask the platform operator to raise it.” |
| New paid transaction quota | 409 `payment_quota_reached` | The same monthly-allowance message; existing debts remain recordable and payable. |
| Additional resource quota | 409 `<key>_quota_reached` | “This space has reached its allowance of … (…). Ask the platform operator to raise it.” |
| Single upload / presign headroom | 400 `upload_limit` | “This file is …; files here can be at most ….” / “This space has used its … of storage. Remove old files or ask the platform operator for more room.” |
| Combined storage reservation / final charge | 400 `limit_reached` | The reserved maximum or accepted final bytes exceed the combined storage allowance. |
| Split storage class | 409 `storage_evidence_bytes_quota_reached` / `storage_public_images_bytes_quota_reached` | The reserved or accepted bytes exceed that storage class allowance. |
| Platform online rail | 409 `platform_rail_limit_reached` | “This space has used the … allowed by the platform (…).” Own gateway credentials and offline settlement are independent. |
| Request throttle | 429 `throttled` | “Request was throttled. Expected available in … seconds.” Respect `Retry-After`. |
| Field validation | 400, field-specific validation messages | DRF returns the field and its message, e.g. “Ensure this value is less than or equal to 3650.” Field-keyed responses retain their existing bodies; a top-level code is not added (decision 509). |

Notification quota exhaustion skips that delivery and records the failure/notice rather than rolling back
the member's completed business action. Telemetry limits can decline retaining samples without an HTTP
quota refusal. Those are background-work policies, not promises that every quota produces a 409.

## Common fixed bounds and space rules

Unless marked otherwise, these apply equally to managed and self-hosted installations. “Fixed” means
the operator cannot change it in space settings. The detailed declaration index below lists the rest,
including every discovered serializer/model length and numeric bound.

| Area | What is limited; default or boundary | Who can change it | Refusal / behavior; source |
| --- | --- | --- | --- |
| Lists | Default page size 24; individual routes may use a different fixed page size | Fixed server pagination | Extra rows are on the next page, not refused; `backend/config/settings_drf.py:8` |
| Inventory import | 5,000 nonblank rows; 5 MiB upload; preview at most 100 columns | Fixed | 400 field validation with “Bulk import is limited to 5000 rows.”; `backend/apps/admin_api/bulk_import_parsers.py:5`, `bulk_import_sheet.py:24` |
| ID-programme import | 2 MiB, 2,000 rows, 40 columns, 500 characters per cell; preview 20 rows | Fixed | 400 file validation; `backend/apps/id_programmes/imports.py:23` |
| Bulk staff decisions | At most 50 IDs per request | Fixed | 400 validation; `backend/apps/admin_api/bulk_decisions.py:21` |
| Bulk membership admission | At most 100 rows | Fixed | 400 validation; `backend/apps/makerspaces/membership_admission_bulk.py:15` |
| Inventory loan rules | Loan duration 1–365 days; at most 100 renewals | Authorized inventory settings manager, within fixed bounds | 400 field validation; `backend/apps/inventory/models.py:25` |
| Search | Inventory search text at most 200 characters | Fixed | Search normalizes bounded input; `backend/apps/inventory/search.py:26` |
| Inventory text | Product names at most 200 characters; other labels have their own declared bounds | Fixed field validation | 400 field validation; see inventory/admin serializer declarations below |
| QR generation / print batches | Generate at most 200 assets per operation; batch title 200 characters; label 255 characters. No separate whole-batch item-count cap is declared | Fixed operation/field bounds | 400 field validation; `backend/apps/operations/serializers.py:182`, `:210`, `:214` |
| Submission stages | At most 50 stages; the superadmin's `hackathon_stages` can lower it | Organizer within fixed and per-space ceilings | 400 `invalid_stage_count` / 409 `hackathon_stages_quota_reached`; `backend/apps/events/submissions/models_stages.py:20`, `stage_rules.py:40` |
| Submission family budgets | Video 500 MiB; deck/images/firmware/embroidery 50 MiB each; source/archives 200 MiB; PCB/fab-2d 150 MiB; CAD/3D-print 500 MiB; CNC 300 MiB; resume 1,536 MiB | Fixed ceilings; organizer can lower accepted stage caps | 413 `submission_budget_exceeded` / `storage_budget_exceeded`; `backend/apps/events/submissions/quota.py:11` |
| Public images | Default 10 MiB; JPEG, PNG, WebP with matching extension and detected content | Operator `PUBLIC_IMAGE_MAX_BYTES`; MIME/extension set fixed | Input/content refusal; `backend/config/settings_storage.py:105` |
| Machine types | No separate numeric machine-type quota is registered; machine instances have the `machines` quota | Superadmin sets machine count; authorized staff define types | No invented type-count cap; `backend/apps/makerspaces/limits_core.py:4` |
| Machine type booking defaults | Slots 1–1,440 minutes; before/after buffers 0–1,440 minutes | Authorized machine settings manager | 400 field validation; `backend/apps/machines/views_type_setup.py:20` |
| Machine jobs | 1–999 copies; estimates up to 100,000 minutes | Fixed validation; staff choose actual job values | 400 field validation; `backend/apps/machines/serializers_jobs.py:58` |
| Machine sessions | Staff adjustments 0–1,440 minutes; max session setting 5–1,440 minutes | Authorized machine manager | 400 field validation; `backend/apps/machines/serializers_sessions.py:181` |
| Machine consumables | 32 actual usage entries; templates at most 30 consumables; profiles at most 100 choices | Fixed | Typed service/field refusal; `backend/apps/machines/consumable_usage.py:26`, `template_spec.py:28`, `consumable_profiles.py:59` |
| Bookings | Resource-configured slot length, buffers, advance window, maximum duration, opening hours and included-hours bank | Authorized resource/settings managers; plan hours through membership plans | Reject invalid/out-of-window/conflicting slots in shared booking services; `backend/apps/bookings/models_spaces.py:70`, `backend/apps/bookings/services_bookings.py:1` |
| Events | Event/ticket capacity and registration window; monthly registrations also count against the optional space quota | Event organizer within their action scope | 409 `capacity_full` or registration-window refusal; `backend/apps/events/services_registration.py:1` |
| Hackathon teams | Team size 1–100; default maximum 4; solo mode fixes size to 1; no separate universal team-count quota | Event organizer | 400 config validation or 409 `capacity_full` (“The team's last place was taken.”); `backend/apps/events/hackathons/serializers_config.py:15`, `team_workflow.py:50` |
| Hackathon review | 1–20 reviews; rubric 1–20 criteria; RSVP 1–30 days; submission grace 0–1,440 minutes; offer capacity optional | Event organizer | 400 config validation; `backend/apps/events/hackathons/serializers_config.py:19` |
| Submission files | At most 100 live assets, including at most 10 images; 1,536 MiB per submission; family-specific aggregate caps | Fixed ceilings; organizer can choose lower stage caps | 413 `asset_count_limit` / quota refusals; `backend/apps/events/submissions/quota.py:8` |
| Submission storage | Managed event pool 25,000,000,000 bytes; self-host pool can be uncapped; organizer-specified budget can lower it | Event organizer within deployment ceilings | Asset quota refusal, with reservations counted before upload; `backend/apps/events/submissions/quota.py:17` |
| Shop basket | 50 lines; each merged variant quantity 1–999; product-specific maximum optional | Fixed basket bounds; Shop Manager sets per-product maximum | 400 `variant_invalid`: “Choose a quantity between 1 and 999.” / “An order holds at most 50 different items.”; 400 `per_order_limit`; `backend/apps/shop/pricing.py:21` |
| Evidence photos | Default 10 MiB; JPEG, PNG, WebP; actual uploaded object is checked | Operator `EVIDENCE_MAX_BYTES`; MIME list fixed | Content/size refusal before attachment; `backend/config/settings_storage.py:33`, `backend/apps/evidence/storage.py:174` |
| Evidence retention | Default 365 days; per-space override 30–3,650 days; expiry switch independent | Superadmin policy controls / deployment env | 400 field validation for invalid policy; expired reads 410, metadata retained; `backend/apps/evidence/serializers.py:60`, `backend/config/settings_storage.py:35` |
| Unused-upload cleanup | Default 7 days; override 1–3,650; global and tenant switches both off by default | Operator plus superadmin per space | Only proven unused slots; never attached evidence; `backend/apps/evidence/serializers.py:64`, `backend/config/settings_storage.py:48` |
| Public images and documents | Separate per-format byte and MIME caps, plus per-file and storage-class quotas | Operator env; superadmin quota controls | Reject unsupported MIME / oversize real object; see upload settings index below |
| Reports | Default row preview 100, capped at 500; audit export cap 10,000; saved reports at most 10 email recipients | Fixed; scheduled recipients selected by authorized staff | Bounded output / field validation; `backend/apps/operations/reports.py:29`, `reports_audit.py:16`, `models_report_schedules.py:19` |
| API client | Public 30/min, standard 120/min, trusted 600/min; per-space rate can only lower the tier | Operator env or platform throttle controls; superadmin space cap | 429 `throttled`; `backend/apps/apiclients/throttling.py:21`, `backend/config/settings_drf.py` |
| Deployment API ceiling | Anonymous/device 600/min; authenticated person 1,200/min; endpoint-specific throttles replace this baseline | Operator `THROTTLE_DEPLOYMENT_*` | 429 `throttled`; signed provider callbacks explicitly opt out; `backend/config/settings_drf.py:26` |
| Membership plan hours | 0-8,784 included booking hours and machine hours per term; 0 means no included hours | Authorized membership-plan manager | 400 field validation; `backend/apps/makerspaces/models_membership_plans.py:41` |
| Channel configuration | Optional daily allowance 1-100,000 and per-recipient daily allowance 1-10,000; absent means no channel-config allowance | Authorized notification settings manager | 400 field validation for configuration; delivery skipped when the allowance is spent; `backend/apps/integrations/notification_api_serializers.py:88`, `backend/apps/integrations/notification_quotas.py:24` |
| Staff sign-in policy | Remembered device 1-90 days (90 default); session 1-720 hours (168 default); idle timeout 0-1,440 minutes (0 disables idle expiry) | Space Manager with recent reauthentication; superadmin can lock a stricter floor | 400 `invalid_security_value` in policy validation; strictest policy across staff spaces wins; `backend/apps/accounts/login_security_settings.py:68`, `backend/apps/makerspaces/security_setting_types.py:71` |
| Authentication texts | SMS cost cap default 200/day; managed global OTP caps email 200/day, SMS 100/day | Operator env | Sending refused/skipped through auth quota machinery; `backend/config/settings_runtime.py:127` |

## Every configurable resource quota

Every numeric row below defaults to **unlimited** on both deployment kinds. Only the superadmin changes it,
through a space override, hosted plan or platform default. A suggested number is advisory only.
The boolean `custom_domain` is the exception: self-host/own spaces allow domains; a hosted space needs
an explicit `custom_domain=true`. Its historical self-host exemption is separate from numeric quotas.
The enforcement citation identifies the shared server call or worker used by its surfaces; it is not
an assertion that all route, concurrency and role combinations have been tested. The lane's audit note
lists regression evidence and outstanding verification.

| Area | Quota key / what is counted | Suggestion only | Refusal | Enforcement source |
| --- | --- | --- | --- | --- |
| bookings | `bookable_spaces`: bookable spaces | none | 409 `bookable_spaces_quota_reached` | `backend/apps/bookings/services_spaces.py:123` |
| bookings | `bookings`: active bookings | 500 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/bookings/services_bookings.py:145` |
| bookings | `bookings_monthly`: bookings created this month | none | 409 `booking_quota_reached` | `backend/apps/makerspaces/limits_check.py:25` |
| events | `checkin_lists`: check-in lists on one event | none | 409 `checkin_lists_quota_reached` | `backend/apps/events/checkin_lists.py:27` |
| events | `event_badge_prints_monthly`: event badges printed this month | none | 409 `event_badge_prints_monthly_quota_reached` | `backend/apps/events/badge_prints.py:5` |
| events | `event_registrations_monthly`: event registrations and tickets this month | none | 409 `event_registrations_monthly_quota_reached` | `backend/apps/events/services_registration.py:171` |
| events | `events`: events | 10 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/events/services_lifecycle.py:64` |
| events | `events_monthly`: events created this month | none | 409 `event_quota_reached` | `backend/apps/makerspaces/limits_check.py:25` |
| events | `hackathon_stages`: submission stages on one hackathon | none | 409 `hackathon_stages_quota_reached` | `backend/apps/events/submissions/stage_rules.py:32` |
| events | `reimbursement_claims_monthly`: event reimbursement claims started this month | none | 409 `reimbursement_claims_monthly_quota_reached` | `backend/apps/event_reimbursements/claim_workflow.py:55` |
| events | `saved_views`: saved views per person on one event list | none | 409 `saved_views_quota_reached` | `backend/apps/operations/saved_view_events.py:1` |
| events | `series_invites`: series invite-list entries | none | 409 `series_invites_quota_reached` | `backend/apps/events/series_invites.py:23` |
| integrations | `analytics_connections`: analytics connections (Metabase or Grafana) | none | 409 `analytics_connections_quota_reached` | `backend/apps/analytics/services.py:85` |
| integrations | `api_clients`: API clients | 1 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/admin_api/api_client_views.py:101` |
| integrations | `api_requests_per_minute`: API requests per minute for each API client | none | 409 `api_requests_per_minute_quota_reached` | `backend/apps/apiclients/throttling.py:21` |
| integrations | `custom_domain`: custom domains | none | Custom-domain validation refuses the change | `backend/apps/makerspaces/limits_usage.py:18` |
| integrations | `data_exports`: active data exports | 1 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/data_export/services.py:43` |
| integrations | `report_exports_monthly`: report exports this month | none | 409 `report_exports_monthly_quota_reached` | `backend/apps/operations/report_download.py:25` |
| integrations | `scheduled_reports`: active scheduled reports | none | 409 `scheduled_reports_quota_reached` | `backend/apps/operations/views_report_schedules.py:112` |
| integrations | `webhook_endpoints`: outbound webhook endpoints | none | 409 `webhook_endpoints_quota_reached` | `backend/apps/admin_api/views_notification_destinations.py:90` |
| inventory | `assets`: assets | 2000 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/boxes/api_views_external.py:107` |
| inventory | `boxes`: QR boxes | none | 409 `boxes_quota_reached` | `backend/apps/boxes/api_views_qr.py:80` |
| inventory | `hardware_requests_monthly`: hardware requests submitted this month | none | 409 `hardware_requests_monthly_quota_reached` | `backend/apps/hardware_requests/request_workflow.py:62` |
| inventory | `kiosk_stations`: kiosk stations | none | 409 `kiosk_stations_quota_reached` | `backend/apps/makerspaces/kiosk_station_services.py:72` |
| inventory | `products`: products | 500 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/admin_api/serializers_inventory_products.py:165` |
| inventory | `shelf_checks_monthly`: shelf checks saved this month | none | 409 `shelf_checks_monthly_quota_reached` | `backend/apps/devices/services_shelf_check.py:51` |
| inventory | `stock_transfers_monthly`: stock transfers made this month | none | 409 `stock_transfers_monthly_quota_reached` | `backend/apps/operations/services_transfers.py:19` |
| inventory | `stocktake_sessions_monthly`: stocktake sessions started this month | none | 409 `stocktake_sessions_monthly_quota_reached` | `backend/apps/operations/services_stocktake_workflow.py:54` |
| machines | `adapter_artifacts`: adapter timelapses, previews and bundles kept | none | 409 `adapter_artifacts_quota_reached` | `backend/apps/devices/services_adapter_artifacts.py:7` |
| machines | `adapter_bridges`: enrolled device adapters (bridges) | none | 409 `adapter_bridges_quota_reached` | `backend/apps/devices/services_identity.py:31` |
| machines | `adapter_snapshots`: camera snapshots requested this month | none | 409 `adapter_snapshots_quota_reached` | `backend/apps/devices/services_adapter_watch.py:49` |
| machines | `adapter_telemetry_points`: device telemetry samples kept | none | 409 `adapter_telemetry_points_quota_reached` | `backend/apps/devices/services_adapter_history.py:72` |
| machines | `adapter_watch_streams`: camera watch sessions open at once | none | 409 `adapter_watch_streams_quota_reached` | `backend/apps/devices/services_adapter_media.py:162` |
| machines | `devices`: enrolled devices | none | 409 `devices_quota_reached` | `backend/apps/devices/services_identity.py:27` |
| machines | `machine_jobs_monthly`: machine jobs requested this month | none | 409 `machine_jobs_monthly_quota_reached` | `backend/apps/machines/service_workflow_actions.py:68` |
| machines | `machine_service_open`: open machine service requests | 100 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/machines/service_workflow_actions.py:65` |
| machines | `machine_service_submit`: daily machine service requests | 100 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/machines/service_workflow_actions.py:66` |
| machines | `machine_sessions_monthly`: machine sessions started this month | none | 409 `machine_sessions_monthly_quota_reached` | `backend/apps/machines/sessions_service.py:55` |
| machines | `machines`: machines | 5 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/admin_api/views_machines.py:36` |
| machines | `print`: monthly print requests | 200 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/machines/job_intake.py:68` |
| messaging | `discord`: daily Discord notifications | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `email`: daily emails | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/integrations/dispatch_outbox.py:35` |
| messaging | `mattermost`: daily Mattermost notifications | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `native_push`: daily native push notifications | 500 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `platform_email_monthly`: emails sent with the platform mail account this month | none | Delivery skipped / pass issuance refused | `backend/apps/integrations/dispatch_outbox.py:35` |
| messaging | `platform_push_monthly`: push deliveries (one per recipient or device) through the platform this month | none | Delivery skipped / pass issuance refused | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `platform_sms_monthly`: SMS sent with the platform SMS account this month | none | Delivery skipped / pass issuance refused | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `platform_wallet_monthly`: new wallet passes signed with the platform certificates this month | none | Delivery skipped / pass issuance refused | `backend/apps/card_designs/wallet/service.py:33` |
| messaging | `platform_whatsapp_monthly`: WhatsApp messages sent with the platform account this month | none | Delivery skipped / pass issuance refused | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `slack`: daily Slack notifications | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `sms`: daily SMS notifications | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `telegram`: daily Telegram notifications | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `webhook`: daily signed webhook deliveries | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| messaging | `whatsapp`: daily WhatsApp notifications | 100 | Delivery skipped when its daily allowance is spent | `backend/apps/makerspaces/limits_reservations.py:28` |
| money | `collection_sheet_rows_monthly`: collection sheet rows this month | none | 409 `collection_sheet_rows_monthly_quota_reached` | `backend/apps/payments/collection_sheet.py:11` |
| money | `donation_campaigns`: active donation campaigns and funds | none | 409 `donation_campaigns_quota_reached` | `backend/apps/payments/donations/views_staff.py:110` |
| money | `payments_monthly_amount`: money taken this month (per currency) | none | 409 `payment_quota_reached` | `backend/apps/payments/pricing/charging.py:50` |
| money | `payments_monthly_count`: paid transactions this month | none | 409 `payment_quota_reached` | `backend/apps/payments/pricing/charging.py:50` |
| money | `platform_payments_monthly_amount`: money taken through the platform rail this month (per currency) | none | 409 `platform_rail_limit_reached` | `backend/apps/payments/checkout_coordination.py:196` |
| money | `platform_payments_monthly_count`: online payments through the platform rail this month | none | 409 `platform_rail_limit_reached` | `backend/apps/payments/checkout_coordination.py:196` |
| people | `anthias_players`: registered Anthias display players | none | 409 `anthias_players_quota_reached` | `backend/apps/presence/views_anthias.py:114` |
| people | `card_templates`: saved card and certificate templates | none | 409 `card_templates_quota_reached` | `backend/apps/card_designs/templates.py:23` |
| people | `guest_passes`: guest and day passes issued per day | 100 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/makerspaces/guest_pass_issue.py:88` |
| people | `member_cards_issued_monthly`: member cards issued this month | none | 409 `member_cards_issued_monthly_quota_reached` | `backend/apps/makerspaces/member_card_services.py:76` |
| people | `member_units`: member units (districts, chapters, branches) | none | 409 `member_units_quota_reached` | `backend/apps/makerspaces/member_units.py:25` |
| people | `members`: members | 25 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/makerspaces/membership_activation.py:74` |
| people | `membership_plans`: membership plans | none | 409 `membership_plans_quota_reached` | `backend/apps/admin_api/views_membership_plans.py:20` |
| people | `organizations_linked`: linked organizations | none | 409 `organizations_linked_quota_reached` | `backend/apps/organizations/services_owner.py:77` |
| people | `paired_displays`: paired space display screens | none | 409 `paired_displays_quota_reached` | `backend/apps/presence/display_pairing.py:39` |
| people | `photo_cutout_jobs_monthly`: card photo background-removal jobs this month | none | 409 `photo_cutout_jobs_monthly_quota_reached` | `backend/apps/card_designs/cutouts.py:4` |
| people | `staff`: staff members | 10 | 400 `limit_reached` / `plan_limit_reached` | `backend/apps/accounts/staff_account_policy.py:149` |
| people | `staff_cards_issued_monthly`: staff ID cards issued this month | none | 409 `staff_cards_issued_monthly_quota_reached` | `backend/apps/card_designs/staff_card_services.py:25` |
| people | `wallet_passes`: member and event wallet passes | none | 409 `wallet_passes_quota_reached` | `backend/apps/card_designs/wallet/service.py:54` |
| shop | `shop_orders_monthly`: shop orders this month | none | 409 `shop_orders_monthly_quota_reached` | `backend/apps/shop/orders_core.py:44` |
| shop | `shop_products`: shop products | none | 409 `shop_products_quota_reached` | `backend/apps/shop/services_catalogue.py:117` |
| storage | `adapter_media_bytes`: storage used by device adapter timelapses, previews and bundles | none | 409 `adapter_media_bytes_quota_reached` | `backend/apps/devices/services_adapter_artifacts.py:114` |
| storage | `public_page_assets`: images on the public space page | none | 409 `public_page_assets_quota_reached` | `backend/apps/makerspaces/public_page_assets.py:61` |
| storage | `storage`: storage | 1073741824 | 400 `upload_limit` (upload); other storage writers use their own refusal | `backend/apps/makerspaces/limits_uploads.py:50` |
| storage | `storage_evidence_bytes`: storage used by evidence photos | none | 409 `storage_evidence_bytes_quota_reached` | `backend/apps/makerspaces/limits_uploads.py:59` |
| storage | `storage_public_images_bytes`: storage used by public images and other non-evidence files | none | 409 `storage_public_images_bytes_quota_reached` | `backend/apps/makerspaces/limits_uploads.py:59` |
| storage | `upload_bytes`: largest single upload | none | 400 `upload_limit` (upload); other storage writers use their own refusal | `backend/apps/makerspaces/limits_uploads.py:31` |

## Verification scope

The registry below contains 81 keys. The CX7 boundary inventory maps each key to a shared-gate,
worker or HTTP regression; tests written during fix pass 1 have not been executed in this lane.
A shared-gate test is not proof that every creator reaches it. Browser and attested Android/iOS
API regressions additionally cover inventory and machine creation, shop catalogue capacity and
merged basket quantities; the HMAC rate regression exercises an actual HTTP 429.

The native repositories were inspected read-only: both preserve status, error code and display
message, and both currently have no shop screen. The native API tests do not assert that such a
screen exists. The shop's Django `/control/` records are read-only. Inventory and machine Django
admin forms still require review because their raw model-save paths do not call the same quota
services. Full route/form boundary coverage, concurrency review and runtime sign-off remain open.
The declaration appendix is discovery data, not a statement that all 5,287 declarations have
passing max/max+1 tests. Existing field bodies and frozen pricing agreements stay intact (509).

## Deployment settings, throttles and validation declarations

The indexes below are taken from current Python declarations, excluding migrations. They preserve
identifiers so an operator can locate the setting. Environment defaults are deployment-wide, and are
the same on managed and self-host unless the declaration explicitly selects a hosting mode. Settings
with no default must be supplied by the operator. These indexes are discovery evidence, not test results.

For serializer bounds the server's 400 response names the field; the standard maximum messages are
“Ensure this value is less than or equal to …”, “Ensure this field has no more than … characters”, and
“Ensure this field has no more than … elements.” Model constraints also protect direct Django writes;
they do not prove that every admin form/API serializer maps the failure to a typed response.

<details>
<summary>accounts (301 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_RESENDS` | `3` | fixed / see setting | `backend/apps/accounts/account_merge_proofs.py:36` |
| `MfaResetForm.reason (forms.CharField)` | `min_length=3, max_length=300` | field / model | `backend/apps/accounts/admin_mfa_reset.py:19` |
| `PiiReasonForm.reason (forms.CharField)` | `min_length=10, max_length=300` | field / model | `backend/apps/accounts/admin_pii_access.py:29` |
| `DisableAccountForm.reason (forms.CharField)` | `min_length=3, max_length=200` | field / model | `backend/apps/accounts/admin_staff_lifecycle.py:25` |
| `MAX_SPACES` | `20` | fixed / see setting | `backend/apps/accounts/channel_activity.py:25` |
| `COOKIE_MAX_AGE` | `400 * 86400` | fixed / see setting | `backend/apps/accounts/device_memory.py:30` |
| `DEVICE_FAILURE_LIMIT` | `10` | fixed / see setting | `backend/apps/accounts/ip_guard.py:34` |
| `_BODY_LIMIT` | `16 * 1024` | fixed / see setting | `backend/apps/accounts/ip_guard_middleware.py:37` |
| `MAX_RESENDS` | `2` | fixed / see setting | `backend/apps/accounts/login_code_flow.py:22` |
| `MAX_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/accounts/login_codes.py:18` |
| `STAFF_SESSION_MAX_HOURS` | `SecuritySetting('security.staff_session_max_hours', 'Staff session length (hours)', INT, 168, lower_is_stricter, storage=POLICY, scope=STAFF_STRICTEST, minimum=1, maximum=720, description='Staff sign in again after this long, however active they are.')` | fixed / see setting | `backend/apps/accounts/login_security_settings.py:70` |
| `AccountMergeRecord.decision (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_account_merge.py:40` |
| `AccountMergeRecord.proof_method (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_account_merge.py:45` |
| `AccountMergeRecord.plan_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_merge.py:47` |
| `AccountMergeRecord.snapshot_scheme (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_account_merge.py:48` |
| `AccountMergeRecord.state (models.CharField)` | `max_length=16; default=State.PENDING` | field / model | `backend/apps/accounts/models_account_merge.py:55` |
| `AccountMergeIntent.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_account_merge.py:99` |
| `AccountMergeIntent.identifier_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_merge.py:100` |
| `AccountMergeIntent.survivor_code_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_merge.py:101` |
| `AccountMergeIntent.source_code_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_merge.py:102` |
| `AccountMergeIntent.preview_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_merge.py:109` |
| `AccountMergeIntent.state (models.CharField)` | `max_length=16; default=State.STARTED` | field / model | `backend/apps/accounts/models_account_merge.py:110` |
| `AccountPurgeObject.bucket (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_account_purge.py:24` |
| `AccountPurgeObject.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/accounts/models_account_purge.py:25` |
| `AccountPurgeObject.last_error (models.CharField)` | `max_length=128; default=''` | field / model | `backend/apps/accounts/models_account_purge.py:30` |
| `AppleRefreshCredential.client_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_account_purge.py:40` |
| `AppleRevocation.client_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_account_purge.py:54` |
| `AppleRevocation.last_error (models.CharField)` | `max_length=128; default=''` | field / model | `backend/apps/accounts/models_account_purge.py:60` |
| `AccountRestoreIntent.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_restore.py:9` |
| `AccountRestoreIntent.credential_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_restore.py:10` |
| `AccountRestoreIntent.provider (models.CharField)` | `max_length=100` | field / model | `backend/apps/accounts/models_account_restore.py:11` |
| `AccountRestoreIntent.nonce_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_account_restore.py:12` |
| `AccountRestoreIntent.origin (models.CharField)` | `max_length=500` | field / model | `backend/apps/accounts/models_account_restore.py:13` |
| `AccountRestoreIntent.redirect_uri (models.URLField)` | `max_length=1000` | field / model | `backend/apps/accounts/models_account_restore.py:14` |
| `AccountRestoreIntent.delivery (models.CharField)` | `max_length=16; default='web'` | field / model | `backend/apps/accounts/models_account_restore.py:16` |
| `AccountRestoreIntent.client_platform (models.CharField)` | `max_length=16; default='web'` | field / model | `backend/apps/accounts/models_account_restore.py:17` |
| `DeviceActivityDay.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_activity.py:9` |
| `DeviceActivityDay.app_version (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/accounts/models_activity.py:11` |
| `WebSessionActivityDay.session_hash (models.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/models_activity.py:27` |
| `ChannelUsageDay.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_activity.py:45` |
| `ChannelUsageDay.area (models.CharField)` | `max_length=48` | field / model | `backend/apps/accounts/models_activity.py:46` |
| `AttestationVerificationLog.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_activity.py:59` |
| `AttestationVerificationLog.mode (models.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/models_activity.py:60` |
| `AttestationVerificationLog.outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_activity.py:61` |
| `PlatformAttestationSettings.app_display_name (models.CharField)` | `max_length=100; default='SpaceWorks'` | field / model | `backend/apps/accounts/models_attestation.py:15` |
| `MemberClaimCode.code_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_claim.py:15` |
| `NativeAppRegistration.app_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:31` |
| `NativeAppRegistration.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_devices.py:32` |
| `NativeAppRegistration.environment (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_devices.py:33` |
| `NativeAppRegistration.verifier_config_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:36` |
| `NativeAppRegistration.min_supported_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_devices.py:38` |
| `NativeAppRegistration.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/accounts/models_devices.py:39` |
| `DeviceAttestationChallenge.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_devices.py:87` |
| `DeviceAttestationChallenge.app_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:88` |
| `DeviceAttestationChallenge.signing_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:89` |
| `DeviceAttestationChallenge.environment (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_devices.py:91` |
| `DeviceAttestationChallenge.challenge_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_devices.py:92` |
| `DeviceGrant.status (models.CharField)` | `max_length=16; default=Status.ACTIVE` | field / model | `backend/apps/accounts/models_devices.py:122` |
| `DeviceGrant.authority (models.CharField)` | `max_length=16; default=Authority.MEMBER` | field / model | `backend/apps/accounts/models_devices.py:123` |
| `DeviceGrant.login_method (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/accounts/models_devices.py:130` |
| `DeviceGrant.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_devices.py:133` |
| `DeviceGrant.app_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:134` |
| `DeviceGrant.signing_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:135` |
| `DeviceGrant.environment (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_devices.py:136` |
| `DeviceGrant.attestation_subject_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_devices.py:137` |
| `DeviceGrant.attestation_key_id (models.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/models_devices.py:138` |
| `DeviceRefreshToken.jti (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_devices.py:185` |
| `DeviceRefreshToken.token_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_devices.py:186` |
| `EmailVerificationChallenge.email (models.CharField)` | `max_length=254` | field / model | `backend/apps/accounts/models_email.py:10` |
| `EmailVerificationChallenge.code_digest (models.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/models_email.py:11` |
| `EmailVerificationChallenge.requested_handle (models.CharField)` | `max_length=30; default=''` | field / model | `backend/apps/accounts/models_email.py:18` |
| `IPAccessRule.cidr (models.CharField)` | `max_length=49` | field / model | `backend/apps/accounts/models_ip_access.py:17` |
| `IPAccessRule.action (models.CharField)` | `max_length=8` | field / model | `backend/apps/accounts/models_ip_access.py:18` |
| `IPAccessRule.note (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/accounts/models_ip_access.py:19` |
| `IPAutoBlock.ip_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_ip_access.py:36` |
| `IPAutoBlock.network (models.CharField)` | `max_length=49` | field / model | `backend/apps/accounts/models_ip_access.py:38` |
| `KnownDevice.device_hmac (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_login_risk.py:18` |
| `KnownDevice.ua_label (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/accounts/models_login_risk.py:19` |
| `KnownNetwork.granularity (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_login_risk.py:35` |
| `KnownNetwork.prefix_hmac (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_login_risk.py:36` |
| `SecurityAlert.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/accounts/models_login_risk.py:57` |
| `SecurityAlert.nonce_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_login_risk.py:58` |
| `SecurityAlert.network_label (models.CharField)` | `max_length=120` | field / model | `backend/apps/accounts/models_login_risk.py:59` |
| `SecurityAlert.ua_label (models.CharField)` | `max_length=120` | field / model | `backend/apps/accounts/models_login_risk.py:60` |
| `MFAChallenge.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_mfa.py:20` |
| `MFAChallenge.credential_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_mfa.py:21` |
| `MFAChallenge.auth_generation (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_mfa.py:22` |
| `StaffMfaGrace.source (models.CharField)` | `max_length=8` | field / model | `backend/apps/accounts/models_mfa_grace.py:21` |
| `OidcProvider.slug (models.SlugField)` | `max_length=40` | field / model | `backend/apps/accounts/models_oidc.py:45` |
| `OidcProvider.display_name (models.CharField)` | `max_length=80` | field / model | `backend/apps/accounts/models_oidc.py:46` |
| `OidcProvider.issuer (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_oidc.py:50` |
| `OidcProvider.jwks_url (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_oidc.py:51` |
| `OidcProvider.client_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_oidc.py:53` |
| `OidcBrowserAttempt.provider (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_oidc_browser.py:9` |
| `OidcBrowserAttempt.surface (models.CharField)` | `max_length=16; default=SocialSurface.MEMBER` | field / model | `backend/apps/accounts/models_oidc_browser.py:10` |
| `OidcBrowserAttempt.state_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_oidc_browser.py:11` |
| `OidcBrowserAttempt.nonce_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_oidc_browser.py:12` |
| `OidcBrowserAttempt.code_verifier (models.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/models_oidc_browser.py:13` |
| `OidcBrowserAttempt.redirect_uri (models.CharField)` | `max_length=2048` | field / model | `backend/apps/accounts/models_oidc_browser.py:14` |
| `OidcBrowserAttempt.origin (models.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/models_oidc_browser.py:15` |
| `OidcBrowserAttempt.next_path (models.CharField)` | `max_length=512; default=''` | field / model | `backend/apps/accounts/models_oidc_browser.py:17` |
| `PasswordResetEnvelope.purpose (models.CharField)` | `max_length=16; default='reset'` | field / model | `backend/apps/accounts/models_password_reset.py:26` |
| `PasswordResetEnvelope.email_normalized (models.CharField)` | `max_length=254` | field / model | `backend/apps/accounts/models_password_reset.py:27` |
| `PasswordResetEnvelope.context (models.CharField)` | `max_length=8; default='member'` | field / model | `backend/apps/accounts/models_password_reset.py:28` |
| `PasswordResetEnvelope.request_origin (models.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/models_password_reset.py:30` |
| `PasswordResetEnvelope.email_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_password_reset.py:32` |
| `PasswordResetEnvelope.digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_password_reset.py:33` |
| `PasswordResetEnvelope.credential_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_password_reset.py:35` |
| `PasswordResetEnvelope.status (models.CharField)` | `max_length=20; default=PasswordResetEnvelopeStatus.PENDING` | field / model | `backend/apps/accounts/models_password_reset.py:44` |
| `PasswordResetEnvelope.claim_owner (models.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/models_password_reset.py:50` |
| `PhoneVerificationChallenge.purpose (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_phone.py:28` |
| `PhoneVerificationChallenge.phone_e164 (models.CharField)` | `max_length=20` | field / model | `backend/apps/accounts/models_phone.py:39` |
| `PhoneVerificationChallenge.code_digest (models.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/models_phone.py:40` |
| `PhoneVerificationChallenge.credential_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/accounts/models_phone.py:41` |
| `PlatformPiiAccessGrant.reason (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/models_pii_access.py:37` |
| `PlatformPiiAccessGrant.close_reason (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/accounts/models_pii_access.py:41` |
| `ReauthenticationSession.session_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/models_reauthentication.py:9` |
| `ReauthenticationSession.surface (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_reauthentication.py:10` |
| `ReauthenticationSession.auth_generation (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_reauthentication.py:11` |
| `ReauthenticationSession.credential_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_reauthentication.py:12` |
| `ReauthenticationSession.mfa_version (models.CharField)` | `max_length=36` | field / model | `backend/apps/accounts/models_reauthentication.py:13` |
| `SocialIdentity.provider (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_social.py:38` |
| `SocialIdentity.provider_sub (models.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/models_social.py:39` |
| `SocialLoginNonce.provider (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_social.py:58` |
| `SocialLoginNonce.surface (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_social.py:59` |
| `SocialLoginNonce.delivery (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_social.py:60` |
| `SocialLoginNonce.client_platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_social.py:61` |
| `SocialLoginNonce.nonce_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_social.py:64` |
| `SocialLoginNonce.origin (models.CharField)` | `max_length=512; default=''` | field / model | `backend/apps/accounts/models_social.py:65` |
| `PlatformSocialAuthSettings.google_web_client_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/accounts/models_social.py:121` |
| `PlatformSocialAuthSettings.google_ios_client_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/accounts/models_social.py:122` |
| `PlatformSocialAuthSettings.google_android_client_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/accounts/models_social.py:123` |
| `PlatformSocialAuthSettings.apple_service_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/accounts/models_social.py:124` |
| `PlatformSocialAuthSettings.apple_team_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/accounts/models_social.py:126` |
| `PlatformSocialAuthSettings.apple_key_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/accounts/models_social.py:127` |
| `PlatformSocialAuthSettings.github_client_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/accounts/models_social.py:129` |
| `StaffInvitation.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_staff_invitations.py:19` |
| `User.account_kind (models.CharField)` | `max_length=16; default=AccountKind.MEMBER` | field / model | `backend/apps/accounts/models_user.py:26` |
| `User.deletion_username (models.CharField)` | `max_length=150; default=''` | field / model | `backend/apps/accounts/models_user.py:45` |
| `User.phone (models.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/models_user.py:59` |
| `User.phone_e164 (models.CharField)` | `max_length=20` | field / model | `backend/apps/accounts/models_user.py:65` |
| `User.display_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/models_user.py:67` |
| `User.preferred_locale (models.CharField)` | `max_length=16; default=None` | field / model | `backend/apps/accounts/models_user.py:70` |
| `User.telegram_user_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/models_user.py:78` |
| `User.role (models.CharField)` | `max_length=32; default=Role.REQUESTER` | field / model | `backend/apps/accounts/models_user.py:91` |
| `User.access_status (models.CharField)` | `max_length=32; default=AccessStatus.ACTIVE` | field / model | `backend/apps/accounts/models_user.py:96` |
| `WebAuthnCredential.credential_id (models.CharField)` | `max_length=1366` | field / model | `backend/apps/accounts/models_webauthn.py:22` |
| `WebAuthnCredential.aaguid (models.CharField)` | `max_length=36; default=''` | field / model | `backend/apps/accounts/models_webauthn.py:26` |
| `WebAuthnCredential.rp_id (models.CharField)` | `max_length=253` | field / model | `backend/apps/accounts/models_webauthn.py:28` |
| `WebAuthnCredential.name (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/accounts/models_webauthn.py:29` |
| `WebAuthnCeremony.purpose (models.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/models_webauthn.py:48` |
| `WebAuthnCeremony.challenge (models.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/models_webauthn.py:51` |
| `WebAuthnCeremony.rp_id (models.CharField)` | `max_length=253` | field / model | `backend/apps/accounts/models_webauthn.py:52` |
| `WebAuthnCeremony.origin (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/models_webauthn.py:53` |
| `MAX_PASSKEYS` | `10` | fixed / see setting | `backend/apps/accounts/passkeys/ceremonies.py:27` |
| `PasskeyRenameSerializer.name (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/passkeys/serializers.py:34` |
| `PasskeyMfaOptionsRequestSerializer.challenge (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/passkeys/serializers.py:43` |
| `PasskeyRegisterRequestSerializer.name (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/accounts/passkeys/serializers.py:52` |
| `MAX_NEXT_LENGTH` | `512` | fixed / see setting | `backend/apps/accounts/safe_next.py:12` |
| `MemberSavedDetail.field_key (models.CharField)` | `max_length=40` | field / model | `backend/apps/accounts/saved_details/models.py:15` |
| `MemberSavedDetail.value_type (models.CharField)` | `max_length=20` | field / model | `backend/apps/accounts/saved_details/models.py:17` |
| `MemberSavedAsset.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/saved_details/models.py:32` |
| `MemberSavedAsset.staging_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/saved_details/models.py:33` |
| `MemberSavedAsset.verification_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/saved_details/models.py:34` |
| `MemberSavedAsset.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/saved_details/models.py:36` |
| `MemberSavedAsset.canonical_mime (models.CharField)` | `max_length=100; default='application/pdf'` | field / model | `backend/apps/accounts/saved_details/models.py:38` |
| `MemberSavedAsset.state (models.CharField)` | `max_length=20; default='uploading'` | field / model | `backend/apps/accounts/saved_details/models.py:39` |
| `MemberSavedAsset.scan_status (models.CharField)` | `max_length=30; default='pending'` | field / model | `backend/apps/accounts/saved_details/models.py:42` |
| `MemberSavedAsset.source_version_id (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/saved_details/models.py:46` |
| `MemberSavedAsset.final_version_id (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/saved_details/models.py:47` |
| `MemberSavedAsset.failure_code (models.CharField)` | `max_length=50` | field / model | `backend/apps/accounts/saved_details/models.py:48` |
| `SavedDetailUpdateIntent.subject_kind (models.CharField)` | `max_length=20` | field / model | `backend/apps/accounts/saved_details/models.py:65` |
| `SavedDetailUpdateIntent.state (models.CharField)` | `max_length=10; default='pending'` | field / model | `backend/apps/accounts/saved_details/models.py:72` |
| `SavedDetailUpdateIntent.failure_code (models.CharField)` | `max_length=50` | field / model | `backend/apps/accounts/saved_details/models.py:74` |
| `SavedDetailCommandReceipt.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/saved_details/models.py:91` |
| `AccountSavedDetailsExportJob.state (models.CharField)` | `max_length=10; default='queued'` | field / model | `backend/apps/accounts/saved_details/models.py:103` |
| `AccountSavedDetailsExportJob.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/accounts/saved_details/models.py:104` |
| `AccountSavedDetailsExportJob.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/saved_details/models.py:106` |
| `AccountSavedDetailsExportJob.failure_code (models.CharField)` | `max_length=50` | field / model | `backend/apps/accounts/saved_details/models.py:110` |
| `SavedVaultCommand.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/accounts/saved_details/serializers.py:15` |
| `SavedVaultPrefillSelector.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:55` |
| `SavedVaultPrefillSelector.makerspace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:56` |
| `SavedVaultPrefillSelector.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:58` |
| `SavedVaultPrefillSelector.posting_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:59` |
| `SavedVaultPrefillSelector.stage_form_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:60` |
| `SavedVaultPrefillInput.form_id (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/accounts/saved_details/serializers.py:76` |
| `SavedVaultPrefillInput.form_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:77` |
| `SavedVaultPrefillInput.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:78` |
| `SavedVaultResumeInput.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/accounts/saved_details/serializers.py:91` |
| `SavedVaultResumeInput.bytes (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:92` |
| `SavedVaultCompleteInput.generation (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/saved_details/serializers.py:97` |
| `MAX_RESUME_BYTES` | `10 * 1024 ** 2` | fixed / see setting | `backend/apps/accounts/saved_details/storage.py:17` |
| `AccountDeletionBlockerSerializer.count (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/serializers_account_deletion.py:13` |
| `MergeStartRequestSerializer.identifier (serializers.CharField)` | `max_length=254` | field / model | `backend/apps/accounts/serializers_account_merge.py:13` |
| `MergeProveRequestSerializer.password (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/accounts/serializers_account_merge.py:26` |
| `MergeProveRequestSerializer.otp (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/serializers_account_merge.py:28` |
| `MergeProveRequestSerializer.survivor_code (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/serializers_account_merge.py:34` |
| `MergeProveRequestSerializer.source_code (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/accounts/serializers_account_merge.py:36` |
| `MergePasskeyOptionsRequestSerializer.password (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/accounts/serializers_account_merge.py:41` |
| `MergeConfirmRequestSerializer.preview_sha256 (serializers.CharField)` | `max_length=64, min_length=64` | field / model | `backend/apps/accounts/serializers_account_merge.py:100` |
| `AccountRestoreEmailSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/accounts/serializers_account_restore.py:10` |
| `AccountRestoreEmailSerializer.token (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_account_restore.py:11` |
| `AccountRestoreEmailSerializer.new_password (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/serializers_account_restore.py:12` |
| `AccountRestorePhoneSerializer.new_password (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/serializers_account_restore.py:16` |
| `AccountRestoreSocialStartSerializer.username (serializers.CharField)` | `max_length=150` | field / model | `backend/apps/accounts/serializers_account_restore.py:21` |
| `AccountRestoreSocialStartSerializer.provider (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/accounts/serializers_account_restore.py:22` |
| `AccountRestoreSocialStartSerializer.redirect_uri (serializers.URLField)` | `max_length=1000; default=''` | field / model | `backend/apps/accounts/serializers_account_restore.py:23` |
| `AccountRestoreSocialCompleteSerializer.state (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_account_restore.py:27` |
| `AccountRestoreSocialCompleteSerializer.nonce (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_account_restore.py:28` |
| `AccountRestoreSocialCompleteSerializer.id_token (serializers.CharField)` | `max_length=16384; default=''` | field / model | `backend/apps/accounts/serializers_account_restore.py:29` |
| `AccountRestoreSocialCompleteSerializer.code (serializers.CharField)` | `max_length=4096; default=''` | field / model | `backend/apps/accounts/serializers_account_restore.py:30` |
| `AccountRestoreSocialCompleteSerializer.challenge (serializers.CharField)` | `max_length=512; default=''` | field / model | `backend/apps/accounts/serializers_account_restore.py:31` |
| `ClaimRedemptionSerializer.code (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/serializers_claim.py:7` |
| `ClaimRedemptionSerializer.makerspace_slug (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/accounts/serializers_claim.py:8` |
| `DeviceIdentitySerializer.app_id (serializers.RegexField)` | `max_length=255` | field / model | `backend/apps/accounts/serializers_device.py:10` |
| `DeviceLoginSerializer.makerspace (serializers.SlugField)` | `max_length=150` | field / model | `backend/apps/accounts/serializers_device.py:24` |
| `DeviceLoginSerializer.username (serializers.CharField)` | `max_length=254` | field / model | `backend/apps/accounts/serializers_device.py:26` |
| `DeviceLoginSerializer.password (serializers.CharField)` | `max_length=1024` | field / model | `backend/apps/accounts/serializers_device.py:27` |
| `DeviceLoginSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_device.py:28` |
| `DeviceLoginSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_device.py:30` |
| `DeviceStaffGrantSerializer.makerspace (serializers.SlugField)` | `max_length=150` | field / model | `backend/apps/accounts/serializers_device.py:47` |
| `DeviceStaffGrantSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_device.py:48` |
| `DeviceStaffGrantSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_device.py:51` |
| `DeviceEventGrantSerializer.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/serializers_device.py:61` |
| `DeviceEventGrantSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_device.py:62` |
| `DeviceEventGrantSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_device.py:65` |
| `DeviceRefreshSerializer.refresh (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/accounts/serializers_device.py:74` |
| `DeviceRefreshSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_device.py:75` |
| `DeviceChallengeResponseSerializer.expires_in (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/accounts/serializers_device.py:114` |
| `GithubBrowserStartSerializer.redirect_uri (serializers.URLField)` | `max_length=2048` | field / model | `backend/apps/accounts/serializers_github.py:6` |
| `GithubNativeStartSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_github_native.py:28` |
| `GithubNativeExchangeSerializer.code (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_github_native.py:45` |
| `GithubNativeExchangeSerializer.state (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_github_native.py:46` |
| `GithubNativeExchangeSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_github_native.py:49` |
| `GithubNativeExchangeSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_github_native.py:51` |
| `MFAChallengeSerializer.challenge (serializers.CharField)` | `min_length=20, max_length=200` | field / model | `backend/apps/accounts/serializers_mfa.py:25` |
| `MFAVerifySerializer.code (serializers.CharField)` | `min_length=6, max_length=64` | field / model | `backend/apps/accounts/serializers_mfa.py:34` |
| `MFAPasswordSerializer.password (serializers.CharField)` | `max_length=1024` | field / model | `backend/apps/accounts/serializers_mfa.py:68` |
| `MFAEnrollmentStartSerializer.password (serializers.CharField)` | `max_length=1024; default=''` | field / model | `backend/apps/accounts/serializers_mfa.py:72` |
| `OidcBrowserStartSerializer.redirect_uri (serializers.URLField)` | `max_length=2048` | field / model | `backend/apps/accounts/serializers_oidc_browser.py:8` |
| `SocialLinkStartSerializer.redirect_uri (serializers.URLField)` | `max_length=2048` | field / model | `backend/apps/accounts/serializers_oidc_browser.py:16` |
| `OidcBrowserCallbackSerializer.code (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/accounts/serializers_oidc_browser.py:27` |
| `OidcBrowserCallbackSerializer.state (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_oidc_browser.py:28` |
| `OidcBrowserCallbackSerializer.nonce (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_oidc_browser.py:29` |
| `RecoveryContextSerializer.email (serializers.CharField)` | `max_length=254` | field / model | `backend/apps/accounts/serializers_password_reset.py:20` |
| `ResetPasswordConfirmSerializer.email (serializers.CharField)` | `max_length=254` | field / model | `backend/apps/accounts/serializers_password_reset.py:52` |
| `PhoneStartSerializer.phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_phone.py:10` |
| `PhoneConfirmSerializer.phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_phone.py:14` |
| `PhoneConfirmSerializer.code (serializers.CharField)` | `min_length=6, max_length=6` | field / model | `backend/apps/accounts/serializers_phone.py:17` |
| `PhoneLoginStartSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_phone.py:25` |
| `PhoneLoginConfirmSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_phone.py:42` |
| `ReauthenticationSerializer.password (serializers.CharField)` | `max_length=1024; default=''` | field / model | `backend/apps/accounts/serializers_reauthentication.py:5` |
| `ReauthenticationSerializer.code (serializers.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/accounts/serializers_reauthentication.py:6` |
| `ReauthenticationSocialStartSerializer.provider (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/accounts/serializers_reauthentication.py:28` |
| `ReauthenticationSocialStartSerializer.redirect_uri (serializers.URLField)` | `max_length=2048; default=''` | field / model | `backend/apps/accounts/serializers_reauthentication.py:29` |
| `ReauthenticationSocialCompleteSerializer.state (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_reauthentication.py:40` |
| `ReauthenticationSocialCompleteSerializer.nonce (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_reauthentication.py:41` |
| `ReauthenticationSocialCompleteSerializer.id_token (serializers.CharField)` | `max_length=16384; default=''` | field / model | `backend/apps/accounts/serializers_reauthentication.py:42` |
| `ReauthenticationSocialCompleteSerializer.code (serializers.CharField)` | `max_length=2048; default=''` | field / model | `backend/apps/accounts/serializers_reauthentication.py:43` |
| `ReauthenticationSocialCompleteSerializer.totp (serializers.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/accounts/serializers_reauthentication.py:44` |
| `ReauthenticationEmailConfirmSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_reauthentication.py:48` |
| `ReauthenticationFactorSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_reauthentication.py:64` |
| `ReauthenticationFactorSerializer.code (serializers.RegexField)` | `max_length=6` | field / model | `backend/apps/accounts/serializers_reauthentication.py:65` |
| `MemberSignUpSerializer.display_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_registration.py:6` |
| `MemberSignUpSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/accounts/serializers_registration.py:7` |
| `MemberSignUpSerializer.phone (serializers.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/accounts/serializers_registration.py:8` |
| `MemberSignUpSerializer.password (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/accounts/serializers_registration.py:9` |
| `MemberSignUpSerializer.handle (serializers.CharField)` | `max_length=30; default=''` | field / model | `backend/apps/accounts/serializers_registration.py:14` |
| `EmailVerificationConfirmSerializer.code (serializers.CharField)` | `max_length=6` | field / model | `backend/apps/accounts/serializers_registration.py:41` |
| `SocialProviderKeyField.super().__init__` | `max_length=64` | field / model | `backend/apps/accounts/serializers_social.py:17` |
| `SocialNonceSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_social.py:34` |
| `SocialLoginSerializer.authorization_code (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/accounts/serializers_social.py:57` |
| `SocialLoginSerializer.redirect_uri (serializers.URLField)` | `max_length=2048; default=''` | field / model | `backend/apps/accounts/serializers_social.py:59` |
| `SocialLoginSerializer.id_token (serializers.CharField)` | `max_length=16384` | field / model | `backend/apps/accounts/serializers_social.py:61` |
| `SocialLoginSerializer.nonce (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_social.py:62` |
| `SocialLoginSerializer.apple_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_social.py:66` |
| `SocialLoginSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_social.py:69` |
| `SocialLoginSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/serializers_social.py:73` |
| `SocialLinkSerializer.id_token (serializers.CharField)` | `max_length=16384` | field / model | `backend/apps/accounts/serializers_social.py:109` |
| `SocialLinkSerializer.nonce (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/serializers_social.py:110` |
| `SocialLinkSerializer.apple_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/accounts/serializers_social.py:114` |
| `StaffInvitationAcceptSerializer.token (serializers.CharField)` | `min_length=20, max_length=200` | field / model | `backend/apps/accounts/serializers_staff_invitations.py:46` |
| `StaffInvitationAcceptSerializer.code (serializers.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/accounts/serializers_staff_invitations.py:48` |
| `MAX_FAILED_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/accounts/services_challenge_purge.py:24` |
| `MAX_FAILED_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/accounts/services_claim.py:25` |
| `MAX_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/accounts/services_password_reset.py:24` |
| `MAX_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/accounts/services_password_reset_confirmation.py:17` |
| `MAX_FAILED_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/accounts/services_phone.py:46` |
| `_LIMIT` | `ContextVar('staff_authority_limit', default=None)` | fixed / see setting | `backend/apps/accounts/session_authority.py:19` |
| `SessionContextSerializer.context (serializers.RegexField)` | `max_length=16; default=PERSON` | field / model | `backend/apps/accounts/session_context.py:20` |
| `MAX_FAILURES` | `5` | fixed / see setting | `backend/apps/accounts/staff_invitation_acceptance.py:41` |
| `MAX_ATTEMPTS` | `8` | fixed / see setting | `backend/apps/accounts/username_allocation.py:10` |
| `DevicePasskeyOptionsSerializer.challenge (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/views_device_passkey.py:39` |
| `DevicePasskeyLoginSerializer.app_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/accounts/views_device_passkey.py:48` |
| `LoginCodeResendSerializer.challenge (serializers.CharField)` | `min_length=20, max_length=200` | field / model | `backend/apps/accounts/views_login_codes.py:35` |
| `LogoutAllResponseSerializer.web_sessions (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/accounts/views_logout_all.py:22` |
| `LogoutAllResponseSerializer.devices (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/accounts/views_logout_all.py:25` |
| `StaffMfaResetRequestSerializer.reason (serializers.CharField)` | `min_length=3, max_length=300` | field / model | `backend/apps/accounts/views_mfa_reset.py:23` |
| `AccountActionReasonSerializer.reason (serializers.CharField)` | `min_length=3, max_length=300` | field / model | `backend/apps/accounts/views_platform_accounts.py:47` |
| `UnblockResultSerializer.unblocked (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/accounts/views_platform_ip_access.py:78` |
| `NotMeRequestSerializer.token (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/accounts/views_security_alerts.py:18` |

</details>

<details>
<summary>admin_api (214 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `ApiIntegrationSettingsSerializer.slack_webhook_url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/api_client_serializers_integrations.py:26` |
| `ApiIntegrationSettingsSerializer.mattermost_webhook_url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/api_client_serializers_integrations.py:29` |
| `ApiIntegrationSettingsSerializer.discord_webhook_url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/api_client_serializers_integrations.py:32` |
| `MAX_IDS` | `50` | fixed / see setting | `backend/apps/admin_api/bulk_decisions.py:21` |
| `BulkIds.ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/bulk_decisions.py:36` |
| `BulkIds.ids (serializers.ListField)` | `max_length=MAX_IDS` | field / model | `backend/apps/admin_api/bulk_decisions.py:36` |
| `BulkIds.reason (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/admin_api/bulk_decisions.py:37` |
| `MAX_IMPORT_ROWS` | `5000` | fixed / see setting | `backend/apps/admin_api/bulk_import_parsers.py:5` |
| `MAX_IMPORT_UPLOAD_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/admin_api/bulk_import_parsers.py:6` |
| `MAX_IMPORT_COLUMNS` | `100` | fixed / see setting | `backend/apps/admin_api/bulk_import_sheet.py:24` |
| `ImportSourceSerializer.url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/import_sources.py:31` |
| `MAX_REDIRECTS` | `5` | fixed / see setting | `backend/apps/admin_api/import_sources_sheets.py:44` |
| `identity_filter.field (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/admin_api/list_options.py:19` |
| `BulkImportJob.mode (models.CharField)` | `max_length=20` | field / model | `backend/apps/admin_api/models.py:26` |
| `BulkImportJob.status (models.CharField)` | `max_length=20; default=Status.PENDING` | field / model | `backend/apps/admin_api/models.py:27` |
| `RecipientRulesPutSerializer.feature (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/admin_api/recipient_rule_serializers.py:24` |
| `RecipientRulesPutSerializer.event (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/admin_api/recipient_rule_serializers.py:25` |
| `ManagedPolicyMarkerSerializer.count (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/recipient_rule_serializers.py:72` |
| `SearchInput.makerspace_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/admin_api/search.py:26` |
| `SearchInput.q (serializers.CharField)` | `min_length=2, max_length=100` | field / model | `backend/apps/admin_api/search.py:27` |
| `SearchInput.limit (serializers.IntegerField)` | `min_value=1, max_value=10; default=5` | field / model | `backend/apps/admin_api/search.py:28` |
| `MAX_AUDIT_RANGE` | `timedelta(days=366)` | fixed / see setting | `backend/apps/admin_api/serializers_audit.py:18` |
| `AuditLogFilterSerializer.makerspace (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_audit.py:72` |
| `AuditLogFilterSerializer.action (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/admin_api/serializers_audit.py:73` |
| `AuditLogFilterSerializer.target_type (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_audit.py:74` |
| `AuditLogFilterSerializer.target_id (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_audit.py:75` |
| `AuditLogFilterSerializer.actor (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_audit.py:76` |
| `BulkImportPreviewSerializer.rows (serializers.ListField)` | `max_length=bulk_import.MAX_IMPORT_ROWS` | field / model | `backend/apps/admin_api/serializers_bulk.py:11` |
| `BulkImportJobCreateSerializer.rows (serializers.ListField)` | `max_length=bulk_import.MAX_IMPORT_ROWS` | field / model | `backend/apps/admin_api/serializers_bulk.py:26` |
| `CertificationTypeSerializer.validity_days (serializers.IntegerField)` | `min_value=1, max_value=2147483647` | field / model | `backend/apps/admin_api/serializers_certifications.py:14` |
| `FirstStaffInviteSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/admin_api/serializers_creation_setup.py:11` |
| `MakerspaceCreationSetupSerializer.modules (ModuleKeyListField)` | `max_length=60` | field / model | `backend/apps/admin_api/serializers_creation_setup.py:47` |
| `DomainSettingValuesSerializer.filament_low_stock_threshold_grams (serializers.DecimalField)` | `max_digits=10` | field / model | `backend/apps/admin_api/serializers_domain_settings.py:55` |
| `EmailTemplateUpdateSerializer.subject (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_email_templates.py:52` |
| `EmailTemplatePreviewRequestSerializer.subject (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_email_templates.py:73` |
| `PublicImageUploadRequestSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_inventory_assets.py:28` |
| `PublicImageAttachRequestSerializer.object_key (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/admin_api/serializers_inventory_assets.py:32` |
| `ServiceConsumptionSerializer.quantity (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:48` |
| `MachineServiceRequestSerializer.planned_quantity (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:77` |
| `MachineServiceRequestSerializer.reserved_quantity (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:78` |
| `MachineServiceRequestSerializer.actual_consumed_quantity (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:79` |
| `MachineServiceRequestSerializer.planned_grams (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:80` |
| `MachineServiceRequestSerializer.reserved_grams (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:81` |
| `MachineServiceRequestSerializer.actual_consumed_grams (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service.py:82` |
| `MachineServiceSubmitSerializer.requester_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service.py:156` |
| `MachineServiceSubmitSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service.py:157` |
| `MachineServiceSubmitSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_machine_service.py:158` |
| `MachineServiceSubmitSerializer.contact_phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/admin_api/serializers_machine_service.py:163` |
| `MachineServiceSubmitSerializer.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/admin_api/serializers_machine_service.py:165` |
| `ServiceAcceptSerializer.estimated_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/admin_api/serializers_machine_service.py:173` |
| `ServiceAcceptSerializer.planned_grams (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:174` |
| `ServiceCancelSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/admin_api/serializers_machine_service.py:192` |
| `ServiceCancelSerializer.consumed_quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:193` |
| `ServiceStartSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service.py:202` |
| `ServiceStartSerializer.estimated_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/admin_api/serializers_machine_service.py:203` |
| `ServiceStartSerializer.consumable_pool_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service.py:204` |
| `ServiceStartSerializer.planned_grams (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:205` |
| `ServiceStartSerializer.planned_quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:208` |
| `ServiceConsumptionInputSerializer.machine_consumable_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service.py:212` |
| `ServiceConsumptionInputSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:213` |
| `ServiceCompleteSerializer.pickup_location (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/admin_api/serializers_machine_service.py:219` |
| `ServiceCompleteSerializer.actual_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/admin_api/serializers_machine_service.py:220` |
| `ServiceCompleteSerializer.actual_grams (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:221` |
| `ServiceCompleteSerializer.actual_quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service.py:222` |
| `ServiceCompleteSerializer.profile_consumptions (serializers.ListField)` | `max_length=32; default=list` | field / model | `backend/apps/admin_api/serializers_machine_service.py:225` |
| `ServiceFailSerializer.percent_complete (serializers.IntegerField)` | `min_value=0, max_value=100` | field / model | `backend/apps/admin_api/serializers_machine_service.py:231` |
| `ServiceCollectSerializer.pickup_code (serializers.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/admin_api/serializers_machine_service.py:243` |
| `ServiceCollectSerializer.collector_name (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/admin_api/serializers_machine_service.py:244` |
| `ServiceFilePresignSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_machine_service.py:252` |
| `ServiceFilePresignSerializer.content_type (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/admin_api/serializers_machine_service.py:253` |
| `ServiceFileFinalizeSerializer.file_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service.py:269` |
| `PrinterPoolCreateSerializer.unit_cost (serializers.DecimalField)` | `max_digits=14, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:20` |
| `PrinterPoolCreateSerializer.cost_currency (serializers.CharField)` | `max_length=3` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:21` |
| `PrinterPoolCreateSerializer.cost_unit (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:22` |
| `PrinterPoolCreateSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:23` |
| `PrinterPoolCreateSerializer.machine_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:24` |
| `PrinterPoolCreateSerializer.material (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:26` |
| `PrinterPoolCreateSerializer.color (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:27` |
| `PrinterPoolCreateSerializer.color_hex (serializers.CharField)` | `max_length=7` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:28` |
| `PrinterPoolCreateSerializer.brand (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:29` |
| `PrinterPoolCreateSerializer.lot_code (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:30` |
| `PrinterPoolCreateSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:32` |
| `PrinterPoolCreateSerializer.initial_grams (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:33` |
| `PrinterPoolCreateSerializer.low_threshold_grams (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:34` |
| `PrinterPoolCorrectionSerializer.quantity_delta (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:54` |
| `TypedManualUsageSerializer.member (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:59` |
| `TypedManualUsageSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:61` |
| `TypedManualUsageSerializer.consumable_pool_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:62` |
| `TypedManualUsageSerializer.service_request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:63` |
| `TypedManualUsageSerializer.duration_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:64` |
| `TypedManualUsageSerializer.percent_complete (serializers.IntegerField)` | `min_value=0, max_value=100; default=100` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:66` |
| `TypedManualUsageSerializer.grams (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0'); default=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:68` |
| `TypedManualUsageSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:69` |
| `TypedManualUsageSerializer.note (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_machine_service_printer.py:71` |
| `MachineTypePricingSetSerializer.rate_per_unit (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/admin_api/serializers_machine_type_pricing.py:17` |
| `MachineTypePricingSetSerializer.flat_fee (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/admin_api/serializers_machine_type_pricing.py:18` |
| `MakerspaceProfileSerializer.timezone (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_makerspace_profile.py:14` |
| `MakerspaceProfileSerializer.country (serializers.CharField)` | `max_length=2` | field / model | `backend/apps/admin_api/serializers_makerspace_profile.py:15` |
| `MakerspaceProfileSerializer.default_currency (serializers.CharField)` | `max_length=3` | field / model | `backend/apps/admin_api/serializers_makerspace_profile.py:17` |
| `MakerspaceSerializer.organization_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:57` |
| `MakerspaceSerializer.organization_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:61` |
| `MakerspaceSerializer.install_profile_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:65` |
| `MakerspaceSerializer.event_reminder_lead_hours (serializers.ListField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:70` |
| `MakerspaceSerializer.event_reminder_lead_hours (serializers.IntegerField)` | `min_value=1, max_value=8760` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:71` |
| `MakerspaceSerializer.booking_reminder_lead_hours (serializers.ListField)` | `max_length=100` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:74` |
| `MakerspaceSerializer.booking_reminder_lead_hours (serializers.IntegerField)` | `min_value=1, max_value=8760` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:75` |
| `MakerspaceSerializer.frontend_domain (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:83` |
| `MakerspaceSerializer.slack_webhook_url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:101` |
| `MakerspaceSerializer.mattermost_webhook_url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:104` |
| `MakerspaceSerializer.discord_webhook_url (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:107` |
| `MakerspaceSerializer.public_display_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_makerspaces.py:119` |
| `MemberClaimCodeIssueRequestSerializer.membership_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_member_claim.py:8` |
| `InvitationSerializer.invite_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/admin_api/serializers_member_memberships.py:19` |
| `MemberMachineScopeWriteSerializer.machine_type_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_member_scope.py:28` |
| `MemberMachineScopeWriteSerializer.machine_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_member_scope.py:29` |
| `MemberUnitCreateSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/admin_api/serializers_member_units.py:42` |
| `MemberUnitCreateSerializer.code (serializers.CharField)` | `max_length=6` | field / model | `backend/apps/admin_api/serializers_member_units.py:44` |
| `MemberUnitCreateSerializer.payment_instructions (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/admin_api/serializers_member_units.py:45` |
| `MemberUnitCreateSerializer.sort_order (serializers.IntegerField)` | `min_value=0, max_value=100000` | field / model | `backend/apps/admin_api/serializers_member_units.py:46` |
| `MemberUnitUpdateSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/admin_api/serializers_member_units.py:50` |
| `MemberUnitUpdateSerializer.code (serializers.CharField)` | `max_length=6` | field / model | `backend/apps/admin_api/serializers_member_units.py:51` |
| `MemberUnitUpdateSerializer.payment_instructions (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/admin_api/serializers_member_units.py:52` |
| `MemberUnitUpdateSerializer.sort_order (serializers.IntegerField)` | `min_value=0, max_value=100000` | field / model | `backend/apps/admin_api/serializers_member_units.py:53` |
| `MemberUnitLevelsSerializer.levels (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/admin_api/serializers_member_units.py:61` |
| `MemberUnitLevelsSerializer.levels (serializers.ListField)` | `max_length=4` | field / model | `backend/apps/admin_api/serializers_member_units.py:61` |
| `PlanUnitsSerializer.unit_ids (serializers.ListField)` | `max_length=500` | field / model | `backend/apps/admin_api/serializers_member_units.py:74` |
| `MembershipRecordInputSerializer.state_code (serializers.CharField)` | `max_length=2` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:32` |
| `MembershipRecordInputSerializer.gstin (serializers.CharField)` | `max_length=15` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:33` |
| `MembershipRecordInputSerializer.staff_notes (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:34` |
| `InviteLinkCreateSerializer.label (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:76` |
| `InviteLinkCreateSerializer.max_uses (serializers.IntegerField)` | `min_value=1, max_value=10000; default=1` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:79` |
| `MembershipIdsSerializer.membership_ids (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:119` |
| `ExtendInputSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:123` |
| `ExtendInputSerializer.days (serializers.IntegerField)` | `min_value=1, max_value=3650` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:124` |
| `BulkDecideInputSerializer.request_ids (serializers.ListField)` | `min_length=1, max_length=100` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:129` |
| `BulkDecideInputSerializer.reason (serializers.CharField)` | `max_length=1000; default=''` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:131` |
| `ErasureDecisionInputSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/admin_api/serializers_membership_l4.py:153` |
| `MembershipPlanSerializer.renewal_price (MoneyField)` | `max_digits=13` | field / model | `backend/apps/admin_api/serializers_membership_plans.py:17` |
| `MembershipCreateSerializer.username (serializers.CharField)` | `max_length=User._meta.get_field('username').max_length` | field / model | `backend/apps/admin_api/serializers_memberships.py:42` |
| `MembershipCreateSerializer.email (serializers.EmailField)` | `max_length=User._meta.get_field('email').max_length` | field / model | `backend/apps/admin_api/serializers_memberships.py:43` |
| `MembershipCreateSerializer.first_name (serializers.CharField)` | `max_length=User._meta.get_field('first_name').max_length` | field / model | `backend/apps/admin_api/serializers_memberships.py:46` |
| `MembershipCreateSerializer.last_name (serializers.CharField)` | `max_length=User._meta.get_field('last_name').max_length` | field / model | `backend/apps/admin_api/serializers_memberships.py:49` |
| `NotificationDestinationWriteSerializer.label (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/admin_api/serializers_notification_destinations.py:68` |
| `NotificationDestinationWriteSerializer.webhook_url (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/admin_api/serializers_notification_destinations.py:71` |
| `NotificationDestinationWriteSerializer.telegram_chat_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/admin_api/serializers_notification_destinations.py:74` |
| `NotificationDestinationWriteSerializer.signing_secret (serializers.CharField)` | `min_length=16, max_length=512` | field / model | `backend/apps/admin_api/serializers_notification_destinations.py:79` |
| `MakerspacePaymentSettingsSerializer.default_currency (serializers.CharField)` | `max_length=3` | field / model | `backend/apps/admin_api/serializers_payments.py:19` |
| `MakerspacePaymentSettingsSerializer.stripe_publishable_key (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_payments.py:20` |
| `MakerspacePaymentSettingsSerializer.razorpay_key_id (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_payments.py:32` |
| `MakerspacePaymentSettingsSerializer.razorpay_key_secret (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_payments.py:35` |
| `MakerspacePaymentSettingsSerializer.razorpay_webhook_secret (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_payments.py:39` |
| `PlatformStripeConnectSettingsSerializer.stripe_publishable_key (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/admin_api/serializers_payments.py:164` |
| `SecurityLockRequestSerializer.note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/admin_api/serializers_security_settings.py:43` |
| `PiiAccessOpenSerializer.reason (serializers.CharField)` | `min_length=10, max_length=300` | field / model | `backend/apps/admin_api/serializers_security_settings.py:47` |
| `PackBookingRulesSerializer.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/serializers_space_packs.py:31` |
| `PackBookingRulesSerializer.min_booking_duration_minutes (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_space_packs.py:32` |
| `PackBookingRulesSerializer.max_booking_duration_minutes (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_space_packs.py:33` |
| `PackBookingRulesSerializer.booking_lead_time_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/admin_api/serializers_space_packs.py:34` |
| `PackBookingRulesSerializer.max_booking_advance_days (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_space_packs.py:35` |
| `SpacePackSerializer.version (serializers.IntegerField)` | `min_value=1, max_value=1` | field / model | `backend/apps/admin_api/serializers_space_packs.py:62` |
| `SpacePackSerializer.checksum (serializers.CharField)` | `min_length=64, max_length=64` | field / model | `backend/apps/admin_api/serializers_space_packs.py:64` |
| `PackImportSerializer.base_checksum (serializers.CharField)` | `min_length=64, max_length=64` | field / model | `backend/apps/admin_api/serializers_space_packs.py:77` |
| `StaffRoleCreateSerializer.user_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:17` |
| `StaffRoleCreateSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:19` |
| `StaffRoleCreateSerializer.roles (serializers.ListField)` | `max_length=8` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:21` |
| `StaffRoleCreateSerializer.machine_type_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:22` |
| `StaffRoleCreateSerializer.machine_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:23` |
| `StaffRoleCreateSerializer.expires_in_days (serializers.IntegerField)` | `min_value=1, max_value=30; default=7` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:25` |
| `StaffRoleChangeSerializer.roles (serializers.ListField)` | `max_length=8` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:35` |
| `StaffRoleChangeSerializer.machine_type_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:36` |
| `StaffRoleChangeSerializer.machine_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:37` |
| `StaffRoleRevokeSerializer.reason (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/admin_api/serializers_staff_roles.py:47` |
| `ResetPasswordRequestSerializer.password (serializers.CharField)` | `min_length=8` | field / model | `backend/apps/admin_api/serializers_users.py:107` |
| `EmailLogQuerySerializer.recent_days (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/admin_api/views_email_logs.py:42` |
| `FinancialYearSerializer.financial_year_start_month (serializers.IntegerField)` | `min_value=1, max_value=12` | field / model | `backend/apps/admin_api/views_financial_year.py:31` |
| `ProvisionSubdomainRequestSerializer.label (serializers.CharField)` | `max_length=63` | field / model | `backend/apps/admin_api/views_hosting.py:21` |
| `MachineAccessCreateSerializer.member_ids (serializers.ListField)` | `max_length=200; default=list` | field / model | `backend/apps/admin_api/views_machine_access.py:78` |
| `MachineAccessCreateSerializer.membership_ids (serializers.ListField)` | `max_length=200; default=list` | field / model | `backend/apps/admin_api/views_machine_access.py:80` |
| `MachineAccessCreateSerializer.note (serializers.CharField)` | `max_length=1000; default=''` | field / model | `backend/apps/admin_api/views_machine_access.py:84` |
| `DowntimeUpdateSerializer.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/admin_api/views_machine_downtime.py:41` |
| `JobSettingsSerializer.file_groups (serializers.ListField)` | `max_length=len(FILE_GROUPS)` | field / model | `backend/apps/admin_api/views_machine_job_board.py:36` |
| `ChangesSerializer.message (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/admin_api/views_machine_jobs.py:30` |
| `JobQuoteRequestSerializer.estimated_minutes (serializers.IntegerField)` | `min_value=0, max_value=100000` | field / model | `backend/apps/admin_api/views_machine_jobs.py:34` |
| `JobQuoteRequestSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/views_machine_jobs.py:35` |
| `JobQuoteRequestSerializer.consumable_pool_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_machine_jobs.py:37` |
| `JobQuoteRequestSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/admin_api/views_machine_jobs.py:38` |
| `JobQuoteRequestSerializer.consumable_estimates (serializers.ListField)` | `max_length=32; default=list` | field / model | `backend/apps/admin_api/views_machine_jobs.py:40` |
| `ReorderSerializer.position (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_machine_jobs.py:45` |
| `UrgentSerializer.reason (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/admin_api/views_machine_jobs.py:50` |
| `AssignSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_machine_jobs.py:54` |
| `BatchStartSerializer.job_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_machine_jobs.py:136` |
| `BatchStartSerializer.job_ids (serializers.ListField)` | `min_length=2, max_length=50` | field / model | `backend/apps/admin_api/views_machine_jobs.py:136` |
| `BatchStartSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_machine_jobs.py:137` |
| `BatchStartSerializer.note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/admin_api/views_machine_jobs.py:141` |
| `BatchCompleteSerializer.actual_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/admin_api/views_machine_jobs.py:145` |
| `BatchCompleteSerializer.actual_quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/admin_api/views_machine_jobs.py:146` |
| `BatchCompleteSerializer.pickup_location (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/admin_api/views_machine_jobs.py:149` |
| `MachineTypePolicySerializer.cert_reminder_days (serializers.IntegerField)` | `min_value=0, max_value=365` | field / model | `backend/apps/admin_api/views_machine_type_policy.py:21` |
| `MachineTypePolicySerializer.reminder_lead_days (serializers.IntegerField)` | `min_value=0, max_value=365` | field / model | `backend/apps/admin_api/views_machine_type_policy.py:22` |
| `MachineTypePolicySerializer.grace_days (serializers.IntegerField)` | `min_value=0, max_value=365` | field / model | `backend/apps/admin_api/views_machine_type_policy.py:23` |
| `RegisterBulkInputSerializer.membership_ids (serializers.ListField)` | `min_length=1, max_length=bulk.MAX_ROWS` | field / model | `backend/apps/admin_api/views_member_register_bulk.py:31` |
| `RequestChangesInputSerializer.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/admin_api/views_member_register_bulk.py:45` |
| `NeedsFixActionSerializer.quantity (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_needs_fix.py:40` |
| `RotateSecretRequestSerializer.grace_hours (serializers.IntegerField)` | `min_value=0, max_value=MAX_GRACE_HOURS; default=DEFAULT_GRACE_HOURS` | field / model | `backend/apps/admin_api/views_notification_destination_secret.py:27` |
| `QueueDecisionNoteSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/admin_api/views_platform_queues.py:60` |
| `PlatformSocialAuthSettingsSerializer.github_client_secret (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/admin_api/views_platform_social.py:16` |
| `StaffInviteItemSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/admin_api/views_staff_bulk.py:23` |
| `StaffInviteItemSerializer.roles (serializers.ListField)` | `max_length=8` | field / model | `backend/apps/admin_api/views_staff_bulk.py:24` |
| `StaffInviteItemSerializer.machine_type_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_staff_bulk.py:25` |
| `StaffInviteItemSerializer.machine_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/admin_api/views_staff_bulk.py:26` |
| `StaffInviteItemSerializer.expires_in_days (serializers.IntegerField)` | `min_value=1, max_value=30; default=7` | field / model | `backend/apps/admin_api/views_staff_bulk.py:28` |
| `StaffInviteBulkSerializer.invites (StaffInviteItemSerializer)` | `max_length=MAX_IDS` | field / model | `backend/apps/admin_api/views_staff_bulk.py:32` |
| `WalkInMemberCreateSerializer.display_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/admin_api/views_walk_in.py:35` |
| `WalkInMemberCreateSerializer.phone (serializers.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/admin_api/views_walk_in.py:39` |

</details>

<details>
<summary>analytics (17 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `JSON_LIMIT` | `1024 * 1024` | fixed / see setting | `backend/apps/analytics/grafana_client.py:24` |
| `IMAGE_LIMIT` | `8 * 1024 * 1024` | fixed / see setting | `backend/apps/analytics/grafana_client.py:25` |
| `GrafanaDashboardViewSerializer.uid (serializers.RegexField)` | `max_length=40` | field / model | `backend/apps/analytics/grafana_serializers.py:11` |
| `GrafanaDashboardViewSerializer.title (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/analytics/grafana_serializers.py:12` |
| `GrafanaDashboardSerializer.public_token (serializers.RegexField)` | `max_length=32` | field / model | `backend/apps/analytics/grafana_serializers.py:17` |
| `GrafanaConnectionUpdateSerializer.grafana_url (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/analytics/grafana_serializers.py:44` |
| `GrafanaConnectionUpdateSerializer.org_id (serializers.IntegerField)` | `min_value=1, max_value=2 ** 31 - 1` | field / model | `backend/apps/analytics/grafana_serializers.py:45` |
| `GrafanaTokenSerializer.token (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/analytics/grafana_serializers.py:50` |
| `MAX_DASHBOARDS` | `50` | fixed / see setting | `backend/apps/analytics/grafana_validation.py:22` |
| `ConnectionFields.metabase_url (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/analytics/models.py:38` |
| `ConnectionFields.login_role (models.CharField)` | `max_length=63; default=''` | field / model | `backend/apps/analytics/models.py:42` |
| `ConnectionFields.provider (models.CharField)` | `max_length=16; default='metabase'` | field / model | `backend/apps/analytics/models.py:48` |
| `ConnectionFields.grafana_url (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/analytics/models.py:49` |
| `MetabaseDashboardSerializer.id (serializers.IntegerField)` | `min_value=1, max_value=2 ** 31 - 1` | field / model | `backend/apps/analytics/serializers.py:10` |
| `MetabaseDashboardSerializer.title (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/analytics/serializers.py:11` |
| `MetabaseConnectionUpdateSerializer.metabase_url (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/analytics/serializers.py:53` |
| `MetabaseConnectionUpdateSerializer.embed_secret (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/analytics/serializers.py:54` |

</details>

<details>
<summary>apiclients (24 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `ApiClientAdminForm.smtp_port (forms.IntegerField)` | `min_value=1` | field / model | `backend/apps/apiclients/admin_forms.py:22` |
| `ApiClient.label (models.CharField)` | `max_length=200` | field / model | `backend/apps/apiclients/models.py:22` |
| `ApiClient.client_id (models.CharField)` | `max_length=64; default=generate_client_id` | field / model | `backend/apps/apiclients/models.py:23` |
| `ApiClient.client_type (models.CharField)` | `max_length=20; default='server'` | field / model | `backend/apps/apiclients/models.py:33` |
| `ApiClient.rate_limit_tier (models.CharField)` | `max_length=20; default='standard'` | field / model | `backend/apps/apiclients/models.py:45` |
| `ApiClient.import_provenance_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:68` |
| `ApiKeyRequest.label (models.CharField)` | `max_length=120` | field / model | `backend/apps/apiclients/models.py:184` |
| `ApiKeyRequest.status (models.CharField)` | `max_length=20; default=Status.PENDING` | field / model | `backend/apps/apiclients/models.py:187` |
| `ApiClientImportApproval.artifact_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:220` |
| `ApiClientImportApproval.source_catalog_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:222` |
| `ApiClientImportApproval.source_client_ref (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:223` |
| `ApiClientImportApproval.source_entry_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:224` |
| `ApiClientImportApproval.approval_record_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:225` |
| `ApiClientImportApproval.host_principal (models.CharField)` | `max_length=255` | field / model | `backend/apps/apiclients/models.py:226` |
| `ApiClientImportApproval.approval_nonce (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models.py:227` |
| `MAX_TTL_DAYS` | `365` | fixed / see setting | `backend/apps/apiclients/models_tokens.py:19` |
| `PersonalAccessToken.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/apiclients/models_tokens.py:32` |
| `PersonalAccessToken.lookup (models.CharField)` | `max_length=16` | field / model | `backend/apps/apiclients/models_tokens.py:33` |
| `PersonalAccessToken.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/apiclients/models_tokens.py:34` |
| `KeysetQuerySerializer.cursor (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/apiclients/read_contract.py:111` |
| `KeysetQuerySerializer.page_size (serializers.IntegerField)` | `min_value=1, max_value=200; default=100` | field / model | `backend/apps/apiclients/read_contract.py:112` |
| `OAuthAppSerializer.name (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/apiclients/views_oauth_apps.py:41` |
| `AccessTokenCreateSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/apiclients/views_tokens.py:37` |
| `AccessTokenCreateSerializer.expires_in_days (serializers.IntegerField)` | `min_value=1, max_value=MAX_TTL_DAYS; default=DEFAULT_TTL_DAYS` | field / model | `backend/apps/apiclients/views_tokens.py:41` |

</details>

<details>
<summary>audit (26 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_INTEGER` | `2 ** 63 - 1` | fixed / see setting | `backend/apps/audit/canonical.py:13` |
| `AuditLog.action (models.CharField)` | `max_length=100` | field / model | `backend/apps/audit/models.py:30` |
| `AuditLog.target_type (models.CharField)` | `max_length=200` | field / model | `backend/apps/audit/models.py:31` |
| `AuditLog.target_id (models.CharField)` | `max_length=100` | field / model | `backend/apps/audit/models.py:32` |
| `AuditSigningKey.fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/audit/models_signing.py:35` |
| `AuditSigningKeyRotation.old_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/audit/models_signing.py:132` |
| `AuditSigningKeyRotation.new_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/audit/models_signing.py:133` |
| `AuditSigningKeyRotationEvent.state (models.CharField)` | `max_length=16` | field / model | `backend/apps/audit/models_signing.py:193` |
| `AuditBatch.signer_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/audit/models_signing.py:230` |
| `AuditVerificationRun.action_filter (models.CharField)` | `max_length=100` | field / model | `backend/apps/audit/models_verification_runs.py:29` |
| `AuditVerificationRun.target_type_filter (models.CharField)` | `max_length=200` | field / model | `backend/apps/audit/models_verification_runs.py:30` |
| `AuditVerificationRun.target_id_filter (models.CharField)` | `max_length=100` | field / model | `backend/apps/audit/models_verification_runs.py:31` |
| `AuditVerificationRun.filter_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/audit/models_verification_runs.py:38` |
| `SOFT_TIME_LIMIT` | `('soft_time_limit', gettext_noop('Soft time limit'))` | fixed / see setting | `backend/apps/audit/models_verification_runs.py:93` |
| `AuditVerificationRunEvent.state (models.CharField)` | `max_length=16` | field / model | `backend/apps/audit/models_verification_runs.py:97` |
| `AuditVerificationRunEvent.chain_status (models.CharField)` | `max_length=24; default=ChainStatus.PENDING` | field / model | `backend/apps/audit/models_verification_runs.py:109` |
| `AuditVerificationRunEvent.anchor_status (models.CharField)` | `max_length=24; default=AnchorStatus.PENDING` | field / model | `backend/apps/audit/models_verification_runs.py:112` |
| `AuditVerificationRunEvent.failure_code (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/audit/models_verification_runs.py:115` |
| `MAX_ROWS` | `10000` | fixed / see setting | `backend/apps/audit/verification_runs.py:31` |
| `MAX_EXPANDED_LEAVES` | `50000` | fixed / see setting | `backend/apps/audit/verification_runs.py:32` |
| `MAX_CHAIN_BATCHES` | `2500` | fixed / see setting | `backend/apps/audit/verification_runs.py:33` |
| `MAX_ROTATIONS` | `256` | fixed / see setting | `backend/apps/audit/verification_runs.py:34` |
| `MAX_ANCHOR_READS` | `2760` | fixed / see setting | `backend/apps/audit/verification_runs.py:35` |
| `SOFT_TIME_LIMIT` | `120` | fixed / see setting | `backend/apps/audit/verification_runs.py:36` |
| `HARD_TIME_LIMIT` | `150` | fixed / see setting | `backend/apps/audit/verification_runs.py:37` |
| `MAX_ATTEMPTS` | `3` | fixed / see setting | `backend/apps/audit/verification_runs.py:38` |

</details>

<details>
<summary>backup (89 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_REQUEST_BYTES` | `64 * 1024` | fixed / see setting | `backend/apps/backup/host_capability_socket.py:18` |
| `MAX_OID` | `(1 << 32) - 1` | fixed / see setting | `backend/apps/backup/host_marker.py:22` |
| `MAX_SYSTEM_IDENTIFIER` | `(1 << 64) - 1` | fixed / see setting | `backend/apps/backup/host_marker.py:23` |
| `ManagedWriterBoundary.category (models.CharField)` | `max_length=24` | field / model | `backend/apps/backup/managed/models.py:54` |
| `ManagedStagedObject.label (models.CharField)` | `max_length=80` | field / model | `backend/apps/backup/managed/models_staging.py:10` |
| `ManagedStagedObject.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/managed/models_staging.py:13` |
| `ManagedStagedObject.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/managed/models_staging.py:15` |
| `PlatformBackupSettings.retention_days (MaxValueValidator)` | `max_value=3650` | field / model | `backend/apps/backup/models.py:23` |
| `PlatformBackupSettings.retention_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/backup/models.py:23` |
| `PlatformBackupSettings.last_error (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models.py:27` |
| `PlatformBackupSettings.restore_drill_interval_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/backup/models.py:32` |
| `BackupArchive.scope (models.CharField)` | `max_length=16` | field / model | `backend/apps/backup/models.py:66` |
| `BackupArchive.format (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/backup/models.py:70` |
| `BackupArchive.trigger (models.CharField)` | `max_length=16; default=Trigger.ON_DEMAND` | field / model | `backend/apps/backup/models.py:71` |
| `BackupArchive.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/backup/models.py:87` |
| `BackupArchive.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models.py:89` |
| `BackupArchive.staging_object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models.py:90` |
| `BackupArchive.archive_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models.py:93` |
| `BackupArchive.failure_detail (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models.py:95` |
| `BackupArchive.download_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models.py:99` |
| `BackupArtifactLedger.outer_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_artifact_ledger.py:27` |
| `BackupArtifactLedger.outer_manifest_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_artifact_ledger.py:28` |
| `BackupArtifactLedger.format (models.CharField)` | `max_length=80` | field / model | `backend/apps/backup/models_artifact_ledger.py:29` |
| `BackupArtifactLedger.staging_locator (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models_artifact_ledger.py:33` |
| `BackupArtifactLedger.final_locator (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models_artifact_ledger.py:34` |
| `BackupArtifactLedger.state (models.CharField)` | `max_length=24; default=State.PENDING` | field / model | `backend/apps/backup/models_artifact_ledger.py:35` |
| `BackupArtifactLedger.staging_verified_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_artifact_ledger.py:43` |
| `BackupArtifactLedger.final_verified_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_artifact_ledger.py:46` |
| `BackupArtifactLedger.failure_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_artifact_ledger.py:51` |
| `BackupArtifactComponent.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/backup/models_artifact_ledger.py:80` |
| `BackupArtifactComponent.ciphertext_path (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models_artifact_ledger.py:82` |
| `BackupArtifactComponent.ciphertext_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_artifact_ledger.py:83` |
| `BackupArtifactComponent.storage_state (models.CharField)` | `max_length=16; default=StorageState.PENDING` | field / model | `backend/apps/backup/models_artifact_ledger.py:85` |
| `RestoreDrillReport.outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/backup/models_drill.py:27` |
| `RestoreDrillReport.error_code (models.CharField)` | `max_length=48` | field / model | `backend/apps/backup/models_drill.py:28` |
| `RestoreDrillReport.error_detail (models.CharField)` | `max_length=300` | field / model | `backend/apps/backup/models_drill.py:29` |
| `DeploymentDatabaseIdentity.artifact_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_host_identity.py:11` |
| `BackupKeyFingerprint.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/backup/models_keys.py:21` |
| `BackupKeyFingerprint.fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_keys.py:22` |
| `BackupDestination.name (models.SlugField)` | `max_length=64` | field / model | `backend/apps/backup/models_offsite.py:28` |
| `BackupDestination.kind (models.CharField)` | `max_length=16; default=Kind.S3` | field / model | `backend/apps/backup/models_offsite.py:29` |
| `BackupDestination.endpoint_url (models.URLField)` | `max_length=300` | field / model | `backend/apps/backup/models_offsite.py:30` |
| `BackupDestination.bucket (models.CharField)` | `max_length=255` | field / model | `backend/apps/backup/models_offsite.py:31` |
| `BackupDestination.region (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_offsite.py:32` |
| `BackupDestination.prefix (models.CharField)` | `max_length=200` | field / model | `backend/apps/backup/models_offsite.py:33` |
| `BackupDestination.addressing_style (models.CharField)` | `max_length=16; default=AddressingStyle.AUTO` | field / model | `backend/apps/backup/models_offsite.py:34` |
| `BackupDestination.access_key_id (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models_offsite.py:40` |
| `BackupDestination.secret_access_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models_offsite.py:41` |
| `BackupDestination.retention_days (MaxValueValidator)` | `max_value=3650` | field / model | `backend/apps/backup/models_offsite.py:44` |
| `BackupDestination.retention_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/backup/models_offsite.py:44` |
| `BackupDestination.last_error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_offsite.py:57` |
| `BackupDestinationUpload.scope_snapshot (models.CharField)` | `max_length=16` | field / model | `backend/apps/backup/models_offsite.py:109` |
| `BackupDestinationUpload.format_snapshot (models.CharField)` | `max_length=80` | field / model | `backend/apps/backup/models_offsite.py:111` |
| `BackupDestinationUpload.expected_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_offsite.py:114` |
| `BackupDestinationUpload.integrity_source (models.CharField)` | `max_length=24` | field / model | `backend/apps/backup/models_offsite.py:115` |
| `BackupDestinationUpload.remote_locator (models.CharField)` | `max_length=600` | field / model | `backend/apps/backup/models_offsite.py:117` |
| `BackupDestinationUpload.state (models.CharField)` | `max_length=24; default=State.PENDING` | field / model | `backend/apps/backup/models_offsite.py:118` |
| `BackupDestinationUpload.verified_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_offsite.py:126` |
| `BackupDestinationUpload.last_error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_offsite.py:129` |
| `RestoreOperation.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/backup/models_restore.py:43` |
| `RestoreOperation.stage (models.CharField)` | `max_length=24; default=Stage.REQUESTED` | field / model | `backend/apps/backup/models_restore.py:44` |
| `RestoreOperation.decision (models.CharField)` | `max_length=16; default=Decision.PENDING` | field / model | `backend/apps/backup/models_restore.py:45` |
| `RestoreOperation.requested_by_username_snapshot (models.CharField)` | `max_length=150` | field / model | `backend/apps/backup/models_restore.py:50` |
| `RestoreOperation.error_detail (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models_restore.py:55` |
| `DeploymentRecoveryState.mode (models.CharField)` | `max_length=16; default=Mode.NORMAL` | field / model | `backend/apps/backup/models_restore.py:71` |
| `BackupLease.name (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_restore.py:101` |
| `RestoreRollbackObject.bucket_kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/backup/models_restore.py:117` |
| `RestoreRollbackObject.module_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_restore.py:118` |
| `RestoreRollbackObject.source_key (models.CharField)` | `max_length=1024` | field / model | `backend/apps/backup/models_restore.py:119` |
| `RestoreRollbackObject.copy_key (models.CharField)` | `max_length=1024` | field / model | `backend/apps/backup/models_restore.py:120` |
| `RestoreRollbackObject.source_absent_marker_version_id (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models_restore.py:122` |
| `RestoreRollbackObject.source_version_id (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models_restore.py:123` |
| `RestoreRollbackObject.replacement_version_id (models.CharField)` | `max_length=512` | field / model | `backend/apps/backup/models_restore.py:124` |
| `BackupRun.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/backup/models_runs.py:19` |
| `BackupRun.failure_detail (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models_runs.py:22` |
| `BackupRunCoverage.path (models.CharField)` | `max_length=16` | field / model | `backend/apps/backup/models_runs.py:63` |
| `BackupRunCoverage.state (models.CharField)` | `max_length=16; default=State.PENDING` | field / model | `backend/apps/backup/models_runs.py:64` |
| `BackupRunCoverage.archive_sha256_snapshot (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_runs.py:69` |
| `MakerspaceRestoreOperation.source (models.CharField)` | `max_length=24; default=Source.SPACE_ARCHIVE` | field / model | `backend/apps/backup/models_space_restore.py:38` |
| `MakerspaceRestoreOperation.stage (models.CharField)` | `max_length=16; default=Stage.REQUESTED` | field / model | `backend/apps/backup/models_space_restore.py:42` |
| `MakerspaceRestoreOperation.preview_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/backup/models_space_restore.py:51` |
| `MakerspaceRestoreOperation.error_code (models.CharField)` | `max_length=48` | field / model | `backend/apps/backup/models_space_restore.py:54` |
| `MakerspaceRestoreOperation.error_detail (models.CharField)` | `max_length=500` | field / model | `backend/apps/backup/models_space_restore.py:55` |
| `LINK_MAX_AGE` | `7 * 24 * 3600` | fixed / see setting | `backend/apps/backup/operator_notice.py:23` |
| `_MAX_PROTOCOL_VERSION` | `65535` | fixed / see setting | `backend/apps/backup/producer_capability.py:31` |
| `BackupDestinationSerializer.access_key_id (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/backup/serializers_offsite.py:12` |
| `BackupDestinationSerializer.secret_access_key (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/backup/serializers_offsite.py:15` |
| `SpaceRestoreConfirmSerializer.confirm_slug (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/backup/serializers_space_restore.py:32` |
| `DrillRunSerializer.makerspace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/backup/views_drills.py:71` |

</details>

<details>
<summary>bookings (127 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `BookingCheckInEvent.action (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_arrival.py:27` |
| `BookingCheckInEvent.source (models.CharField)` | `max_length=16; default='staff_qr'` | field / model | `backend/apps/bookings/models_arrival.py:28` |
| `Booking.status (models.CharField)` | `max_length=16; default=Status.CONFIRMED` | field / model | `backend/apps/bookings/models_booking.py:49` |
| `Booking.status_before_cancel (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/bookings/models_booking.py:55` |
| `BookingDepartureEvent.outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/bookings/models_departure.py:42` |
| `BookingDepartureEvent.source (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_departure.py:44` |
| `BookingIssue.outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/bookings/models_departure.py:72` |
| `BookingIssue.resolution_note (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/bookings/models_departure.py:77` |
| `BookingCalendarFeed.token_digest (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/bookings/models_feed.py:10` |
| `BookingCalendarFeed.token_hint (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_feed.py:11` |
| `MAX_PHOTOS_PER_SPACE` | `12` | fixed / see setting | `backend/apps/bookings/models_gallery.py:12` |
| `BookableSpacePhoto.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/bookings/models_gallery.py:18` |
| `BookableSpacePhoto.caption (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/bookings/models_gallery.py:20` |
| `IncludedHoursUsage.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_included_hours.py:27` |
| `IncludedHoursUsage.entry (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_included_hours.py:28` |
| `MAX_REVISION` | `9007199254740991` | fixed / see setting | `backend/apps/bookings/models_loan_context.py:5` |
| `BookingOrganizationLink.organization_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/models_organization.py:18` |
| `OrganizationHoursAllowance.period (models.CharField)` | `max_length=8; default=Period.NONE` | field / model | `backend/apps/bookings/models_organization_hours.py:25` |
| `OrganizationHoursLedger.entry (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_organization_hours.py:47` |
| `OrganizationHoursLedger.period_key (models.CharField)` | `max_length=8` | field / model | `backend/apps/bookings/models_organization_hours.py:51` |
| `OrganizationHoursLedger.reason (models.CharField)` | `max_length=500` | field / model | `backend/apps/bookings/models_organization_hours.py:54` |
| `BookableSpace.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/models_spaces.py:38` |
| `BookableSpace.kind (models.CharField)` | `max_length=16; default=Kind.OTHER` | field / model | `backend/apps/bookings/models_spaces.py:39` |
| `BookableSpace.location (models.CharField)` | `max_length=255` | field / model | `backend/apps/bookings/models_spaces.py:46` |
| `BookableSpace.image_key (models.CharField)` | `max_length=500; default=None` | field / model | `backend/apps/bookings/models_spaces.py:47` |
| `BookableSpace.approval_mode (models.CharField)` | `max_length=16; default=ApprovalMode.APPROVE` | field / model | `backend/apps/bookings/models_spaces.py:56` |
| `BookableSpace.payment_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/bookings/models_spaces.py:74` |
| `BookableSpace.payment_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/bookings/models_spaces.py:78` |
| `BookableSpace.min_booking_duration_minutes (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/bookings/models_spaces.py:82` |
| `BookableSpace.max_booking_duration_minutes (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/bookings/models_spaces.py:86` |
| `BookableSpace.buffer_before_minutes (MaxValueValidator)` | `max_value=1440` | field / model | `backend/apps/bookings/models_spaces.py:90` |
| `BookableSpace.buffer_after_minutes (MaxValueValidator)` | `max_value=1440` | field / model | `backend/apps/bookings/models_spaces.py:93` |
| `BookableSpace.cancellation_cutoff_hours (MaxValueValidator)` | `max_value=8760` | field / model | `backend/apps/bookings/models_spaces.py:96` |
| `BookableSpace.max_booking_advance_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/bookings/models_spaces.py:100` |
| `BookingResourcePageAsset.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/bookings/models_website.py:24` |
| `BookingResourcePageAsset.alt_text (models.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/models_website.py:26` |
| `BookingResourcePageSection.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/bookings/models_website.py:40` |
| `BookingResourcePageSection.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/bookings/models_website.py:41` |
| `BookingResourcePageSection.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/models_website.py:42` |
| `BookingResourcePageSection.body (models.CharField)` | `max_length=10000` | field / model | `backend/apps/bookings/models_website.py:43` |
| `BookingResourcePageSection.url (models.URLField)` | `max_length=500` | field / model | `backend/apps/bookings/models_website.py:44` |
| `BookingResourcePageSection.visibility (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/bookings/models_website.py:46` |
| `SpaceImagePresignRequestSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/bookings/serializers_admin_actions.py:13` |
| `SpaceImagePresignRequestSerializer.content_type (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/bookings/serializers_admin_actions.py:14` |
| `SpaceImageFinalizeRequestSerializer.object_key (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/bookings/serializers_admin_actions.py:30` |
| `BookingListFilterSerializer.booking_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_admin_actions.py:58` |
| `BookingCredentialSerializer.credential (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/bookings/serializers_arrival.py:8` |
| `StaffBookingReadinessQuerySerializer.member_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_booking_readiness.py:8` |
| `BookingBroadcastInputSerializer.subject (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/serializers_broadcasts.py:10` |
| `BookingBroadcastInputSerializer.body (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/bookings/serializers_broadcasts.py:11` |
| `BookingBroadcastInputSerializer.statuses (serializers.ListField)` | `min_length=1, max_length=2; default=['confirmed']` | field / model | `backend/apps/bookings/serializers_broadcasts.py:14` |
| `BookingBroadcastSerializer.subject (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/serializers_broadcasts.py:26` |
| `BookingBroadcastSerializer.body (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/bookings/serializers_broadcasts.py:27` |
| `BookingBroadcastSerializer.statuses (serializers.ListField)` | `min_length=1, max_length=2` | field / model | `backend/apps/bookings/serializers_broadcasts.py:28` |
| `DepartureInputSerializer.remark (serializers.CharField)` | `max_length=MAX_REMARK; default=''` | field / model | `backend/apps/bookings/serializers_departure.py:11` |
| `BookingQueueFilterSerializer.space (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_departure.py:34` |
| `BookingIssueFilterSerializer.space (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_departure.py:65` |
| `IssueResolveSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/bookings/serializers_departure.py:69` |
| `IntegrationBookingPublicPageSerializer.payment_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/bookings/serializers_integration.py:25` |
| `MAX_SAFE_INTEGER` | `9007199254740991` | fixed / see setting | `backend/apps/bookings/serializers_loan_context.py:6` |
| `OrganizationHoursBankWriteSerializer.allowance_minutes (serializers.IntegerField)` | `min_value=0, max_value=6000000` | field / model | `backend/apps/bookings/serializers_organization_hours.py:23` |
| `OrganizationHoursAdjustSerializer.minutes (serializers.IntegerField)` | `min_value=-6000000, max_value=6000000` | field / model | `backend/apps/bookings/serializers_organization_hours.py:63` |
| `OrganizationHoursAdjustSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/bookings/serializers_organization_hours.py:65` |
| `BookingPassTemplateSerializer.version (serializers.IntegerField)` | `min_value=2, max_value=2` | field / model | `backend/apps/bookings/serializers_passes.py:13` |
| `BookingPassTemplateSerializer.page_width_mm (serializers.FloatField)` | `min_value=100, max_value=500` | field / model | `backend/apps/bookings/serializers_passes.py:16` |
| `BookingPassTemplateSerializer.page_height_mm (serializers.FloatField)` | `min_value=100, max_value=500` | field / model | `backend/apps/bookings/serializers_passes.py:17` |
| `BookingPassTemplateSerializer.card_width_mm (serializers.FloatField)` | `min_value=40, max_value=150` | field / model | `backend/apps/bookings/serializers_passes.py:18` |
| `BookingPassTemplateSerializer.card_height_mm (serializers.FloatField)` | `min_value=30, max_value=120` | field / model | `backend/apps/bookings/serializers_passes.py:19` |
| `BookingPassTemplateSerializer.margin_mm (serializers.FloatField)` | `min_value=0, max_value=40` | field / model | `backend/apps/bookings/serializers_passes.py:20` |
| `BookingPassTemplateSerializer.gap_mm (serializers.FloatField)` | `min_value=0, max_value=30` | field / model | `backend/apps/bookings/serializers_passes.py:21` |
| `BookingPassTemplateSerializer.grid_mm (serializers.FloatField)` | `min_value=0.5, max_value=10` | field / model | `backend/apps/bookings/serializers_passes.py:22` |
| `BookingPassTemplateSerializer.elements (BookingPassElementSerializer)` | `min_length=1, max_length=4` | field / model | `backend/apps/bookings/serializers_passes.py:23` |
| `PublicBookableSpaceSerializer.capacity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/bookings/serializers_public.py:44` |
| `PublicBookingInputSerializer.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/bookings/serializers_public.py:133` |
| `PublicBookingInputSerializer.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_public.py:141` |
| `BookableSpaceWriteSerializer.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/serializers_space_write.py:12` |
| `BookableSpaceWriteSerializer.capacity (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/bookings/serializers_space_write.py:19` |
| `BookableSpaceWriteSerializer.location (serializers.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/bookings/serializers_space_write.py:20` |
| `BookableSpaceWriteSerializer.payment_amount (MoneyField)` | `max_digits=13, min_value=0; default=0` | field / model | `backend/apps/bookings/serializers_space_write.py:40` |
| `BookableSpaceWriteSerializer.machine_type (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_space_write.py:50` |
| `BookableSpaceWriteSerializer.machine (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_space_write.py:52` |
| `StaffBookingInputSerializer.member_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_staff_booking.py:14` |
| `StaffBookingInputSerializer.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/bookings/serializers_staff_booking.py:15` |
| `StaffBookingInputSerializer.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/bookings/serializers_staff_booking.py:16` |
| `StaffSingleBookingInputSerializer.member_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_staff_booking.py:36` |
| `StaffBookingQuoteInputSerializer.member_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_staff_booking.py:59` |
| `StaffBookingQuoteInputSerializer.replaces_booking_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_staff_booking.py:62` |
| `StaffBookingQuoteInputSerializer.organization_id (serializers.IntegerField)` | `min_value=1, max_value=9223372036854775807` | field / model | `backend/apps/bookings/serializers_staff_booking.py:67` |
| `BookingStaffGrantPermissionsSerializer.permissions (serializers.ListField)` | `min_length=1, max_length=4` | field / model | `backend/apps/bookings/serializers_staff_grants.py:18` |
| `BookingStaffGrantSerializer.permissions (serializers.ListField)` | `min_length=1, max_length=4` | field / model | `backend/apps/bookings/serializers_staff_grants.py:39` |
| `BookingStaffGrantInviteSerializer.permissions (serializers.ListField)` | `min_length=1, max_length=4` | field / model | `backend/apps/bookings/serializers_staff_grants.py:50` |
| `BookingStaffGrantRedeemSerializer.token (serializers.CharField)` | `min_length=32, max_length=128` | field / model | `backend/apps/bookings/serializers_staff_grants.py:68` |
| `BookingDetailsInputSerializer.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/bookings/serializers_staff_tools.py:15` |
| `BookingTimeInputSerializer.price_confirmation (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/bookings/serializers_staff_tools.py:27` |
| `BookingWebsiteSectionInput.slug (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/bookings/serializers_website.py:25` |
| `BookingWebsiteSectionInput.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/serializers_website.py:26` |
| `BookingWebsiteSectionInput.body (serializers.CharField)` | `max_length=10000; default=''` | field / model | `backend/apps/bookings/serializers_website.py:27` |
| `BookingWebsiteSectionInput.url (serializers.URLField)` | `max_length=500; default=''` | field / model | `backend/apps/bookings/serializers_website.py:28` |
| `BookingWebsiteSectionInput.asset_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/bookings/serializers_website.py:29` |
| `BookingWebsiteSectionInput.position (serializers.IntegerField)` | `min_value=0, max_value=1000; default=0` | field / model | `backend/apps/bookings/serializers_website.py:31` |
| `BookingWebsiteContentInput.revision (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/bookings/serializers_website.py:45` |
| `BookingWebsiteContentInput.sections (BookingWebsiteSectionInput)` | `max_length=100` | field / model | `backend/apps/bookings/serializers_website.py:46` |
| `BookingWebsiteReleaseInput.revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_website.py:50` |
| `BookingWebsiteAssetInput.alt_text (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/serializers_website.py:56` |
| `BookingWebsiteAssetInput.replace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_website.py:57` |
| `PublicBookingResourceSerializer.payment_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/bookings/serializers_website.py:87` |
| `BookingDiscoveryFilters.q (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/serializers_website.py:94` |
| `BookingDiscoveryFilters.location (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/bookings/serializers_website.py:95` |
| `BookingDiscoveryFilters.page (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/serializers_website.py:97` |
| `MAX_REASON` | `1000` | fixed / see setting | `backend/apps/bookings/services_decisions.py:6` |
| `BookingDecisionSerializer.reason (serializers.CharField)` | `max_length=MAX_REASON; default=''` | field / model | `backend/apps/bookings/services_decisions.py:21` |
| `BookingRejectSerializer.reason (serializers.CharField)` | `max_length=MAX_REASON` | field / model | `backend/apps/bookings/services_decisions.py:36` |
| `MAX_REMARK` | `2000` | fixed / see setting | `backend/apps/bookings/services_departure.py:22` |
| `MAX_DURATION_MINUTES` | `60 * 24 * 30` | fixed / see setting | `backend/apps/bookings/services_rules.py:29` |
| `MAX_LEAD_MINUTES` | `60 * 24 * 365` | fixed / see setting | `backend/apps/bookings/services_rules.py:30` |
| `MAX_ADVANCE_DAYS` | `3650` | fixed / see setting | `backend/apps/bookings/services_rules.py:31` |
| `MAX_WINDOW` | `timedelta(days=14)` | fixed / see setting | `backend/apps/bookings/views_admin_booking_availability.py:20` |
| `SpacePhotoAttachSerializer.object_key (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/bookings/views_gallery.py:38` |
| `SpacePhotoAttachSerializer.caption (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/bookings/views_gallery.py:39` |
| `SpacePhotoUpdateSerializer.caption (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/bookings/views_gallery.py:43` |
| `SpacePhotoOrderSerializer.order (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/views_gallery.py:47` |
| `SpacePhotoOrderSerializer.order (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/bookings/views_gallery.py:47` |
| `OrganizationBookingInputSerializer.organization_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/views_organization_booking.py:42` |
| `OrganizationBookingInputSerializer.contact_member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/bookings/views_organization_booking.py:43` |
| `OrganizationBookingInputSerializer.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/bookings/views_organization_booking.py:46` |
| `RecurringBookingInputSerializer.count (serializers.IntegerField)` | `min_value=2, max_value=52` | field / model | `backend/apps/bookings/views_recurrence.py:18` |
| `RecurringBookingInputSerializer.interval_weeks (serializers.IntegerField)` | `min_value=1, max_value=12; default=1` | field / model | `backend/apps/bookings/views_recurrence.py:19` |

</details>

<details>
<summary>boxes (16 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `QrRebindAdminForm.new_name (forms.CharField)` | `max_length=100` | field / model | `backend/apps/boxes/admin.py:37` |
| `Box.code (models.CharField)` | `max_length=32; default=generate_box_code` | field / model | `backend/apps/boxes/models.py:30` |
| `Box.label (models.CharField)` | `max_length=200` | field / model | `backend/apps/boxes/models.py:36` |
| `Box.location (models.CharField)` | `max_length=200` | field / model | `backend/apps/boxes/models.py:37` |
| `BoxScan.context (models.CharField)` | `max_length=20` | field / model | `backend/apps/boxes/models.py:107` |
| `QrCode.payload (models.CharField)` | `max_length=64; default=generate_box_code` | field / model | `backend/apps/boxes/models.py:144` |
| `QrCode.source (models.CharField)` | `max_length=20; default=Source.SPACEWORKS` | field / model | `backend/apps/boxes/models.py:145` |
| `QrCode.external_value (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/boxes/models.py:146` |
| `QrCode.target_type (models.CharField)` | `max_length=20` | field / model | `backend/apps/boxes/models.py:147` |
| `QrCode.status (models.CharField)` | `max_length=20; default=Status.ACTIVE` | field / model | `backend/apps/boxes/models.py:149` |
| `QrScanEvent.context (models.CharField)` | `max_length=32` | field / model | `backend/apps/boxes/models.py:225` |
| `EXTERNAL_VALUE_MAX_LENGTH` | `64` | fixed / see setting | `backend/apps/boxes/qr_lookup.py:14` |
| `QrRebindTargetSerializer.new_name (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/boxes/serializers.py:162` |
| `ExternalQrNewAssetSerializer.asset_tag (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/boxes/serializers_external.py:9` |
| `ExternalQrNewAssetSerializer.serial_number (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/boxes/serializers_external.py:10` |
| `ExternalQrAssignSerializer.value (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/boxes/serializers_external.py:17` |

</details>

<details>
<summary>card_designs (176 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `LIST_LIMIT` | `200` | fixed / see setting | `backend/apps/card_designs/asset_library.py:20` |
| `MAX_BYTES` | `32000` | fixed / see setting | `backend/apps/card_designs/badge_format.py:22` |
| `MAX_DIMENSION_MM` | `300.0` | fixed / see setting | `backend/apps/card_designs/badge_format.py:23` |
| `FOOTER_MAX_LENGTH` | `240` | fixed / see setting | `backend/apps/card_designs/badge_format.py:24` |
| `MAX_FILE_BYTES` | `200000` | fixed / see setting | `backend/apps/card_designs/badge_import.py:18` |
| `MAX_PAYLOAD` | `80` | fixed / see setting | `backend/apps/card_designs/barcode_symbols.py:19` |
| `MAX_BYTES` | `256 * 1024` | fixed / see setting | `backend/apps/card_designs/csv_merge.py:23` |
| `MAX_ROWS` | `200` | fixed / see setting | `backend/apps/card_designs/csv_merge.py:24` |
| `MAX_COLUMNS` | `40` | fixed / see setting | `backend/apps/card_designs/csv_merge.py:25` |
| `MAX_VALUE` | `200` | fixed / see setting | `backend/apps/card_designs/csv_merge.py:26` |
| `MAX_ATTEMPTS` | `4` | fixed / see setting | `backend/apps/card_designs/cutouts.py:27` |
| `MAX_FILE_BYTES` | `300000` | fixed / see setting | `backend/apps/card_designs/design_file.py:19` |
| `DAILY_CAP` | `200` | fixed / see setting | `backend/apps/card_designs/email.py:25` |
| `NEW_SPACE_CAP` | `50` | fixed / see setting | `backend/apps/card_designs/email.py:25` |
| `MAX_FONT_BYTES` | `40 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/font_fetch.py:21` |
| `MAX_CARDS` | `50` | fixed / see setting | `backend/apps/card_designs/holder_access.py:11` |
| `MAX_CHARS` | `200` | fixed / see setting | `backend/apps/card_designs/holders_member_answers.py:11` |
| `MAX_INPUT_BYTES` | `8 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/image_adapter/contract.py:25` |
| `MAX_INPUT_EDGE` | `4096` | fixed / see setting | `backend/apps/card_designs/image_adapter/contract.py:26` |
| `MAX_OUTPUT_BYTES` | `16 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/image_adapter/contract.py:27` |
| `MAX_MASK_BYTES` | `8 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/image_adapter/contract.py:28` |
| `MAX_PIXELS` | `MAX_INPUT_EDGE * MAX_INPUT_EDGE` | fixed / see setting | `backend/apps/card_designs/image_adapter/png_validation.py:17` |
| `MAX_UPLOAD_BYTES` | `8 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/images.py:13` |
| `MAX_PUBLIC_BYTES` | `8 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/images.py:14` |
| `MAX_JPEG_PIXELS` | `50000000` | fixed / see setting | `backend/apps/card_designs/images.py:17` |
| `MAX_OTHER_PIXELS` | `16000000` | fixed / see setting | `backend/apps/card_designs/images.py:18` |
| `MAX_ATTEMPTS` | `3` | fixed / see setting | `backend/apps/card_designs/job_runner.py:22` |
| `MAX_BYTES` | `256 * 1024` | fixed / see setting | `backend/apps/card_designs/layout.py:25` |
| `MAX_LAYERS` | `60` | fixed / see setting | `backend/apps/card_designs/layout.py:26` |
| `MAX_SPANS` | `20` | fixed / see setting | `backend/apps/card_designs/layout_studio.py:19` |
| `MAX_TEXT` | `500` | fixed / see setting | `backend/apps/card_designs/layout_studio.py:20` |
| `MAX_RULERS` | `20` | fixed / see setting | `backend/apps/card_designs/layout_studio.py:21` |
| `CardPhotoCutout.state (models.CharField)` | `max_length=8; default=State.QUEUED` | field / model | `backend/apps/card_designs/models_cutout.py:26` |
| `CardPhotoCutout.error_code (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:27` |
| `CardPhotoCutout.source_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/models_cutout.py:29` |
| `CardPhotoCutout.cutout_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:30` |
| `CardPhotoCutout.content_type (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:31` |
| `CardPhotoCutout.provider_scope (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:37` |
| `CardPhotoCutout.notice_version (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:42` |
| `CardPhotoEraserOptOut.notice_version (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:58` |
| `CardPhotoBatch.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/card_designs/models_cutout.py:72` |
| `CardPhotoBatch.state (models.CharField)` | `max_length=10; default=State.DRAFT` | field / model | `backend/apps/card_designs/models_cutout.py:76` |
| `CardPhotoBatchItem.filename (models.CharField)` | `max_length=200` | field / model | `backend/apps/card_designs/models_cutout.py:107` |
| `CardPhotoBatchItem.file_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:108` |
| `CardPhotoBatchItem.match_kind (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:110` |
| `CardPhotoBatchItem.decision (models.CharField)` | `max_length=8; default=Decision.APPLY` | field / model | `backend/apps/card_designs/models_cutout.py:114` |
| `CardPhotoBatchItem.state (models.CharField)` | `max_length=8; default=State.PENDING` | field / model | `backend/apps/card_designs/models_cutout.py:115` |
| `CardPhotoBatchItem.error_code (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/card_designs/models_cutout.py:116` |
| `CardDesign.domain (models.CharField)` | `max_length=16` | field / model | `backend/apps/card_designs/models_designs.py:36` |
| `CardDesign.name (models.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/card_designs/models_designs.py:37` |
| `CardDesign.card_role (models.CharField)` | `max_length=12` | field / model | `backend/apps/card_designs/models_designs.py:52` |
| `CardDesign.status (models.CharField)` | `max_length=20; default=Status.DRAFT` | field / model | `backend/apps/card_designs/models_designs.py:53` |
| `CardDesignApproval.decision (models.CharField)` | `max_length=12; default=Decision.PENDING` | field / model | `backend/apps/card_designs/models_designs.py:158` |
| `CardDesignApproval.note (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/card_designs/models_designs.py:159` |
| `CardDesignAsset.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/card_designs/models_designs.py:180` |
| `CardDesignAsset.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/models_designs.py:181` |
| `CardDesignAsset.content_type (models.CharField)` | `max_length=32` | field / model | `backend/apps/card_designs/models_designs.py:182` |
| `CardDesignAsset.sha256 (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/card_designs/models_designs.py:184` |
| `CardDesignAsset.mean_colour (models.CharField)` | `max_length=7; default=''` | field / model | `backend/apps/card_designs/models_designs.py:187` |
| `CardFont.family (models.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/models_fonts.py:15` |
| `CardFont.state (models.CharField)` | `max_length=8; default=State.PENDING` | field / model | `backend/apps/card_designs/models_fonts.py:17` |
| `CardFont.font_key (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/card_designs/models_fonts.py:18` |
| `CardFont.sha256 (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/card_designs/models_fonts.py:19` |
| `CardFont.error (models.CharField)` | `max_length=48; default=''` | field / model | `backend/apps/card_designs/models_fonts.py:21` |
| `CardVerifyToken.token (models.CharField)` | `max_length=43` | field / model | `backend/apps/card_designs/models_holders.py:70` |
| `CardVerifyToken.retired_reason (models.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/card_designs/models_holders.py:73` |
| `CardHolderExtras.consent_version (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/card_designs/models_holders.py:96` |
| `CardPhotoRequest.reason (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/card_designs/models_holders.py:107` |
| `ImageAdapterFields.provider_url (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/card_designs/models_image_adapter.py:16` |
| `ImageAdapterFields.secret_fingerprint (models.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/card_designs/models_image_adapter.py:18` |
| `ImageAdapterFields.last_test_error (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/card_designs/models_image_adapter.py:21` |
| `CardJob.kind (models.CharField)` | `max_length=20` | field / model | `backend/apps/card_designs/models_jobs.py:32` |
| `CardJob.scope (models.CharField)` | `max_length=20; default='member_cards'` | field / model | `backend/apps/card_designs/models_jobs.py:34` |
| `CardJob.idempotency_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/card_designs/models_jobs.py:41` |
| `CardJob.state (models.CharField)` | `max_length=12; default=State.QUEUED` | field / model | `backend/apps/card_designs/models_jobs.py:46` |
| `CardJob.error_code (models.CharField)` | `max_length=48; default=''` | field / model | `backend/apps/card_designs/models_jobs.py:47` |
| `CardJob.result_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/card_designs/models_jobs.py:50` |
| `CardJob.result_content_type (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/card_designs/models_jobs.py:52` |
| `CardNumberScheme.prefix (models.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/card_designs/models_numbering.py:15` |
| `CardNumberScheme.pattern (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/card_designs/models_numbering.py:16` |
| `CardNumberScheme.draft_prefix (models.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/card_designs/models_numbering.py:17` |
| `CardNumberScheme.draft_pattern (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/card_designs/models_numbering.py:18` |
| `CardNumberCounter.scheme_key (models.CharField)` | `max_length=32` | field / model | `backend/apps/card_designs/models_numbering.py:38` |
| `CardApprovalSetting.group (models.CharField)` | `max_length=12` | field / model | `backend/apps/card_designs/models_policy.py:19` |
| `StaffCard.number_text (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/card_designs/models_staff_cards.py:20` |
| `StaffCard.revoked_reason (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/card_designs/models_staff_cards.py:26` |
| `StaffCardNumbering.prefix (models.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/card_designs/models_staff_cards.py:54` |
| `StaffCardNumbering.pattern (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/card_designs/models_staff_cards.py:55` |
| `CardTemplate.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/models_templates.py:18` |
| `CardTemplate.description (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/card_designs/models_templates.py:19` |
| `CardTemplate.kind (models.CharField)` | `max_length=12; default=Kind.CARD` | field / model | `backend/apps/card_designs/models_templates.py:20` |
| `CardTemplate.domain_hint (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/card_designs/models_templates.py:22` |
| `CardTemplate.stock (models.CharField)` | `max_length=24` | field / model | `backend/apps/card_designs/models_templates.py:23` |
| `CardTemplate.theme (models.CharField)` | `max_length=5; default='light'` | field / model | `backend/apps/card_designs/models_templates.py:24` |
| `WalletPass.platform (models.CharField)` | `max_length=8` | field / model | `backend/apps/card_designs/models_wallet.py:19` |
| `WalletPass.serial (models.CharField)` | `max_length=64` | field / model | `backend/apps/card_designs/models_wallet.py:20` |
| `WalletPass.auth_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/card_designs/models_wallet.py:21` |
| `WalletPass.pass_type_id (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/card_designs/models_wallet.py:22` |
| `WalletPass.content_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/card_designs/models_wallet.py:26` |
| `WalletDeviceRegistration.device_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/card_designs/models_wallet.py:43` |
| `WalletCredentialFields.apple_pass_type_id (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/card_designs/models_wallet_credentials.py:20` |
| `WalletCredentialFields.apple_team_id (models.CharField)` | `max_length=20; default=''` | field / model | `backend/apps/card_designs/models_wallet_credentials.py:21` |
| `WalletCredentialFields.apple_cert_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/card_designs/models_wallet_credentials.py:25` |
| `WalletCredentialFields.google_issuer_id (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/card_designs/models_wallet_credentials.py:27` |
| `WalletCredentialFields.google_class_prefix (models.CharField)` | `max_length=40; default='spaceworks_card'` | field / model | `backend/apps/card_designs/models_wallet_credentials.py:28` |
| `WalletCredentialFields.google_key_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/card_designs/models_wallet_credentials.py:30` |
| `MAX_LENGTH` | `32` | fixed / see setting | `backend/apps/card_designs/numbering.py:19` |
| `MAX_ATTEMPTS` | `50` | fixed / see setting | `backend/apps/card_designs/numbering.py:20` |
| `MAX_OPEN_BATCHES` | `5` | fixed / see setting | `backend/apps/card_designs/photo_batch.py:30` |
| `MAX_HOLDERS` | `5000` | fixed / see setting | `backend/apps/card_designs/photo_batch_holders.py:13` |
| `MAX_FILES` | `500` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:18` |
| `MAX_ZIP_BYTES` | `200 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:19` |
| `MAX_ZIP_ENTRIES` | `2000` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:20` |
| `MAX_ZIP_UNCOMPRESSED` | `600 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:21` |
| `MAX_RATIO` | `100` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:22` |
| `MAX_ZIPS_PER_REQUEST` | `1` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:23` |
| `MAX_REQUEST_BYTES` | `MAX_ZIP_UNCOMPRESSED` | fixed / see setting | `backend/apps/card_designs/photo_batch_intake.py:24` |
| `MAX_BLEED_MM` | `5.0` | fixed / see setting | `backend/apps/card_designs/print_export.py:17` |
| `MAX_EDGE_PX` | `3200` | fixed / see setting | `backend/apps/card_designs/rendering_media.py:12` |
| `CardDesignSaveSerializer.revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers.py:110` |
| `CardDesignSaveSerializer.name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/serializers.py:111` |
| `CardDesignDecisionSerializer.note (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/serializers.py:115` |
| `CardPreviewSerializer.holder_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers.py:137` |
| `CardPreviewSerializer.bleed_mm (serializers.FloatField)` | `min_value=0, max_value=5; default=0` | field / model | `backend/apps/card_designs/serializers.py:139` |
| `CardJobCreateSerializer.card_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers.py:196` |
| `CardJobCreateSerializer.card_ids (serializers.ListField)` | `max_length=1000` | field / model | `backend/apps/card_designs/serializers.py:196` |
| `CardJobCreateSerializer.expiring_within_days (serializers.IntegerField)` | `min_value=1, max_value=90` | field / model | `backend/apps/card_designs/serializers.py:199` |
| `CardJobCreateSerializer.roles (serializers.ListField)` | `max_length=7` | field / model | `backend/apps/card_designs/serializers.py:200` |
| `CardDesignRestoreSerializer.revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_history.py:31` |
| `SheetPreviewRequestSerializer.card_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_history.py:58` |
| `SheetPreviewRequestSerializer.card_ids (serializers.ListField)` | `max_length=1000` | field / model | `backend/apps/card_designs/serializers_history.py:58` |
| `SheetPreviewRequestSerializer.plan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_history.py:59` |
| `SheetPreviewRequestSerializer.expiring_within_days (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/card_designs/serializers_history.py:60` |
| `SheetPreviewRequestSerializer.roles (serializers.ListField)` | `max_length=7` | field / model | `backend/apps/card_designs/serializers_history.py:61` |
| `ImageAdapterInputSerializer.provider_url (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/serializers_image_adapter.py:7` |
| `ImageAdapterInputSerializer.secret (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/card_designs/serializers_image_adapter.py:8` |
| `BatchFilesSerializer.files (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/card_designs/serializers_image_adapter.py:72` |
| `CardCsvMergeSerializer.csv (serializers.CharField)` | `max_length=256 * 1024` | field / model | `backend/apps/card_designs/serializers_library.py:32` |
| `CardBarcodeRequestSerializer.value (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/serializers_library.py:53` |
| `ReasonSerializer.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/serializers_openapi.py:96` |
| `StaffCardIssueSerializer.membership_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:35` |
| `StaffCardBulkIssueSerializer.membership_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:39` |
| `StaffCardBulkIssueSerializer.membership_ids (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:39` |
| `StaffCardReasonSerializer.reason (serializers.CharField)` | `max_length=32; default='revoked'` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:53` |
| `StaffCardNumberingSerializer.prefix (serializers.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:57` |
| `StaffCardNumberingSerializer.pattern (serializers.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:58` |
| `StaffCardJobCreateSerializer.card_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:71` |
| `StaffCardJobCreateSerializer.card_ids (serializers.ListField)` | `max_length=1000` | field / model | `backend/apps/card_designs/serializers_staff_cards.py:71` |
| `TemplateCreateSerializer.design_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_templates.py:28` |
| `TemplateCreateSerializer.name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/serializers_templates.py:32` |
| `TemplateCreateSerializer.description (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/card_designs/serializers_templates.py:33` |
| `TemplateUpdateSerializer.name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/serializers_templates.py:42` |
| `TemplateUpdateSerializer.description (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/card_designs/serializers_templates.py:43` |
| `TemplateApplySerializer.expected_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/serializers_templates.py:64` |
| `MAX_CARDS_PER_PDF` | `1000` | fixed / see setting | `backend/apps/card_designs/sheets.py:17` |
| `MAX_NAMES` | `4` | fixed / see setting | `backend/apps/card_designs/staff_card_roles.py:13` |
| `CERTIFICATE_CUSTOM_MAX_MM` | `420.0` | fixed / see setting | `backend/apps/card_designs/stocks.py:39` |
| `CUSTOM_MAX_MM` | `300.0` | fixed / see setting | `backend/apps/card_designs/stocks.py:44` |
| `MAX_OBJECT_BYTES` | `200 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/storage.py:21` |
| `MAX_ASSETS` | `12` | fixed / see setting | `backend/apps/card_designs/templates_files.py:28` |
| `MAX_TOTAL_BYTES` | `6 * 1024 * 1024` | fixed / see setting | `backend/apps/card_designs/templates_files.py:29` |
| `MAX_ORGANISATIONS` | `200` | fixed / see setting | `backend/apps/card_designs/views_approval.py:32` |
| `ApprovalLevelWriteSerializer.organization_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/card_designs/views_approval.py:56` |
| `CardSettingsSerializer.blood_group (serializers.CharField)` | `max_length=3` | field / model | `backend/apps/card_designs/views_holder.py:51` |
| `CardSettingsSerializer.emergency_contact_name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/card_designs/views_holder.py:52` |
| `CardSettingsSerializer.emergency_contact_phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/card_designs/views_holder.py:53` |
| `PhotoFinalizeSerializer.object_key (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/views_holder_photo.py:34` |
| `StaffPhotoFinalizeSerializer.object_key (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/card_designs/views_staff_photo.py:32` |
| `NumberSchemeWriteSerializer.prefix (serializers.CharField)` | `max_length=6; default=''` | field / model | `backend/apps/card_designs/views_title_cards.py:49` |
| `NumberSchemeWriteSerializer.pattern (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/card_designs/views_title_cards.py:50` |
| `MAX_BYTES` | `64 * 1024` | fixed / see setting | `backend/apps/card_designs/wallet/credential_parsing.py:21` |
| `WalletCredentialsInputSerializer.apple_pass_type_id (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/card_designs/wallet/serializers.py:13` |
| `WalletCredentialsInputSerializer.apple_team_id (serializers.CharField)` | `max_length=20` | field / model | `backend/apps/card_designs/wallet/serializers.py:14` |
| `WalletCredentialsInputSerializer.google_issuer_id (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/card_designs/wallet/serializers.py:21` |
| `WalletCredentialsInputSerializer.google_class_prefix (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/card_designs/wallet/serializers.py:22` |
| `GuestPassScanInputSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/card_designs/wallet/serializers.py:75` |

</details>

<details>
<summary>data_export (6 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `DataExportJob.fidelity (models.CharField)` | `max_length=16; default='REDACTED'` | field / model | `backend/apps/data_export/models.py:56` |
| `DataExportJob.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/data_export/models.py:57` |
| `DataExportJob.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/data_export/models.py:60` |
| `DataExportJob.failure_code (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/data_export/models.py:63` |
| `DataExportJob.failure_detail (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/data_export/models.py:66` |
| `DataExportJob.download_token_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/data_export/models.py:72` |

</details>

<details>
<summary>deployment settings (242 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `JSON_LIMIT` | `20000` | fixed / see setting | `backend/config/admin_display.py:22` |
| `STORAGE_CAPABILITIES_FILE` | `default=''` | operator env | `backend/config/cloud_settings/configuration.py:12` |
| `FREE_TICK_INTERVAL_SECONDS` | `default=600` | operator env | `backend/config/cloud_settings/configuration.py:17` |
| `FREE_TICK_BUDGET_SECONDS` | `default=20` | operator env | `backend/config/cloud_settings/configuration.py:18` |
| `STORAGE_CAPABILITY_TTL_SECONDS` | `default=default` | operator env | `backend/config/cloud_settings/configuration.py:24` |
| `STORAGE_CAPABILITIES_FILE` | `default=''` | operator env | `backend/config/cloud_settings/configuration.py:35` |
| `MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS` | `default=0` | operator env | `backend/config/cloud_settings/configuration.py:48` |
| `UPLOAD_SCAN_POLICY` | `default='none' if selection.mode == 'managed' else ''` | operator env | `backend/config/cloud_settings/configuration.py:62` |
| `CLAMD_TIMEOUT_SECONDS` | `default=5` | operator env | `backend/config/cloud_settings/configuration.py:70` |
| `CLAMD_MAX_SCAN_BYTES` | `default=2147483648` | operator env | `backend/config/cloud_settings/configuration.py:71` |
| `FREE_EMAIL_MONTHLY_CAP` | `default=None` | operator env | `backend/config/cloud_settings/configuration.py:80` |
| `FREE_TICK_INGRESS_LIMIT_PER_MINUTE` | `default=120` | operator env | `backend/config/cloud_settings/configuration.py:83` |
| `FREE_MAX_PROMOTION_BYTES` | `default=16777216` | operator env | `backend/config/cloud_settings/configuration.py:84` |
| `OAUTH_ACCESS_TOKEN_SECONDS` | `default=3600` | operator env | `backend/config/oauth_settings.py:14` |
| `OAUTH_REFRESH_TOKEN_SECONDS` | `default=30 * 86400` | operator env | `backend/config/oauth_settings.py:15` |
| `THROTTLE_PERSON_TOKEN_MANAGE` | `default='30/hour'` | operator env | `backend/config/oauth_settings.py:52` |
| `THROTTLE_OAUTH_CONSENT` | `default='30/hour'` | operator env | `backend/config/oauth_settings.py:53` |
| `THROTTLE_API_CLIENT_MANAGE` | `default='120/hour'` | operator env | `backend/config/openapi_settings.py:78` |
| `FALLBACK_MAX_ENTRIES` | `10000` | fixed / see setting | `backend/config/redis_cache.py:35` |
| `_MAX_TIMESTAMP` | `4102444800` | fixed / see setting | `backend/config/sentry_privacy.py:17` |
| `FREE_TICK_INTERVAL_SECONDS` | `default=600` | operator env | `backend/config/settings.py:78` |
| `FREE_TICK_BUDGET_SECONDS` | `default=20` | operator env | `backend/config/settings.py:79` |
| `FREE_TICK_RATE_LIMIT_PER_MINUTE` | `default=6` | operator env | `backend/config/settings.py:80` |
| `FREE_DB_CAP_BYTES` | `default=None` | operator env | `backend/config/settings.py:81` |
| `FREE_OBJECT_CAP_BYTES` | `default=None` | operator env | `backend/config/settings.py:82` |
| `FREE_EMAIL_DAILY_CAP` | `default=None` | operator env | `backend/config/settings.py:83` |
| `THROTTLE_PAYMENT_CLAIMS` | `default='5/hour'` | operator env | `backend/config/settings.py:120` |
| `THROTTLE_PAY_LINKS` | `default='30/min'` | operator env | `backend/config/settings.py:121` |
| `THROTTLE_MINOR_PERSON_LOOKUP` | `default='60/min'` | operator env | `backend/config/settings.py:127` |
| `THROTTLE_PRICING_QUOTE` | `default='60/min'` | operator env | `backend/config/settings.py:128` |
| `THROTTLE_CARD_VERIFY` | `default='30/min'` | operator env | `backend/config/settings.py:150` |
| `THROTTLE_MEMBER_CARD_RESOLVE` | `default='60/min'` | operator env | `backend/config/settings.py:151` |
| `THROTTLE_ID_JOIN` | `default='10/min'` | operator env | `backend/config/settings.py:152` |
| `THROTTLE_ID_JOIN_UPLOAD` | `default='12/hour'` | operator env | `backend/config/settings.py:153` |
| `ADAPTER_ACCESS_CACHE_TTL_SECONDS` | `default=900` | operator env | `backend/config/settings.py:178` |
| `ADAPTER_ARTIFACT_RETENTION_DAYS` | `default={}` | operator env | `backend/config/settings.py:180` |
| `HMAC_MAX_CLOCK_SKEW_SECONDS` | `default=300` | operator env | `backend/config/settings_credentials.py:32` |
| `HMAC_MAX_CLOCK_SKEW_SECONDS` | `env.int('HMAC_MAX_CLOCK_SKEW_SECONDS', default=300)` | fixed / see setting | `backend/config/settings_credentials.py:32` |
| `DEVICE_SIGNATURE_MAX_SKEW_SECONDS` | `default=300` | operator env | `backend/config/settings_credentials.py:36` |
| `DEVICE_SIGNATURE_MAX_SKEW_SECONDS` | `env.int('DEVICE_SIGNATURE_MAX_SKEW_SECONDS', default=300)` | fixed / see setting | `backend/config/settings_credentials.py:36` |
| `DEVICE_ENROLLMENT_TTL_SECONDS` | `default=900` | operator env | `backend/config/settings_credentials.py:37` |
| `DEVICE_NONCE_TTL_SECONDS` | `default=86400` | operator env | `backend/config/settings_credentials.py:38` |
| `DEVICE_COMMAND_LEASE_SECONDS` | `default=60` | operator env | `backend/config/settings_credentials.py:39` |
| `DEVICE_COMMAND_MAX_ATTEMPTS` | `default=10` | operator env | `backend/config/settings_credentials.py:40` |
| `DEVICE_COMMAND_MAX_ATTEMPTS` | `env.int('DEVICE_COMMAND_MAX_ATTEMPTS', default=10)` | fixed / see setting | `backend/config/settings_credentials.py:40` |
| `KIOSK_STATION_SESSION_TTL_SECONDS` | `default=12 * 60 * 60` | operator env | `backend/config/settings_credentials.py:64` |
| `KIOSK_OPERATOR_LEASE_TTL_SECONDS` | `default=8 * 60 * 60` | operator env | `backend/config/settings_credentials.py:67` |
| `KIOSK_OPERATOR_LEASE_RETENTION_SECONDS` | `default=7 * 24 * 60 * 60` | operator env | `backend/config/settings_credentials.py:70` |
| `KIOSK_COMMAND_MAX_AGE_SECONDS` | `default=8 * 60 * 60` | operator env | `backend/config/settings_credentials.py:73` |
| `KIOSK_COMMAND_MAX_AGE_SECONDS` | `env.int('KIOSK_COMMAND_MAX_AGE_SECONDS', default=8 * 60 * 60)` | fixed / see setting | `backend/config/settings_credentials.py:73` |
| `KIOSK_REPLAY_RETENTION_SECONDS` | `default=7 * 24 * 60 * 60` | operator env | `backend/config/settings_credentials.py:74` |
| `KIOSK_REPLAY_CLAIM_TIMEOUT_SECONDS` | `default=5 * 60` | operator env | `backend/config/settings_credentials.py:75` |
| `KIOSK_REPLAY_CLEANUP_BATCH_SIZE` | `default=500` | operator env | `backend/config/settings_credentials.py:76` |
| `EVENT_CHECKIN_CLOCK_SKEW_SECONDS` | `default=300` | operator env | `backend/config/settings_credentials.py:89` |
| `EVENT_CHECKIN_ROSTER_MAX` | `default=1000` | operator env | `backend/config/settings_credentials.py:92` |
| `AUDIT_ATTESTATION_RETENTION_DAYS` | `default=2555` | operator env | `backend/config/settings_credentials.py:107` |
| `AUDIT_ATTESTATION_HTTP_TIMEOUT` | `default=10` | operator env | `backend/config/settings_credentials.py:129` |
| `PII_DEK_CACHE_TTL_SECONDS` | `default=300` | operator env | `backend/config/settings_credentials.py:139` |
| `PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS` | `default=2` | operator env | `backend/config/settings_credentials.py:167` |
| `LOGIN_IP_BLOCK_WINDOW_SECONDS` | `default=900` | operator env | `backend/config/settings_credentials.py:177` |
| `LOGIN_IP_BLOCK_SECONDS` | `default=3600` | operator env | `backend/config/settings_credentials.py:178` |
| `LOGIN_CODE_TTL_SECONDS` | `default=600` | operator env | `backend/config/settings_credentials.py:182` |
| `SECURITY_ALERT_LINK_TTL_DAYS` | `default=14` | operator env | `backend/config/settings_credentials.py:183` |
| `CONN_MAX_AGE` | `default=60` | operator env | `backend/config/settings_django.py:165` |
| `BACKUP_PRODUCER_CAPABILITY_MARKER_PATH` | `default='/run/spaceworks-host/producer-capability.json'` | operator env | `backend/config/settings_django.py:177` |
| `ACCOUNT_DELETION_RETENTION_DAYS` | `default=90` | operator env | `backend/config/settings_django.py:226` |
| `AXES_FAILURE_LIMIT` | `default=5` | operator env | `backend/config/settings_django.py:236` |
| `AXES_FAILURE_LIMIT` | `env.int('AXES_FAILURE_LIMIT', default=5)` | fixed / see setting | `backend/config/settings_django.py:236` |
| `THROTTLE_DEPLOYMENT_ANON` | `default='600/min'` | operator env | `backend/config/settings_drf.py:27` |
| `THROTTLE_DEPLOYMENT_USER` | `default='1200/min'` | operator env | `backend/config/settings_drf.py:28` |
| `THROTTLE_DEPLOYMENT_DEVICE` | `default='600/min'` | operator env | `backend/config/settings_drf.py:29` |
| `THROTTLE_PROFILE_LOOKUP` | `default='30/min'` | operator env | `backend/config/settings_drf.py:32` |
| `THROTTLE_PROFILE_LOOKUP_DAILY` | `default='500/day'` | operator env | `backend/config/settings_drf.py:33` |
| `THROTTLE_HANDLE_CHECK` | `default='20/min'` | operator env | `backend/config/settings_drf.py:34` |
| `THROTTLE_HANDLE_CHECK_DAILY` | `default='300/day'` | operator env | `backend/config/settings_drf.py:35` |
| `THROTTLE_LOGIN` | `default='10/min'` | operator env | `backend/config/settings_drf.py:36` |
| `THROTTLE_MFA_VERIFY` | `default='10/min'` | operator env | `backend/config/settings_drf.py:37` |
| `THROTTLE_MFA_CHALLENGE` | `default='10/min'` | operator env | `backend/config/settings_drf.py:38` |
| `THROTTLE_MFA_USER` | `default='20/hour'` | operator env | `backend/config/settings_drf.py:39` |
| `THROTTLE_MFA_MANAGE` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:40` |
| `THROTTLE_STAFF_INVITE` | `default='20/hour'` | operator env | `backend/config/settings_drf.py:41` |
| `THROTTLE_STAFF_INVITE_ACCEPT` | `default='10/min'` | operator env | `backend/config/settings_drf.py:42` |
| `THROTTLE_DEVICE_ATTESTATION_CHALLENGE` | `default='5/min'` | operator env | `backend/config/settings_drf.py:43` |
| `THROTTLE_DEVICE_LOGIN` | `default='5/min'` | operator env | `backend/config/settings_drf.py:44` |
| `THROTTLE_DEVICE_LOGIN_USER` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:45` |
| `THROTTLE_DEVICE_REFRESH` | `default='30/min'` | operator env | `backend/config/settings_drf.py:46` |
| `THROTTLE_PUSH_DEVICE_REGISTRATION` | `default='10/min'` | operator env | `backend/config/settings_drf.py:47` |
| `THROTTLE_SOCIAL_NONCE` | `default='10/min'` | operator env | `backend/config/settings_drf.py:48` |
| `THROTTLE_SOCIAL_LOGIN` | `default='10/min'` | operator env | `backend/config/settings_drf.py:49` |
| `THROTTLE_SOCIAL_LINK` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:50` |
| `THROTTLE_MEMBER_CLAIM_ISSUE` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:54` |
| `THROTTLE_AUDIT_VERIFICATION` | `default='6/hour'` | operator env | `backend/config/settings_drf.py:56` |
| `THROTTLE_MEMBER_CLAIM_REDEEM` | `default='10/min'` | operator env | `backend/config/settings_drf.py:57` |
| `THROTTLE_PHONE_OTP_REQUEST` | `default='5/min'` | operator env | `backend/config/settings_drf.py:60` |
| `THROTTLE_PHONE_OTP_NUMBER` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:61` |
| `THROTTLE_PHONE_LOGIN_CONFIRM` | `default='10/min'` | operator env | `backend/config/settings_drf.py:62` |
| `THROTTLE_PHONE_CONFIRM_NUMBER` | `default='15/hour'` | operator env | `backend/config/settings_drf.py:63` |
| `THROTTLE_PASSWORD_RESET_REQUEST` | `default='5/min'` | operator env | `backend/config/settings_drf.py:64` |
| `THROTTLE_PASSWORD_RESET_EMAIL` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:68` |
| `THROTTLE_PASSWORD_RESET_CONFIRM` | `default='10/min'` | operator env | `backend/config/settings_drf.py:72` |
| `THROTTLE_PASSWORD_RESET_CONFIRM_EMAIL` | `default='15/hour'` | operator env | `backend/config/settings_drf.py:76` |
| `THROTTLE_MEMBER_SIGN_UP` | `default='5/min'` | operator env | `backend/config/settings_drf.py:80` |
| `THROTTLE_EMAIL_VERIFICATION_RESEND` | `default='5/min'` | operator env | `backend/config/settings_drf.py:81` |
| `THROTTLE_EMAIL_VERIFICATION_CONFIRM` | `default='10/min'` | operator env | `backend/config/settings_drf.py:84` |
| `THROTTLE_MEMBER_VERIFICATION_EMAIL` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:87` |
| `THROTTLE_TELEGRAM_WEBHOOK` | `default='60/min'` | operator env | `backend/config/settings_drf.py:90` |
| `THROTTLE_ANTHIAS_PLAYER_CALL` | `default='20/min'` | operator env | `backend/config/settings_drf.py:91` |
| `THROTTLE_IMAGE_ADAPTER_TEST` | `default='10/min'` | operator env | `backend/config/settings_drf.py:92` |
| `THROTTLE_DEVICE_ADAPTER` | `default='300/min'` | operator env | `backend/config/settings_drf.py:93` |
| `THROTTLE_DEVICE_ADAPTER_CREDENTIAL` | `default='60/min'` | operator env | `backend/config/settings_drf.py:94` |
| `THROTTLE_ADAPTER_WATCH_START` | `default='10/min'` | operator env | `backend/config/settings_drf.py:95` |
| `THROTTLE_ADAPTER_WATCH_RELAY` | `default='300/min'` | operator env | `backend/config/settings_drf.py:96` |
| `THROTTLE_PUBLIC_REQUEST_SUBMIT` | `default='10/min'` | operator env | `backend/config/settings_drf.py:97` |
| `THROTTLE_ANONYMOUS_REQUEST_IP_BURST` | `default='5/min'` | operator env | `backend/config/settings_drf.py:101` |
| `THROTTLE_ANONYMOUS_REQUEST_IP_HOUR` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:105` |
| `THROTTLE_ANONYMOUS_REQUEST_EMAIL` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:109` |
| `THROTTLE_PUBLIC_INVITATION_REQUEST` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:113` |
| `THROTTLE_HOSTING_REQUEST_SUBMIT` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:116` |
| `THROTTLE_HOSTING_REQUEST_EMAIL` | `default='3/day'` | operator env | `backend/config/settings_drf.py:117` |
| `THROTTLE_HOSTING_REQUEST_TOKEN` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:118` |
| `THROTTLE_HOSTING_INVITATION_CREATE` | `default='20/hour'` | operator env | `backend/config/settings_drf.py:119` |
| `THROTTLE_PRINT_REQUEST_SUBMIT` | `default='10/min'` | operator env | `backend/config/settings_drf.py:120` |
| `THROTTLE_PUBLIC_TOOL_CHECKOUT` | `default='10/min'` | operator env | `backend/config/settings_drf.py:121` |
| `THROTTLE_PUBLIC_TOOL_RETURN` | `default='10/min'` | operator env | `backend/config/settings_drf.py:122` |
| `THROTTLE_REQUEST_SUBMIT` | `default='10/min'` | operator env | `backend/config/settings_drf.py:123` |
| `THROTTLE_REQUEST_STATUS` | `default='60/min'` | operator env | `backend/config/settings_drf.py:124` |
| `THROTTLE_PUBLIC_READ` | `default='120/min'` | operator env | `backend/config/settings_drf.py:125` |
| `THROTTLE_EVENT_REGISTER` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:126` |
| `THROTTLE_EVENT_REGISTRATION_RETRY` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:127` |
| `THROTTLE_EVENT_CHECKIN_RESOLVE` | `default='60/min'` | operator env | `backend/config/settings_drf.py:130` |
| `THROTTLE_EVENT_OFFLINE_ROSTER` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:133` |
| `THROTTLE_EVENT_OFFLINE_SYNC` | `default='60/hour'` | operator env | `backend/config/settings_drf.py:136` |
| `THROTTLE_EVENT_STATION_PIN_TOKEN` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:139` |
| `THROTTLE_EVENT_STATION_PIN_IP` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:142` |
| `THROTTLE_EVENT_STATION_SESSION` | `default='120/hour'` | operator env | `backend/config/settings_drf.py:145` |
| `THROTTLE_EVENT_STATION_REVEAL` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:148` |
| `THROTTLE_KIOSK_STATION_PIN_TOKEN` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:151` |
| `THROTTLE_KIOSK_STATION_PIN_IP` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:154` |
| `THROTTLE_KIOSK_STATION_SESSION` | `default='120/hour'` | operator env | `backend/config/settings_drf.py:157` |
| `THROTTLE_KIOSK_OPERATOR_LEASE` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:160` |
| `THROTTLE_KIOSK_REPLAY_PREPARE` | `default='60/hour'` | operator env | `backend/config/settings_drf.py:163` |
| `THROTTLE_KIOSK_REPLAY_EXECUTE` | `default='240/hour'` | operator env | `backend/config/settings_drf.py:164` |
| `THROTTLE_EVENT_CALENDAR_FEED_TOKEN` | `default='120/hour'` | operator env | `backend/config/settings_drf.py:167` |
| `THROTTLE_EVENT_CALENDAR_FEED_IP` | `default='300/hour'` | operator env | `backend/config/settings_drf.py:170` |
| `THROTTLE_PUBLIC_STATS` | `default='30/min'` | operator env | `backend/config/settings_drf.py:173` |
| `THROTTLE_CLIENT_PUBLIC` | `default='30/min'` | operator env | `backend/config/settings_drf.py:174` |
| `THROTTLE_CLIENT_STANDARD` | `default='120/min'` | operator env | `backend/config/settings_drf.py:175` |
| `THROTTLE_CLIENT_TRUSTED` | `default='600/min'` | operator env | `backend/config/settings_drf.py:176` |
| `THROTTLE_BOOKING_SUBMIT` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:177` |
| `THROTTLE_MEMBERSHIP_REQUEST` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:178` |
| `THROTTLE_PRESENCE_START` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:179` |
| `THROTTLE_MEMBER_IMAGE_PRESIGN` | `default='20/hour'` | operator env | `backend/config/settings_drf.py:184` |
| `THROTTLE_DATA_EXPORT_CREATE` | `default='3/hour'` | operator env | `backend/config/settings_drf.py:185` |
| `THROTTLE_TENANT_MIGRATION_READ` | `default='120/min'` | operator env | `backend/config/settings_drf.py:186` |
| `THROTTLE_TENANT_MIGRATION_WRITE` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:189` |
| `THROTTLE_TENANT_MIGRATION_UPLOAD` | `default='1200/min'` | operator env | `backend/config/settings_drf.py:192` |
| `THROTTLE_EVENT_SHORT_LINK` | `default='30/min'` | operator env | `backend/config/settings_drf.py:196` |
| `THROTTLE_LOGIN_CODE_RESEND` | `default='5/hour'` | operator env | `backend/config/settings_drf.py:198` |
| `THROTTLE_LOGIN_CODE_IP` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:199` |
| `THROTTLE_PASSKEY_OPTIONS` | `default='30/min'` | operator env | `backend/config/settings_drf.py:200` |
| `THROTTLE_PASSKEY_VERIFY` | `default='10/min'` | operator env | `backend/config/settings_drf.py:201` |
| `THROTTLE_SECURITY_ALERT_ACTION` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:202` |
| `THROTTLE_ACCOUNT_MERGE_START` | `default='10/hour'` | operator env | `backend/config/settings_drf.py:204` |
| `THROTTLE_ACCOUNT_MERGE_PROVE` | `default='30/hour'` | operator env | `backend/config/settings_drf.py:205` |
| `SECURE_HSTS_SECONDS` | `default=31536000 if ENABLE_HTTPS else 0` | operator env | `backend/config/settings_http.py:29` |
| `DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS` | `default=180` | operator env | `backend/config/settings_http.py:97` |
| `DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS` | `default=10` | operator env | `backend/config/settings_http.py:98` |
| `SOCIAL_AUTH_NONCE_TTL_SECONDS` | `default=300` | operator env | `backend/config/settings_http.py:100` |
| `SOCIAL_AUTH_CLOCK_SKEW_SECONDS` | `default=60` | operator env | `backend/config/settings_http.py:101` |
| `SOCIAL_AUTH_JWKS_TIMEOUT_SECONDS` | `default=5` | operator env | `backend/config/settings_http.py:102` |
| `SOCIAL_AUTH_JWKS_CACHE_SECONDS` | `default=3600` | operator env | `backend/config/settings_http.py:103` |
| `SOCIAL_AUTH_JWKS_MAX_BYTES` | `default=1048576` | operator env | `backend/config/settings_http.py:104` |
| `SOCIAL_AUTH_JWKS_MAX_BYTES` | `env.int('SOCIAL_AUTH_JWKS_MAX_BYTES', default=1048576)` | fixed / see setting | `backend/config/settings_http.py:104` |
| `OIDC_ATTEMPT_TTL_SECONDS` | `default=300` | operator env | `backend/config/settings_http.py:105` |
| `OIDC_HTTP_TIMEOUT_SECONDS` | `default=5` | operator env | `backend/config/settings_http.py:106` |
| `OIDC_HTTP_MAX_BYTES` | `default=65536` | operator env | `backend/config/settings_http.py:107` |
| `OIDC_HTTP_MAX_BYTES` | `env.int('OIDC_HTTP_MAX_BYTES', default=65536)` | fixed / see setting | `backend/config/settings_http.py:107` |
| `OIDC_DISCOVERY_CACHE_SECONDS` | `default=300` | operator env | `backend/config/settings_http.py:108` |
| `MEMBER_CLAIM_CODE_TTL_SECONDS` | `default=15 * 60` | operator env | `backend/config/settings_http.py:109` |
| `MEMBER_CLAIM_SESSION_TTL_SECONDS` | `default=12 * 60 * 60` | operator env | `backend/config/settings_http.py:112` |
| `LIVE_MAX_STREAM_SECONDS` | `default=3600` | operator env | `backend/config/settings_observability.py:18` |
| `LIVE_MAX_STREAM_SECONDS` | `env.int('LIVE_MAX_STREAM_SECONDS', default=3600)` | fixed / see setting | `backend/config/settings_observability.py:18` |
| `MFA_CHALLENGE_TTL_SECONDS` | `default=300` | operator env | `backend/config/settings_observability.py:67` |
| `MFA_MAX_ATTEMPTS` | `default=5` | operator env | `backend/config/settings_observability.py:68` |
| `MFA_MAX_ATTEMPTS` | `env.int('MFA_MAX_ATTEMPTS', default=5)` | fixed / see setting | `backend/config/settings_observability.py:68` |
| `ORGANIZATION_SELF_CREATION_MAX_OWNED` | `default=3` | operator env | `backend/config/settings_observability.py:85` |
| `ORGANIZATION_SELF_CREATION_MAX_OWNED` | `env.int('ORGANIZATION_SELF_CREATION_MAX_OWNED', default=3)` | fixed / see setting | `backend/config/settings_observability.py:85` |
| `ORGANIZATION_SELF_CREATION_MAX_PER_DAY` | `default=1` | operator env | `backend/config/settings_observability.py:86` |
| `ORGANIZATION_SELF_CREATION_MAX_PER_DAY` | `env.int('ORGANIZATION_SELF_CREATION_MAX_PER_DAY', default=1)` | fixed / see setting | `backend/config/settings_observability.py:86` |
| `DATA_EXPORT_DEADLINE_SECONDS` | `default=900` | operator env | `backend/config/settings_recovery.py:8` |
| `DATA_EXPORT_PAGE_SIZE` | `default=500` | operator env | `backend/config/settings_recovery.py:9` |
| `DATA_EXPORT_RETENTION_SECONDS` | `default=7 * 24 * 60 * 60` | operator env | `backend/config/settings_recovery.py:10` |
| `DATA_EXPORT_DOWNLOAD_TTL_SECONDS` | `default=5 * 60` | operator env | `backend/config/settings_recovery.py:13` |
| `TENANT_MIGRATION_GATE_LEASE_SECONDS` | `default=2 * 60 * 60` | operator env | `backend/config/settings_recovery.py:16` |
| `TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS` | `default=max(EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECONDS)` | operator env | `backend/config/settings_recovery.py:19` |
| `BACKUP_DOWNLOAD_TTL_SECONDS` | `default=5 * 60` | operator env | `backend/config/settings_recovery.py:39` |
| `BACKUP_LEASE_SECONDS` | `default=2 * 60 * 60` | operator env | `backend/config/settings_recovery.py:40` |
| `BACKUP_DECISION_SECONDS` | `default=5 * 60` | operator env | `backend/config/settings_recovery.py:41` |
| `BACKUP_PRESIGN_DRAIN_SECONDS` | `default=max(EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECONDS)` | operator env | `backend/config/settings_recovery.py:42` |
| `TENANT_DUMP_STAGING_MAX_AGE_SECONDS` | `default=7 * 24 * 60 * 60` | operator env | `backend/config/settings_recovery.py:48` |
| `TENANT_DUMP_STAGING_MAX_AGE_SECONDS` | `env.int('TENANT_DUMP_STAGING_MAX_AGE_SECONDS', default=7 * 24 * 60 * 60)` | fixed / see setting | `backend/config/settings_recovery.py:48` |
| `REMINDER_SWEEP_BATCH_SIZE` | `default=200` | operator env | `backend/config/settings_recovery.py:52` |
| `DOMAIN_CHANGE_COOLDOWN_SECONDS` | `default=0` | operator env | `backend/config/settings_runtime.py:90` |
| `MANAGED_OTP_EMAIL_DAILY_LIMIT` | `default=200` | operator env | `backend/config/settings_runtime.py:127` |
| `MANAGED_OTP_SMS_DAILY_LIMIT` | `default=100` | operator env | `backend/config/settings_runtime.py:128` |
| `OTP_SMS_DAILY_CAP` | `default=200` | operator env | `backend/config/settings_runtime.py:133` |
| `OTP_SMS_DAILY_CAP` | `env.int('OTP_SMS_DAILY_CAP', default=200)` | fixed / see setting | `backend/config/settings_runtime.py:133` |
| `EVIDENCE_URL_TTL_SECONDS` | `default=300` | operator env | `backend/config/settings_storage.py:28` |
| `REPORT_DELIVERY_URL_TTL_SECONDS` | `default=6 * 60 * 60` | operator env | `backend/config/settings_storage.py:32` |
| `EVIDENCE_MAX_BYTES` | `default=10485760` | operator env | `backend/config/settings_storage.py:33` |
| `EVIDENCE_MAX_BYTES` | `env.int('EVIDENCE_MAX_BYTES', default=10485760)` | fixed / see setting | `backend/config/settings_storage.py:33` |
| `EVIDENCE_ALLOWED_MIME` | `['image/jpeg', 'image/png', 'image/webp']` | fixed / see setting | `backend/config/settings_storage.py:34` |
| `EVIDENCE_OBJECT_RETENTION_DAYS` | `default=365` | operator env | `backend/config/settings_storage.py:35` |
| `EVIDENCE_RETENTION_BATCH_SIZE` | `default=100` | operator env | `backend/config/settings_storage.py:41` |
| `EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED` | `default=False` | operator env | `backend/config/settings_storage.py:44` |
| `EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS` | `default=7` | operator env | `backend/config/settings_storage.py:47` |
| `EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS` | `default=2555` | operator env | `backend/config/settings_storage.py:53` |
| `EVENT_REIMBURSEMENT_FILE_MAX_BYTES` | `default=10485760` | operator env | `backend/config/settings_storage.py:55` |
| `EVENT_REIMBURSEMENT_FILE_MAX_BYTES` | `env.int('EVENT_REIMBURSEMENT_FILE_MAX_BYTES', default=10485760)` | fixed / see setting | `backend/config/settings_storage.py:55` |
| `EVENT_STAGE_FILE_RETENTION_DAYS` | `default=365` | operator env | `backend/config/settings_storage.py:58` |
| `EVENT_STAGE_MEMBER_QUOTA_BYTES` | `default=104857600` | operator env | `backend/config/settings_storage.py:59` |
| `EVENT_STAGE_MEMBER_QUOTA_BYTES` | `env.int('EVENT_STAGE_MEMBER_QUOTA_BYTES', default=104857600)` | fixed / see setting | `backend/config/settings_storage.py:59` |
| `EVENT_STAGE_EVENT_QUOTA_BYTES` | `default=1073741824` | operator env | `backend/config/settings_storage.py:60` |
| `EVENT_STAGE_EVENT_QUOTA_BYTES` | `env.int('EVENT_STAGE_EVENT_QUOTA_BYTES', default=1073741824)` | fixed / see setting | `backend/config/settings_storage.py:60` |
| `WARRANTY_DOC_MAX_BYTES` | `default=10485760` | operator env | `backend/config/settings_storage.py:70` |
| `WARRANTY_DOC_MAX_BYTES` | `env.int('WARRANTY_DOC_MAX_BYTES', default=10485760)` | fixed / see setting | `backend/config/settings_storage.py:70` |
| `WARRANTY_DOC_ALLOWED_MIME` | `default=['application/pdf', 'image/jpeg', 'image/png', 'image/webp']` | operator env | `backend/config/settings_storage.py:71` |
| `WARRANTY_DOC_ALLOWED_MIME` | `env.list('WARRANTY_DOC_ALLOWED_MIME', default=['application/pdf', 'image/jpeg', 'image/png', 'image/webp'])` | fixed / see setting | `backend/config/settings_storage.py:71` |
| `MACHINE_DOC_MAX_BYTES` | `default=10485760` | operator env | `backend/config/settings_storage.py:75` |
| `MACHINE_DOC_MAX_BYTES` | `env.int('MACHINE_DOC_MAX_BYTES', default=10485760)` | fixed / see setting | `backend/config/settings_storage.py:75` |
| `MACHINE_DOC_ALLOWED_MIME` | `default=['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'application/octet-stream', 'model/stl', 'application/sla', 'application/vnd.ms-pki.stl', 'model/3mf', 'application/vnd.ms-package.3dmanufacturing-3dmodel+xml', 'application/vnd.ms-3mfdocument', 'application/step', 'model/step', 'model/obj', 'application/xml', 'text/xml', 'application/x-amf', 'model/amf', 'application/x-ply', 'model/ply', 'text/x.gcode', 'application/x-gcode', 'application/iges', 'model/iges', 'image/vnd.dxf', 'application/dxf', 'application/x-dxf', 'text/plain']` | operator env | `backend/config/settings_storage.py:83` |
| `PROCUREMENT_RECEIPT_MAX_BYTES` | `default=10485760` | operator env | `backend/config/settings_storage.py:97` |
| `PROCUREMENT_RECEIPT_MAX_BYTES` | `env.int('PROCUREMENT_RECEIPT_MAX_BYTES', default=10485760)` | fixed / see setting | `backend/config/settings_storage.py:97` |
| `PROCUREMENT_RECEIPT_ALLOWED_MIME` | `default=['application/pdf', 'image/jpeg', 'image/png', 'image/webp']` | operator env | `backend/config/settings_storage.py:98` |
| `PROCUREMENT_RECEIPT_ALLOWED_MIME` | `env.list('PROCUREMENT_RECEIPT_ALLOWED_MIME', default=['application/pdf', 'image/jpeg', 'image/png', 'image/webp'])` | fixed / see setting | `backend/config/settings_storage.py:98` |
| `PUBLIC_IMAGE_MAX_BYTES` | `default=10485760` | operator env | `backend/config/settings_storage.py:105` |
| `PUBLIC_IMAGE_MAX_BYTES` | `env.int('PUBLIC_IMAGE_MAX_BYTES', default=10485760)` | fixed / see setting | `backend/config/settings_storage.py:105` |
| `PUBLIC_IMAGE_URL_TTL_SECONDS` | `default=300` | operator env | `backend/config/settings_storage.py:106` |
| `PUBLIC_IMAGE_ALLOWED_MIME` | `{'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'], 'image/webp': ['.webp']}` | fixed / see setting | `backend/config/settings_storage.py:107` |
| `PRINT_UPLOAD_MAX_BYTES` | `default=104857600` | operator env | `backend/config/settings_storage.py:112` |
| `PRINT_UPLOAD_MAX_BYTES` | `env.int('PRINT_UPLOAD_MAX_BYTES', default=104857600)` | fixed / see setting | `backend/config/settings_storage.py:112` |
| `PRINT_ALLOWED_MODEL_MIME` | `default=['application/octet-stream', 'model/stl', 'application/sla', 'application/vnd.ms-pki.stl', 'model/3mf', 'application/vnd.ms-package.3dmanufacturing-3dmodel+xml', 'application/vnd.ms-3mfdocument', 'application/step', 'model/step', 'model/obj', 'application/xml', 'text/xml', 'application/x-amf', 'model/amf', 'application/x-ply', 'model/ply', 'text/x.gcode', 'application/x-gcode', 'application/iges', 'model/iges', 'image/vnd.dxf', 'application/dxf', 'application/x-dxf', 'text/plain']` | operator env | `backend/config/settings_storage.py:120` |

</details>

<details>
<summary>devices (181 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `AdapterProfile.adapter_kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_adapter.py:24` |
| `AdapterProfile.vendor (models.CharField)` | `max_length=80` | field / model | `backend/apps/devices/models_adapter.py:25` |
| `AdapterProfile.software_version (models.CharField)` | `max_length=40` | field / model | `backend/apps/devices/models_adapter.py:26` |
| `AdapterProfile.firmware (models.CharField)` | `max_length=40` | field / model | `backend/apps/devices/models_adapter.py:27` |
| `AdapterProfile.health (models.CharField)` | `max_length=12` | field / model | `backend/apps/devices/models_adapter.py:28` |
| `AdapterBinding.target_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_adapter.py:50` |
| `AdapterBinding.target_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_adapter.py:54` |
| `AdapterBinding.external_ref (models.CharField)` | `max_length=120` | field / model | `backend/apps/devices/models_adapter.py:55` |
| `AdapterStatus.state (models.CharField)` | `max_length=16` | field / model | `backend/apps/devices/models_adapter.py:80` |
| `AdapterCommand.capability (models.CharField)` | `max_length=32` | field / model | `backend/apps/devices/models_adapter.py:101` |
| `AdapterCommand.command (models.CharField)` | `max_length=32` | field / model | `backend/apps/devices/models_adapter.py:102` |
| `AdapterCommand.status (models.CharField)` | `max_length=12; default=Status.QUEUED` | field / model | `backend/apps/devices/models_adapter.py:104` |
| `AdapterCommand.lease_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_adapter.py:106` |
| `AdapterCommand.result_code (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter.py:109` |
| `AdapterEvent.event_type (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter.py:131` |
| `AdapterEvent.capability (models.CharField)` | `max_length=32` | field / model | `backend/apps/devices/models_adapter.py:132` |
| `AdapterCredential.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/devices/models_adapter_ext.py:27` |
| `AdapterCredential.digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_adapter_ext.py:28` |
| `AdapterCredential.label (models.CharField)` | `max_length=60` | field / model | `backend/apps/devices/models_adapter_ext.py:29` |
| `AdapterPose.target_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_adapter_ext.py:52` |
| `AdapterPose.target_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_adapter_ext.py:53` |
| `AdapterPose.note (models.CharField)` | `max_length=80` | field / model | `backend/apps/devices/models_adapter_ext.py:55` |
| `AdapterAccessLog.credential_type (models.CharField)` | `max_length=8` | field / model | `backend/apps/devices/models_adapter_ext.py:74` |
| `AdapterAccessLog.reason (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter_ext.py:76` |
| `AdapterUsageLog.outcome (models.CharField)` | `max_length=12` | field / model | `backend/apps/devices/models_adapter_ext.py:108` |
| `AdapterUsageLog.error_code (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter_ext.py:109` |
| `AdapterWatch.status (models.CharField)` | `max_length=8; default=Status.ACTIVE` | field / model | `backend/apps/devices/models_adapter_ext.py:135` |
| `AdapterWatch.recording_key (models.CharField)` | `max_length=200` | field / model | `backend/apps/devices/models_adapter_ext.py:145` |
| `AdapterArtifact.kind (models.CharField)` | `max_length=20` | field / model | `backend/apps/devices/models_adapter_media.py:27` |
| `AdapterArtifact.content_type (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_adapter_media.py:28` |
| `AdapterArtifact.object_key (models.CharField)` | `max_length=200` | field / model | `backend/apps/devices/models_adapter_media.py:30` |
| `AdapterArtifact.status (models.CharField)` | `max_length=8; default=Status.PENDING` | field / model | `backend/apps/devices/models_adapter_media.py:31` |
| `AdapterTelemetryPoint.series (models.CharField)` | `max_length=80` | field / model | `backend/apps/devices/models_adapter_media.py:55` |
| `AdapterConfigVersion.ack_outcome (models.CharField)` | `max_length=8` | field / model | `backend/apps/devices/models_adapter_media.py:96` |
| `AdapterConfigVersion.ack_detail (models.CharField)` | `max_length=200` | field / model | `backend/apps/devices/models_adapter_media.py:97` |
| `AdapterWebhook.url (models.CharField)` | `max_length=500` | field / model | `backend/apps/devices/models_adapter_push.py:20` |
| `AdapterWebhook.disabled_reason (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter_push.py:26` |
| `AdapterWebhookDelivery.event_type (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter_push.py:44` |
| `AdapterWebhookDelivery.status (models.CharField)` | `max_length=12; default=Status.PENDING` | field / model | `backend/apps/devices/models_adapter_push.py:46` |
| `AdapterWebhookDelivery.last_error (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_adapter_push.py:50` |
| `DeviceCommand.kind (models.CharField)` | `max_length=32; default='printer_job'` | field / model | `backend/apps/devices/models_commands.py:23` |
| `DeviceCommand.status (models.CharField)` | `max_length=24; default=Status.QUEUED` | field / model | `backend/apps/devices/models_commands.py:24` |
| `DeviceCommand.lease_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_commands.py:27` |
| `DeviceCommand.last_error_code (models.CharField)` | `max_length=48` | field / model | `backend/apps/devices/models_commands.py:30` |
| `DeviceEvent.device_id_snapshot (models.CharField)` | `max_length=36` | field / model | `backend/apps/devices/models_events.py:53` |
| `DeviceEvent.device_name (models.CharField)` | `max_length=120` | field / model | `backend/apps/devices/models_events.py:54` |
| `DeviceEvent.event_type (models.CharField)` | `max_length=32` | field / model | `backend/apps/devices/models_events.py:57` |
| `DeviceEvent.outcome (models.CharField)` | `max_length=32; default='ok'` | field / model | `backend/apps/devices/models_events.py:58` |
| `Device.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_identity.py:36` |
| `Device.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/devices/models_identity.py:37` |
| `Device.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/devices/models_identity.py:38` |
| `Device.public_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_identity.py:41` |
| `Device.key_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_identity.py:43` |
| `DeviceEnrollment.purpose (models.CharField)` | `max_length=16` | field / model | `backend/apps/devices/models_identity.py:99` |
| `DeviceEnrollment.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_identity.py:100` |
| `DeviceEnrollment.candidate_key_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/devices/models_identity.py:101` |
| `DeviceEnrollment.challenge_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/devices/models_identity.py:102` |
| `DeviceRequestNonce.nonce_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_identity.py:129` |
| `MachineTypeIntegration.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_integrations.py:31` |
| `PrinterStatusSnapshot.state (models.CharField)` | `max_length=16` | field / model | `backend/apps/devices/models_integrations.py:64` |
| `PrinterStatusSnapshot.nozzle_temp_c (models.DecimalField)` | `max_digits=5` | field / model | `backend/apps/devices/models_integrations.py:68` |
| `PrinterStatusSnapshot.bed_temp_c (models.DecimalField)` | `max_digits=5` | field / model | `backend/apps/devices/models_integrations.py:69` |
| `PrinterStatusSnapshot.chamber_temp_c (models.DecimalField)` | `max_digits=5` | field / model | `backend/apps/devices/models_integrations.py:70` |
| `PrinterStatusSnapshot.clear_token (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_integrations.py:74` |
| `LabelPrintCommand.batch_title_snapshot (models.CharField)` | `max_length=200` | field / model | `backend/apps/devices/models_labels.py:27` |
| `LabelPrintCommand.result (models.CharField)` | `max_length=24; default=Result.PENDING` | field / model | `backend/apps/devices/models_labels.py:29` |
| `LabelPrintCommand.result_code (models.CharField)` | `max_length=32` | field / model | `backend/apps/devices/models_labels.py:30` |
| `LabelPrintCommand.result_message (models.CharField)` | `max_length=160` | field / model | `backend/apps/devices/models_labels.py:31` |
| `LabelPrintResult.outcome (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_labels.py:58` |
| `LabelPrintResult.result_code (models.CharField)` | `max_length=32` | field / model | `backend/apps/devices/models_labels.py:59` |
| `LabelPrintResult.response_result (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_labels.py:60` |
| `LabelPrintResult.response_command_status (models.CharField)` | `max_length=24` | field / model | `backend/apps/devices/models_labels.py:61` |
| `PrinterJob.machine_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/devices/models_printers.py:42` |
| `PrinterJob.service_request_name (models.CharField)` | `max_length=120` | field / model | `backend/apps/devices/models_printers.py:44` |
| `PrinterJob.external_job_id (models.CharField)` | `max_length=120` | field / model | `backend/apps/devices/models_printers.py:45` |
| `PrinterJob.state (models.CharField)` | `max_length=24; default=State.AWAITING` | field / model | `backend/apps/devices/models_printers.py:46` |
| `PrinterJob.telemetry_state (models.CharField)` | `max_length=16` | field / model | `backend/apps/devices/models_printers.py:47` |
| `PrinterJob.report_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/devices/models_printers.py:51` |
| `PrinterJob.outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/devices/models_printers.py:52` |
| `PrinterJob.actual_grams (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/devices/models_printers.py:56` |
| `PrinterJob.actual_quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/devices/models_printers.py:57` |
| `PrinterJobConsumption.quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/devices/models_printers.py:87` |
| `ShelfCheck.scope_label (models.CharField)` | `max_length=80` | field / model | `backend/apps/devices/models_shelf_check.py:19` |
| `MAX_NONCE_BYTES` | `64` | fixed / see setting | `backend/apps/devices/protocol.py:24` |
| `b64url_decode` | `min_length=MIN_NONCE_BYTES, max_length=MAX_NONCE_BYTES` | field / model | `backend/apps/devices/protocol.py:83` |
| `AdapterEnrollSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/devices/serializers_adapter.py:16` |
| `AdapterEnrollSerializer.offline_threshold_seconds (serializers.IntegerField)` | `min_value=1, max_value=7 * 24 * 3600; default=300` | field / model | `backend/apps/devices/serializers_adapter.py:17` |
| `BindingCreateSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/devices/serializers_adapter.py:24` |
| `BindingCreateSerializer.target_id (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:25` |
| `BindingCreateSerializer.external_ref (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:26` |
| `BindingCreateSerializer.capabilities (serializers.ListField)` | `max_length=32` | field / model | `backend/apps/devices/serializers_adapter.py:27` |
| `CommandCreateSerializer.command (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/devices/serializers_adapter.py:66` |
| `PoseWriteSerializer.target_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/devices/serializers_adapter.py:89` |
| `PoseWriteSerializer.note (serializers.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:91` |
| `PoseKeySerializer.target_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/devices/serializers_adapter.py:103` |
| `JogSerializer.dx (serializers.FloatField)` | `min_value=-1000, max_value=1000; default=0` | field / model | `backend/apps/devices/serializers_adapter.py:111` |
| `JogSerializer.dy (serializers.FloatField)` | `min_value=-1000, max_value=1000; default=0` | field / model | `backend/apps/devices/serializers_adapter.py:112` |
| `IndicateSerializer.target_id (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:118` |
| `IndicateSerializer.duration_seconds (serializers.IntegerField)` | `min_value=1, max_value=600; default=10` | field / model | `backend/apps/devices/serializers_adapter.py:119` |
| `IndicateSerializer.color (serializers.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:120` |
| `CredentialWriteSerializer.user_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/devices/serializers_adapter.py:124` |
| `CredentialWriteSerializer.secret (serializers.CharField)` | `max_length=64, min_length=4` | field / model | `backend/apps/devices/serializers_adapter.py:126` |
| `CredentialWriteSerializer.label (serializers.CharField)` | `max_length=60; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:127` |
| `WatchStartSerializer.reason (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/devices/serializers_adapter.py:140` |
| `JobCreateSerializer.service_request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/devices/serializers_adapter.py:157` |
| `BindingConfigSerializer.auto_off_idle_minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/devices/serializers_adapter.py:163` |
| `BindingConfigSerializer.max_session_minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/devices/serializers_adapter.py:165` |
| `BindingConfigSerializer.laser_max_power_pct (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/devices/serializers_adapter.py:168` |
| `BindingConfigSerializer.max_on_seconds (serializers.IntegerField)` | `min_value=1, max_value=600` | field / model | `backend/apps/devices/serializers_adapter.py:169` |
| `TypeProfileSerializer.auto_off_idle_minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/devices/serializers_adapter.py:175` |
| `TypeProfileSerializer.max_session_minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/devices/serializers_adapter.py:177` |
| `WebhookWriteSerializer.url (serializers.URLField)` | `max_length=500` | field / model | `backend/apps/devices/serializers_adapter.py:182` |
| `AckSerializer.lease_token (serializers.CharField)` | `min_length=32, max_length=128` | field / model | `backend/apps/devices/serializers_commands.py:6` |
| `MAX_OFFLINE_THRESHOLD_SECONDS` | `7 * 24 * 3600` | fixed / see setting | `backend/apps/devices/serializers_identity.py:14` |
| `serializers.CharField` | `max_length=120` | field / model | `backend/apps/devices/serializers_identity.py:28` |
| `serializers.IntegerField` | `min_value=1, max_value=MAX_OFFLINE_THRESHOLD_SECONDS` | field / model | `backend/apps/devices/serializers_identity.py:32` |
| `ChallengeRequestSerializer.token (serializers.CharField)` | `max_length=256` | field / model | `backend/apps/devices/serializers_identity.py:86` |
| `ChallengeRequestSerializer.public_key (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/devices/serializers_identity.py:87` |
| `CompleteRequestSerializer.challenge (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/devices/serializers_identity.py:96` |
| `CompleteRequestSerializer.signature (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/devices/serializers_identity.py:97` |
| `MAX_SPOOLS` | `16` | fixed / see setting | `backend/apps/devices/serializers_integrations.py:19` |
| `SpoolSerializer.slot (serializers.IntegerField)` | `min_value=0, max_value=63` | field / model | `backend/apps/devices/serializers_integrations.py:49` |
| `SpoolSerializer.material (serializers.CharField)` | `max_length=24; default=''` | field / model | `backend/apps/devices/serializers_integrations.py:50` |
| `SpoolSerializer.colour (serializers.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/devices/serializers_integrations.py:51` |
| `StatusSnapshotSerializer.observed_at (serializers.IntegerField)` | `min_value=1, max_value=4102444800` | field / model | `backend/apps/devices/serializers_integrations.py:57` |
| `StatusSnapshotSerializer.spools (SpoolSerializer)` | `max_length=MAX_SPOOLS` | field / model | `backend/apps/devices/serializers_integrations.py:64` |
| `StatusSnapshotSerializer.clear_token (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/devices/serializers_integrations.py:65` |
| `QueueJobSerializer.planned_grams (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/devices/serializers_integrations.py:97` |
| `JobReportSerializer.external_job_id (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/devices/serializers_integrations.py:115` |
| `JobReportSerializer.actual_minutes (serializers.IntegerField)` | `min_value=0, max_value=2147483647` | field / model | `backend/apps/devices/serializers_integrations.py:117` |
| `JobReportSerializer.failure_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/devices/serializers_integrations.py:119` |
| `JobReportSerializer.percent_complete (serializers.IntegerField)` | `min_value=0, max_value=100` | field / model | `backend/apps/devices/serializers_integrations.py:120` |
| `JobReportSerializer.actual_grams (serializers.DecimalField)` | `max_digits=12, min_value=0` | field / model | `backend/apps/devices/serializers_integrations.py:121` |
| `JobReportSerializer.actual_quantity (serializers.DecimalField)` | `max_digits=12, min_value=0` | field / model | `backend/apps/devices/serializers_integrations.py:122` |
| `TypeIntegrationCreateSerializer.config_schema_version (serializers.IntegerField)` | `min_value=1, max_value=1; default=1` | field / model | `backend/apps/devices/serializers_integrations.py:143` |
| `TypeIntegrationUpdateSerializer.config_schema_version (serializers.IntegerField)` | `min_value=1, max_value=1` | field / model | `backend/apps/devices/serializers_integrations.py:148` |
| `BindingCreateSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/devices/serializers_printers.py:22` |
| `JobCreateSerializer.service_request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/devices/serializers_printers.py:41` |
| `JobCreateSerializer.external_job_id (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/devices/serializers_printers.py:42` |
| `ConsumptionSerializer.machine_consumable_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/devices/serializers_printers.py:46` |
| `ConsumptionSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/devices/serializers_printers.py:47` |
| `ResultSerializer.external_job_id (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/devices/serializers_printers.py:52` |
| `ResultSerializer.actual_minutes (serializers.IntegerField)` | `min_value=0, max_value=2147483647` | field / model | `backend/apps/devices/serializers_printers.py:54` |
| `ResultSerializer.failure_reason (serializers.CharField)` | `max_length=1000; default=''` | field / model | `backend/apps/devices/serializers_printers.py:56` |
| `ResultSerializer.percent_complete (serializers.IntegerField)` | `min_value=0, max_value=100; default=None` | field / model | `backend/apps/devices/serializers_printers.py:57` |
| `ResultSerializer.actual_grams (serializers.DecimalField)` | `max_digits=12, min_value=0; default=None` | field / model | `backend/apps/devices/serializers_printers.py:58` |
| `ResultSerializer.actual_quantity (serializers.DecimalField)` | `max_digits=12, min_value=0; default=None` | field / model | `backend/apps/devices/serializers_printers.py:59` |
| `TelemetrySerializer.external_job_id (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/devices/serializers_printers.py:75` |
| `TelemetrySerializer.progress_percent (serializers.IntegerField)` | `min_value=0, max_value=100` | field / model | `backend/apps/devices/serializers_printers.py:77` |
| `ShelfTargetSerializer.target_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/devices/serializers_shelf.py:12` |
| `ShelfCoverageRequestSerializer.targets (ShelfTargetSerializer)` | `max_length=200` | field / model | `backend/apps/devices/serializers_shelf.py:16` |
| `ShelfShowSerializer.duration_seconds (serializers.IntegerField)` | `min_value=1, max_value=600; default=15` | field / model | `backend/apps/devices/serializers_shelf.py:31` |
| `ShelfShowSerializer.color (serializers.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/devices/serializers_shelf.py:32` |
| `ShelfClearSerializer.target_id (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/devices/serializers_shelf.py:37` |
| `ShelfCheckEntrySerializer.location (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/devices/serializers_shelf.py:51` |
| `ShelfCheckEntrySerializer.note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/devices/serializers_shelf.py:53` |
| `ShelfCheckWriteSerializer.scope_label (serializers.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/devices/serializers_shelf.py:57` |
| `ShelfCheckWriteSerializer.entries (ShelfCheckEntrySerializer)` | `min_length=1, max_length=500` | field / model | `backend/apps/devices/serializers_shelf.py:58` |
| `MAX_BYTES` | `16 * 1024` | fixed / see setting | `backend/apps/devices/services_adapter_config.py:22` |
| `MAX_ITEMS` | `50` | fixed / see setting | `backend/apps/devices/services_adapter_core.py:13` |
| `RATE_LIMIT` | `30` | fixed / see setting | `backend/apps/devices/services_adapter_detect.py:16` |
| `MAX_POINTS` | `2000` | fixed / see setting | `backend/apps/devices/services_adapter_history.py:22` |
| `MAX_SERIES_PER_REPORT` | `40` | fixed / see setting | `backend/apps/devices/services_adapter_history.py:23` |
| `MAX_POSE_BYTES` | `2048` | fixed / see setting | `backend/apps/devices/services_adapter_locate.py:24` |
| `DEFAULT_LASER_MAX_ON_SECONDS` | `60` | fixed / see setting | `backend/apps/devices/services_adapter_locate_safety.py:12` |
| `MAX_SIGNALS` | `60` | fixed / see setting | `backend/apps/devices/services_adapter_media.py:34` |
| `MAX_PRESSES` | `200` | fixed / see setting | `backend/apps/devices/services_adapter_media.py:35` |
| `MAX_FRAME_CHARS` | `700000` | fixed / see setting | `backend/apps/devices/services_adapter_media.py:38` |
| `MAX_ENTRIES` | `5000` | fixed / see setting | `backend/apps/devices/services_adapter_offline.py:31` |
| `MAX_FUTURE_SECONDS` | `300` | fixed / see setting | `backend/apps/devices/services_adapter_offline.py:33` |
| `DEFAULT_MAX_AGE` | `7 * 86400` | fixed / see setting | `backend/apps/devices/services_adapter_offline.py:35` |
| `MAX_FAILED_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/devices/services_adapter_pin.py:30` |
| `MAX_COOLDOWN` | `86400` | fixed / see setting | `backend/apps/devices/services_adapter_pin.py:35` |
| `RECORDING_MAX_BYTES` | `512 * 1024 * 1024` | fixed / see setting | `backend/apps/devices/services_adapter_recording.py:31` |
| `MAX_FUTURE_SECONDS` | `300` | fixed / see setting | `backend/apps/devices/services_adapter_status.py:22` |
| `MAX_ATTEMPTS` | `6` | fixed / see setting | `backend/apps/devices/services_adapter_webhook.py:35` |
| `complete_enrollment.raw_challenge (protocol.b64url_decode)` | `min_length=32, max_length=32` | field / model | `backend/apps/devices/services_enrollment.py:90` |
| `QUEUE_LIMIT` | `50` | fixed / see setting | `backend/apps/devices/services_integration_reports.py:31` |
| `MAX_FUTURE_SECONDS` | `300` | fixed / see setting | `backend/apps/devices/services_integration_status.py:22` |
| `MAX_LOCATIONS` | `500` | fixed / see setting | `backend/apps/devices/services_shelf_check.py:18` |
| `MAX_COVERAGE_TARGETS` | `200` | fixed / see setting | `backend/apps/devices/services_shelf_pointer.py:24` |

</details>

<details>
<summary>encryption (25 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `AccountPiiKey.broker_backend (models.CharField)` | `max_length=16` | field / model | `backend/apps/encryption/account_models.py:18` |
| `AccountPiiKey.broker_key_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/encryption/account_models.py:19` |
| `AccountPiiKey.status (models.CharField)` | `max_length=16; default=Status.ACTIVE` | field / model | `backend/apps/encryption/account_models.py:20` |
| `PiiAccountWriteFence.state (models.CharField)` | `max_length=8; default=State.OPEN` | field / model | `backend/apps/encryption/account_models.py:42` |
| `MakerspaceEncryptionKey.broker_backend (models.CharField)` | `max_length=16` | field / model | `backend/apps/encryption/models.py:35` |
| `MakerspaceEncryptionKey.broker_key_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/encryption/models.py:36` |
| `MakerspaceEncryptionKey.status (models.CharField)` | `max_length=16; default=Status.ACTIVE` | field / model | `backend/apps/encryption/models.py:37` |
| `SearchKeyGeneration.key_fingerprint (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/encryption/models.py:75` |
| `SearchKeyGeneration.status (models.CharField)` | `max_length=16` | field / model | `backend/apps/encryption/models.py:76` |
| `PiiBlindIndex.model_label (models.CharField)` | `max_length=96` | field / model | `backend/apps/encryption/models.py:92` |
| `PiiBlindIndex.field_name (models.CharField)` | `max_length=64` | field / model | `backend/apps/encryption/models.py:94` |
| `PiiBlindIndex.bloom_bits (models.BinaryField)` | `max_length=256` | field / model | `backend/apps/encryption/models.py:96` |
| `PiiBlindIndex.exact_hash (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/encryption/models.py:97` |
| `_FenceModel.state (models.CharField)` | `max_length=8; default=State.OPEN` | field / model | `backend/apps/encryption/models.py:150` |
| `_FenceModel.operation_kind (models.CharField)` | `max_length=20` | field / model | `backend/apps/encryption/models.py:152` |
| `KeyRotationJob.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/encryption/models_rotation.py:27` |
| `KeyRotationJob.status (models.CharField)` | `max_length=16; default=Status.RUNNING` | field / model | `backend/apps/encryption/models_rotation.py:28` |
| `KeyRotationJob.error_code (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/encryption/models_rotation.py:35` |
| `MakerspaceSearchKey.salt (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/encryption/models_rotation.py:59` |
| `MakerspaceSearchKey.status (models.CharField)` | `max_length=16; default=Status.BUILDING` | field / model | `backend/apps/encryption/models_rotation.py:60` |
| `RetiredPublishableKey.key (models.CharField)` | `max_length=40` | field / model | `backend/apps/encryption/models_rotation.py:80` |
| `MAX_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/encryption/rekey_tasks.py:23` |
| `CANDIDATE_LIMIT` | `250` | fixed / see setting | `backend/apps/encryption/search.py:15` |
| `SpaceKeyActionSerializer.confirm_slug (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/encryption/serializers_space_keys.py:24` |
| `SpaceArchiveKeyActionSerializer.confirm_slug (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/encryption/serializers_space_keys.py:29` |

</details>

<details>
<summary>event_reimbursements (123 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `GrantAward.state (models.CharField)` | `max_length=12; default='offered'` | field / model | `backend/apps/event_reimbursements/award_models.py:14` |
| `GrantAward.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/award_models.py:18` |
| `GrantAward.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/award_models.py:25` |
| `GrantAwardRevision.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/award_models.py:39` |
| `ReimbursementBudgetPool.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/budget_models.py:11` |
| `ReimbursementBudgetPool.audience (models.CharField)` | `max_length=12; default='participants'` | field / model | `backend/apps/event_reimbursements/budget_models.py:13` |
| `BudgetReservation.state (models.CharField)` | `max_length=12; default='held'` | field / model | `backend/apps/event_reimbursements/budget_models.py:33` |
| `BudgetEntry.kind (models.CharField)` | `max_length=20` | field / model | `backend/apps/event_reimbursements/budget_models.py:48` |
| `BudgetEntry.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/budget_models.py:56` |
| `ClaimDecision.outcome (models.CharField)` | `max_length=20` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:16` |
| `ClaimDecision.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:20` |
| `ClaimDecision.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:25` |
| `ClaimLineDecision.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:42` |
| `ClaimScreeningReview.recommendation (models.CharField)` | `max_length=20` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:69` |
| `ClaimScreeningReview.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:70` |
| `ClaimAttendanceAttestation.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/claim_decision_models.py:88` |
| `ReceiptReference.asset_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:9` |
| `ReceiptReference.generation (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:10` |
| `ReceiptReference.receipt_total_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:12` |
| `ClaimLineInput.vendor (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:18` |
| `ClaimLineInput.description (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:19` |
| `ClaimLineInput.traveller (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:20` |
| `ClaimLineInput.original_amount_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:22` |
| `ClaimLineInput.source_note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:27` |
| `ClaimLineInput.lodging_nights (StrictInteger)` | `min_value=1, max_value=365` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:32` |
| `ClaimDraftInput.lines (ClaimLineInput)` | `max_length=50` | field / model | `backend/apps/event_reimbursements/claim_inputs.py:36` |
| `ReimbursementClaim.state (models.CharField)` | `max_length=20; default='draft'` | field / model | `backend/apps/event_reimbursements/claim_models.py:15` |
| `ReimbursementClaim.domain_closure_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/claim_models.py:26` |
| `ReimbursementWorkItem.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/event_reimbursements/claim_models.py:36` |
| `ReimbursementWorkItem.state (models.CharField)` | `max_length=12; default='pending'` | field / model | `backend/apps/event_reimbursements/claim_models.py:38` |
| `ClaimRevision.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/claim_revision_models.py:14` |
| `ClaimLine.category (models.CharField)` | `max_length=24` | field / model | `backend/apps/event_reimbursements/claim_revision_models.py:24` |
| `ClaimLine.original_currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/claim_revision_models.py:30` |
| `ClaimLine.fx_rate (models.DecimalField)` | `max_digits=24` | field / model | `backend/apps/event_reimbursements/claim_revision_models.py:31` |
| `ClaimLine.rate_source (models.CharField)` | `max_length=8` | field / model | `backend/apps/event_reimbursements/claim_revision_models.py:33` |
| `ClaimLine.receipt_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/claim_revision_models.py:37` |
| `ReimbursementProgramme.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/config_models.py:23` |
| `ReimbursementProgramme.request_phase (models.CharField)` | `max_length=16; default='both'` | field / model | `backend/apps/event_reimbursements/config_models.py:24` |
| `ReimbursementProgramme.award_mode (models.CharField)` | `max_length=16; default='need_based'` | field / model | `backend/apps/event_reimbursements/config_models.py:28` |
| `ReimbursementProgramme.min_distance_km (models.DecimalField)` | `max_digits=8` | field / model | `backend/apps/event_reimbursements/config_models.py:33` |
| `ReimbursementProgramme.required_submission (models.CharField)` | `max_length=16; default='none'` | field / model | `backend/apps/event_reimbursements/config_models.py:43` |
| `ReimbursementProgramme.initialization_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/config_models.py:51` |
| `GrantRequest.request_phase (models.CharField)` | `max_length=16` | field / model | `backend/apps/event_reimbursements/request_models.py:19` |
| `GrantRequest.kind (models.CharField)` | `max_length=12; default='participant'` | field / model | `backend/apps/event_reimbursements/request_models.py:23` |
| `GrantRequest.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/event_reimbursements/request_models.py:25` |
| `GrantRequest.mode (models.CharField)` | `max_length=8` | field / model | `backend/apps/event_reimbursements/request_models.py:29` |
| `GrantRequest.distance_km (models.DecimalField)` | `max_digits=8` | field / model | `backend/apps/event_reimbursements/request_models.py:33` |
| `GrantRequest.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/event_reimbursements/request_models.py:38` |
| `GrantRequest.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/request_models.py:42` |
| `Command.expected_version (StrictInteger)` | `min_value=0` | field / model | `backend/apps/event_reimbursements/serializers.py:10` |
| `AwardResponseCommand.award_revision (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers.py:18` |
| `ClaimDraftCommand.lines (ClaimLineInput)` | `max_length=50` | field / model | `backend/apps/event_reimbursements/serializers.py:22` |
| `ClaimSubmitCommand.current_revision (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers.py:26` |
| `ClaimAppealCommand.statement (s.CharField)` | `max_length=5000` | field / model | `backend/apps/event_reimbursements/serializers.py:30` |
| `ReceiptUploadCommand.filename (s.CharField)` | `max_length=255` | field / model | `backend/apps/event_reimbursements/serializers.py:62` |
| `ReceiptUploadCommand.bytes (StrictInteger)` | `min_value=1, max_value=10485760` | field / model | `backend/apps/event_reimbursements/serializers.py:63` |
| `ReceiptCompleteCommand.generation (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers.py:68` |
| `PolicySettings.allowed_categories (s.ListField)` | `max_length=5` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:20` |
| `PolicySettings.exclusions (s.ListField)` | `max_length=30` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:21` |
| `PolicySettings.min_distance_km (s.DecimalField)` | `max_digits=8, min_value=0, max_value=40075` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:22` |
| `PolicySettings.eligible_countries (s.ListField)` | `max_length=250` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:23` |
| `PolicySettings.eligible_cohorts (s.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:24` |
| `PolicySettings.eligible_cohorts (s.ListField)` | `max_length=250` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:24` |
| `PolicySettings.min_application_stage (StrictInteger)` | `min_value=1, max_value=20` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:25` |
| `PolicySettings.award_accept_days (StrictInteger)` | `min_value=1, max_value=365` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:26` |
| `PolicySettings.required_submission_stage (StrictInteger)` | `min_value=1, max_value=50` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:32` |
| `PolicySettings.category_limits (StrictInteger)` | `min_value=0, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:35` |
| `ProgrammeCreateOrGetCommand.expected_version (StrictInteger)` | `min_value=0, max_value=0` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:39` |
| `ProgrammeCreateOrGetCommand.initial_total_minor (StrictInteger)` | `min_value=0, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:41` |
| `ProgrammeFinanceCommand.policy_revision (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:47` |
| `ProgrammeFinanceCommand.pool_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:49` |
| `ProgrammeFinanceCommand.expected_pool_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:50` |
| `ProgrammeFinanceCommand.budget_delta_minor (StrictInteger)` | `min_value=-MAX_MINOR, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:51` |
| `AwardDecisionCommand.expected_award_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:56` |
| `AwardDecisionCommand.expected_pool_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:57` |
| `AwardDecisionCommand.amount_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:59` |
| `AwardDecisionCommand.tier (s.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:61` |
| `LineDecision.approved_minor (StrictInteger)` | `min_value=0, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:75` |
| `LineDecision.reason (s.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:77` |
| `ClaimRecommendationCommand.claim_revision_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:82` |
| `ClaimRecommendationCommand.note (s.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:85` |
| `ClaimDecisionCommand.claim_revision_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:90` |
| `ClaimDecisionCommand.expected_pool_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:91` |
| `ClaimDecisionCommand.expected_decision_sequence (StrictInteger)` | `min_value=0` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:92` |
| `ClaimDecisionCommand.expected_obligation_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:93` |
| `ClaimDecisionCommand.line_decisions (LineDecision)` | `max_length=50` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:95` |
| `ClaimDecisionCommand.eligibility_revision (StrictInteger)` | `min_value=0` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:96` |
| `ClaimDecisionCommand.note (s.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:98` |
| `ClaimDeadlineCommand.due_revision (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:120` |
| `ClaimDeadlineCommand.note (s.CharField)` | `max_length=5000` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:123` |
| `AttendanceAttestationCommand.registration_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:127` |
| `AttendanceAttestationCommand.expected_attendance_revision (StrictInteger)` | `min_value=0` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:128` |
| `AttendanceAttestationCommand.venue_evidence_refs (s.ListField)` | `max_length=20` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:130` |
| `AttendanceAttestationCommand.note (s.CharField)` | `max_length=5000` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:132` |
| `Allocation.original_amount_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:138` |
| `ReceiptAllocationOverrideCommand.asset_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:142` |
| `ReceiptAllocationOverrideCommand.expected_receipt_use_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:143` |
| `ReceiptAllocationOverrideCommand.receipt_total_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:144` |
| `ReceiptAllocationOverrideCommand.allocations (Allocation)` | `max_length=100` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:146` |
| `ReceiptAllocationOverrideCommand.note (s.CharField)` | `max_length=5000` | field / model | `backend/apps/event_reimbursements/serializers_finance.py:148` |
| `CrewPoolCommand.expected_version (StrictInteger)` | `min_value=0, max_value=0` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:11` |
| `CrewPoolCommand.initial_total_minor (StrictInteger)` | `min_value=0, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:12` |
| `DirectBookingCommand.expected_pool_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:16` |
| `DirectBookingCommand.amount_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:17` |
| `DirectBookingCommand.vendor (s.CharField)` | `max_length=150` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:19` |
| `DirectBookingCommand.reference (s.CharField)` | `max_length=64` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:22` |
| `DirectBookingCommand.receipt_id (s.IntegerField)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:23` |
| `DirectBookingCancelCommand.expected_pool_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:28` |
| `DirectBookingCancelCommand.reason (s.CharField)` | `max_length=300` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:29` |
| `StaffClaimCommand.expected_version (StrictInteger)` | `min_value=0, max_value=0` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:34` |
| `StaffClaimCommand.beneficiary_registration_id (s.IntegerField)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:35` |
| `StaffClaimCommand.category (s.CharField)` | `max_length=32` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:38` |
| `StaffClaimCommand.amount_minor (StrictInteger)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:39` |
| `StaffClaimCommand.note (s.CharField)` | `max_length=2000` | field / model | `backend/apps/event_reimbursements/serializers_hackmoney.py:41` |
| `ESTIMATE_MAX_MINOR` | `10000000` | fixed / see setting | `backend/apps/event_reimbursements/serializers_request.py:8` |
| `FormDescriptor.schema_version (StrictInteger)` | `min_value=2, max_value=2` | field / model | `backend/apps/event_reimbursements/serializers_request.py:34` |
| `FormDescriptor.form_id (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/event_reimbursements/serializers_request.py:35` |
| `FormDescriptor.revision (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_request.py:36` |
| `Estimate.amount_minor (StrictInteger)` | `min_value=1, max_value=ESTIMATE_MAX_MINOR` | field / model | `backend/apps/event_reimbursements/serializers_request.py:41` |
| `ReimbursementRequestSubmissionSerializer.programme_id (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_request.py:47` |
| `ReimbursementRequestSubmissionSerializer.programme_version (StrictInteger)` | `min_value=1` | field / model | `backend/apps/event_reimbursements/serializers_request.py:48` |
| `ReimbursementRequestSubmissionSerializer.estimates (Estimate)` | `max_length=5` | field / model | `backend/apps/event_reimbursements/serializers_request.py:50` |
| `ReimbursementRequestSubmissionSerializer.need_statement (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/event_reimbursements/serializers_request.py:52` |

</details>

<details>
<summary>events (1212 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `EventAnswerDerivation.question_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/events/answer_derivations/models.py:36` |
| `LOGO_MAX_BYTES` | `200 * 1024` | fixed / see setting | `backend/apps/events/badge_desk.py:20` |
| `MAX_VALUE` | `120` | fixed / see setting | `backend/apps/events/badge_snapshot.py:16` |
| `MAX_BADGES` | `200` | fixed / see setting | `backend/apps/events/badge_templates.py:31` |
| `MAX_PAGES` | `50` | fixed / see setting | `backend/apps/events/badge_templates.py:32` |
| `MAX_TEXT_LENGTH` | `500` | fixed / see setting | `backend/apps/events/badge_templates.py:33` |
| `MAX_CHAIN` | `50` | fixed / see setting | `backend/apps/events/booking_decision_replacement.py:25` |
| `MAX_BYTES` | `10 * 1024 * 1024` | fixed / see setting | `backend/apps/events/certificate_artwork_storage.py:17` |
| `MAX_PIXELS` | `16000000` | fixed / see setting | `backend/apps/events/certificate_artwork_storage.py:18` |
| `MAX_BATCH` | `10000` | fixed / see setting | `backend/apps/events/certificates/batches.py:17` |
| `EventCertificateLibraryTemplate.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/events/certificates/library_models.py:9` |
| `EventCertificateLibraryArtwork.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/certificates/library_models.py:18` |
| `EventCertificateLibraryArtwork.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/library_models.py:19` |
| `EventCertificateLibraryArtwork.version_id (models.CharField)` | `max_length=1024` | field / model | `backend/apps/events/certificates/library_models.py:21` |
| `EventCertificateLibraryCommand.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/library_models.py:50` |
| `LibraryWriteSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/certificates/library_views.py:21` |
| `LibraryWriteSerializer.artwork_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/library_views.py:23` |
| `CopyLibrarySerializer.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/library_views.py:50` |
| `CopyLibrarySerializer.revision_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/library_views.py:51` |
| `CaptureLibrarySerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/certificates/library_views.py:55` |
| `CaptureLibrarySerializer.template_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/library_views.py:56` |
| `CertificateIssueBatch.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/models.py:18` |
| `CertificateIssueBatch.state (models.CharField)` | `max_length=12; default='queued'` | field / model | `backend/apps/events/certificates/models.py:20` |
| `CertificateIssueBatchItem.subject_kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/certificates/models.py:32` |
| `CertificateIssueBatchItem.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/certificates/models.py:34` |
| `CertificateIssueBatchItem.state (models.CharField)` | `max_length=12; default='queued'` | field / model | `backend/apps/events/certificates/models.py:38` |
| `CertificateIssueBatchItem.error_code (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/certificates/models.py:39` |
| `CertificateIssuePlanRequestSerializer.groups (serializers.ListField)` | `min_length=1, max_length=4` | field / model | `backend/apps/events/certificates/output_serializers.py:54` |
| `CertificatePlannedSubjectSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/output_serializers.py:60` |
| `CertificatePlannedSubjectSerializer.award_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/output_serializers.py:62` |
| `CertificatePlannedSubjectSerializer.result_revision_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/output_serializers.py:63` |
| `MAX_PDF` | `20 * 1024 * 1024` | fixed / see setting | `backend/apps/events/certificates/outputs.py:17` |
| `EventBadgeTemplateRevision.stock (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/certificates/print_models.py:10` |
| `BadgePrintJob.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/print_models.py:23` |
| `BadgePrintJob.fields_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/print_models.py:25` |
| `BadgePrintJob.stock (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/certificates/print_models.py:28` |
| `BadgePrintJob.state (models.CharField)` | `max_length=12; default='queued'` | field / model | `backend/apps/events/certificates/print_models.py:31` |
| `BadgePrintJob.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/certificates/print_models.py:35` |
| `BadgePrintJob.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/print_models.py:36` |
| `BadgePrintResource.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/certificates/print_models.py:60` |
| `BadgePrintResource.source_avatar_revision (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/print_models.py:68` |
| `BadgePrintResource.source_key_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/print_models.py:69` |
| `BadgePrintResource.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/certificates/print_models.py:70` |
| `BadgePrintResource.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/certificates/print_models.py:71` |
| `BadgePrintCleanupReceipt.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/certificates/print_models.py:96` |
| `PublicationSerializer.certificate_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/publication_views.py:15` |
| `PublicationSerializer.certificate_ids (serializers.ListField)` | `max_length=200; default=list` | field / model | `backend/apps/events/certificates/publication_views.py:15` |
| `SeedSelectionSerializer.seed_id (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/certificates/seed_views.py:26` |
| `SeedSelectionSerializer.seed_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/seed_views.py:27` |
| `CertificateSubjectSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/serializers.py:12` |
| `CertificateSubjectSerializer.award_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/serializers.py:14` |
| `CertificateSubjectSerializer.result_revision_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/serializers.py:15` |
| `BulkIssueSerializer.subjects (CertificateSubjectSerializer)` | `max_length=10000; default=list` | field / model | `backend/apps/events/certificates/serializers.py:19` |
| `BulkIssueSerializer.confirmed_count (serializers.IntegerField)` | `min_value=1, max_value=10000` | field / model | `backend/apps/events/certificates/serializers.py:22` |
| `PrintCreateSerializer.registration_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/serializers.py:49` |
| `PrintCreateSerializer.registration_ids (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/events/certificates/serializers.py:49` |
| `PrintCreateSerializer.template_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/serializers.py:50` |
| `BadgeDocumentSerializer.version (serializers.IntegerField)` | `min_value=2, max_value=2` | field / model | `backend/apps/events/certificates/serializers.py:70` |
| `BadgeDocumentSerializer.page_width_mm (serializers.FloatField)` | `min_value=30, max_value=420` | field / model | `backend/apps/events/certificates/serializers.py:71` |
| `BadgeDocumentSerializer.page_height_mm (serializers.FloatField)` | `min_value=30, max_value=420` | field / model | `backend/apps/events/certificates/serializers.py:72` |
| `BadgeDocumentSerializer.layers (CertificateLayerSerializer)` | `min_length=1, max_length=20` | field / model | `backend/apps/events/certificates/serializers.py:73` |
| `CertificateLayerSerializer.order (serializers.IntegerField)` | `min_value=0, max_value=19` | field / model | `backend/apps/events/certificates/serializers_layout.py:19` |
| `CertificateLayerSerializer.x_mm (serializers.FloatField)` | `min_value=0` | field / model | `backend/apps/events/certificates/serializers_layout.py:22` |
| `CertificateLayerSerializer.y_mm (serializers.FloatField)` | `min_value=0` | field / model | `backend/apps/events/certificates/serializers_layout.py:23` |
| `CertificateLayerSerializer.width_mm (serializers.FloatField)` | `min_value=0.1` | field / model | `backend/apps/events/certificates/serializers_layout.py:24` |
| `CertificateLayerSerializer.height_mm (serializers.FloatField)` | `min_value=0.1` | field / model | `backend/apps/events/certificates/serializers_layout.py:25` |
| `CertificateLayerSerializer.rotation (serializers.FloatField)` | `min_value=-360, max_value=360; default=0` | field / model | `backend/apps/events/certificates/serializers_layout.py:26` |
| `CertificateLayerSerializer.text (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/certificates/serializers_layout.py:27` |
| `CertificateLayerSerializer.font_size_pt (serializers.FloatField)` | `min_value=6, max_value=96` | field / model | `backend/apps/events/certificates/serializers_layout.py:30` |
| `CertificateLayerSerializer.tracking_pt (serializers.FloatField)` | `min_value=-1, max_value=8` | field / model | `backend/apps/events/certificates/serializers_layout.py:35` |
| `CertificateLayerSerializer.line_height (serializers.FloatField)` | `min_value=1, max_value=3` | field / model | `backend/apps/events/certificates/serializers_layout.py:36` |
| `CertificateLayerSerializer.opacity (serializers.FloatField)` | `min_value=0, max_value=1` | field / model | `backend/apps/events/certificates/serializers_layout.py:37` |
| `CertificateLayerSerializer.signature_slot (serializers.IntegerField)` | `min_value=1, max_value=3` | field / model | `backend/apps/events/certificates/serializers_layout.py:44` |
| `EventCertificateSignatory.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/events/certificates/signatory_models.py:17` |
| `EventCertificateSignatory.title (models.CharField)` | `max_length=120` | field / model | `backend/apps/events/certificates/signatory_models.py:18` |
| `CertificateSignatoryWriteSerializer.slot (serializers.IntegerField)` | `min_value=1, max_value=3` | field / model | `backend/apps/events/certificates/signatory_serializers.py:23` |
| `CertificateSignatoryWriteSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/certificates/signatory_serializers.py:24` |
| `CertificateSignatoryWriteSerializer.title (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/events/certificates/signatory_serializers.py:25` |
| `CertificateSignatoryWriteSerializer.member_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/signatory_serializers.py:26` |
| `CertificateSignatoryWriteSerializer.signature_artwork_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/certificates/signatory_serializers.py:28` |
| `CertificateApproveSerializer.template_revision_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/certificates/signatory_serializers.py:80` |
| `EventContributorAdmission.capacity_policy (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/contributions/models_admission.py:9` |
| `EventCrewMember.origin (models.CharField)` | `max_length=8; default=Origin.SIGNUP` | field / model | `backend/apps/events/contributions/models_crew.py:42` |
| `EventCrewMember.crew_role (models.CharField)` | `max_length=60; default=''` | field / model | `backend/apps/events/contributions/models_crew.py:44` |
| `EventCrewMember.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/events/contributions/models_crew.py:46` |
| `EventCrewMember.state (models.CharField)` | `max_length=10; default=State.APPLIED` | field / model | `backend/apps/events/contributions/models_crew.py:51` |
| `EventContributorNotice.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/contributions/models_notices.py:9` |
| `EventRequirementOverride.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/contributions/models_policy.py:23` |
| `EventContributorRequirementCompletion.requirements_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/contributions/models_policy.py:31` |
| `EventContributorRequirementCompletion.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/contributions/models_policy.py:34` |
| `EventRolePosting.role (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/contributions/models_roles.py:14` |
| `EventRolePosting.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/contributions/models_roles.py:15` |
| `EventRolePosting.visibility (models.CharField)` | `max_length=24; default='public'` | field / model | `backend/apps/events/contributions/models_roles.py:19` |
| `EventRolePosting.state (models.CharField)` | `max_length=8; default='draft'` | field / model | `backend/apps/events/contributions/models_roles.py:29` |
| `EventRoleAssignment.origin (models.CharField)` | `max_length=8; default='self'` | field / model | `backend/apps/events/contributions/models_roles.py:40` |
| `EventRoleAssignment.role (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/contributions/models_roles.py:42` |
| `EventRoleAssignment.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/contributions/models_roles.py:44` |
| `EventRoleAssignment.host_waiver_version_accepted (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/contributions/models_roles.py:52` |
| `EventGrantEntitlement.source_kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/contributions/models_roles.py:85` |
| `EventSponsor.label (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/contributions/models_roles.py:121` |
| `EventSponsor.logo_reference (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/contributions/models_roles.py:122` |
| `EventSponsor.page_reference (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/contributions/models_roles.py:123` |
| `EventShift.kind (models.CharField)` | `max_length=12; default='volunteer'` | field / model | `backend/apps/events/contributions/models_shifts.py:10` |
| `EventShift.zone (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/contributions/models_shifts.py:15` |
| `EventShift.task (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/contributions/models_shifts.py:16` |
| `EventShift.state (models.CharField)` | `max_length=8; default='open'` | field / model | `backend/apps/events/contributions/models_shifts.py:24` |
| `EventShiftSignup.state (models.CharField)` | `max_length=12; default='applied'` | field / model | `backend/apps/events/contributions/models_shifts.py:40` |
| `EventShiftAttendance.state (models.CharField)` | `max_length=12; default='scheduled'` | field / model | `backend/apps/events/contributions/models_shifts.py:53` |
| `EventShiftAttendance.source (models.CharField)` | `max_length=16; default='self'` | field / model | `backend/apps/events/contributions/models_shifts.py:58` |
| `EventContributionHours.state (models.CharField)` | `max_length=8; default='pending'` | field / model | `backend/apps/events/contributions/models_shifts.py:70` |
| `EventContributionHoursEntry.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/contributions/models_shifts.py:79` |
| `EventShiftAttendanceCorrection.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/events/contributions/models_shifts.py:90` |
| `RequirementOverrideSerializer.shift_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/requirements_workflow.py:14` |
| `RequirementOverrideSerializer.reference_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/requirements_workflow.py:16` |
| `RequirementOverrideSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/contributions/requirements_workflow.py:17` |
| `RequirementCompletionSerializer.reference_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/requirements_workflow.py:42` |
| `CommandSerializer.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/contributions/serializers.py:15` |
| `RoleInputSerializer.saved_detail_versions (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/contributions/serializers.py:33` |
| `RoleInputSerializer.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers.py:36` |
| `RoleInputSerializer.availability (WindowSerializer)` | `max_length=50` | field / model | `backend/apps/events/contributions/serializers.py:37` |
| `RoleInputSerializer.skills (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/contributions/serializers.py:38` |
| `RoleInputSerializer.skills (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/contributions/serializers.py:38` |
| `RoleInputSerializer.host_waiver_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers.py:39` |
| `RoleInputSerializer.host_waiver_version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/contributions/serializers.py:40` |
| `DateReviewSerializer.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers.py:50` |
| `ShiftApplySerializer.role_assignment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers.py:55` |
| `HoursAdjustSerializer.minutes (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/events/contributions/serializers.py:59` |
| `HoursAdjustSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/contributions/serializers.py:60` |
| `PostingWriteSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/contributions/serializers_management.py:8` |
| `PostingWriteSerializer.description (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/events/contributions/serializers_management.py:9` |
| `PostingWriteSerializer.briefing (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/events/contributions/serializers_management.py:10` |
| `PostingWriteSerializer.skills (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/contributions/serializers_management.py:11` |
| `PostingWriteSerializer.skills (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/contributions/serializers_management.py:11` |
| `PostingWriteSerializer.permission_preset (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/contributions/serializers_management.py:16` |
| `PostingWriteSerializer.permission_preset (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/contributions/serializers_management.py:16` |
| `ShiftWriteSerializer.posting_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers_management.py:23` |
| `ShiftWriteSerializer.mentor_assignment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers_management.py:25` |
| `ShiftWriteSerializer.task (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/contributions/serializers_management.py:29` |
| `ShiftWriteSerializer.zone (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/contributions/serializers_management.py:30` |
| `ShiftWriteSerializer.capacity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/contributions/serializers_management.py:31` |
| `ShiftWriteSerializer.grace_minutes (serializers.IntegerField)` | `min_value=0, max_value=60` | field / model | `backend/apps/events/contributions/serializers_management.py:32` |
| `ShiftWriteSerializer.permission_preset (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/contributions/serializers_management.py:36` |
| `ShiftWriteSerializer.permission_preset (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/contributions/serializers_management.py:36` |
| `ShiftWriteSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/contributions/serializers_management.py:39` |
| `AdminRoleSerializer.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers_management.py:43` |
| `AdminRoleSerializer.posting_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers_management.py:44` |
| `AdminRoleSerializer.sponsor_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers_management.py:45` |
| `AdminRoleSerializer.delegated_permissions (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/contributions/serializers_management.py:48` |
| `AdminRoleSerializer.delegated_permissions (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/contributions/serializers_management.py:48` |
| `AdminRoleSerializer.track_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/serializers_management.py:49` |
| `AdminRoleSerializer.track_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/contributions/serializers_management.py:49` |
| `AdminAttendanceSerializer.break_minutes (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/events/contributions/serializers_management.py:54` |
| `AdminAttendanceSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/contributions/serializers_management.py:55` |
| `RoleReasonSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/contributions/views_completion.py:13` |
| `AdmissionSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/contributions/views_completion.py:17` |
| `EventRegistrationCredential.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/credentials/models.py:12` |
| `EventRegistrationCredential.revocation_reason (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/credentials/models.py:20` |
| `EventCredentialCommand.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/credentials/models.py:44` |
| `CredentialCommandSerializer.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/credentials/views.py:17` |
| `CLOSED_LIMIT` | `100` | fixed / see setting | `backend/apps/events/equipment_desk.py:27` |
| `MAX_WARNINGS` | `50` | fixed / see setting | `backend/apps/events/equipment_desk_warnings.py:16` |
| `MAX_PRODUCTS` | `50` | fixed / see setting | `backend/apps/events/equipment_window.py:33` |
| `MAX_PARTICIPANTS` | `50` | fixed / see setting | `backend/apps/events/equipment_window.py:34` |
| `CommandInput.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/hackathons/admission_inputs.py:28` |
| `CocInput.revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/admission_inputs.py:32` |
| `ApplicationInput.saved_detail_versions (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/hackathons/admission_inputs.py:45` |
| `ApplicationInput.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/admission_inputs.py:46` |
| `ApplicationInput.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/admission_inputs.py:49` |
| `ApplicationInput.invite_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/hackathons/admission_inputs.py:50` |
| `ApplicationInput.promo_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/hackathons/admission_inputs.py:51` |
| `ApplicationInput.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/events/hackathons/admission_inputs.py:52` |
| `ApplicationInput.phone (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/admission_inputs.py:53` |
| `ApplicationInput.host_waiver_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/admission_inputs.py:54` |
| `ApplicationInput.host_waiver_version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/admission_inputs.py:55` |
| `ApplicationInput.stage_forms (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/hackathons/admission_inputs.py:57` |
| `effective_contacts.field (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/events/hackathons/admission_inputs.py:102` |
| `HackathonConfig.review_mode (models.CharField)` | `max_length=8; default='rolling'` | field / model | `backend/apps/events/hackathons/admission_models.py:13` |
| `HackathonConfig.team_mode (models.CharField)` | `max_length=24; default='individual_then_team'` | field / model | `backend/apps/events/hackathons/admission_models.py:17` |
| `HackathonConfig.team_eligibility (models.CharField)` | `max_length=12; default='confirmed'` | field / model | `backend/apps/events/hackathons/admission_models.py:22` |
| `HackathonConfig.late_policy (models.CharField)` | `max_length=16; default='reject'` | field / model | `backend/apps/events/hackathons/admission_models.py:33` |
| `HackathonConfig.upload_policy (models.CharField)` | `max_length=64; default='hackathon-maker-v1'` | field / model | `backend/apps/events/hackathons/admission_models.py:35` |
| `HackathonApplicationCohort.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/hackathons/admission_models.py:72` |
| `HackathonApplicationCohort.sealed_roster_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/admission_models.py:74` |
| `HackathonApplication.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/hackathons/admission_models.py:83` |
| `MAX_STAGES` | `20` | fixed / see setting | `backend/apps/events/hackathons/admission_stage_models.py:16` |
| `MAX_CRITERIA` | `10` | fixed / see setting | `backend/apps/events/hackathons/admission_stage_models.py:17` |
| `AdmissionStage.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:32` |
| `AdmissionStage.state (models.CharField)` | `max_length=8; default=State.DRAFT` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:33` |
| `AdmissionStage.guidance (models.TextField)` | `max_length=4000; default=''` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:37` |
| `AdmissionStage.assignment_strategy (models.CharField)` | `max_length=8; default=Strategy.BALANCED` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:40` |
| `AdmissionStage.assignment_seed (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:41` |
| `AdmissionStage.assignment_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:42` |
| `AdmissionStageAssignment.state (models.CharField)` | `max_length=10; default=State.ASSIGNED` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:88` |
| `AdmissionStageAssignment.plan_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:89` |
| `AdmissionStageEntry.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:122` |
| `AdmissionStageEntry.reason_code (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/events/hackathons/admission_stage_models.py:125` |
| `CommentSerializer.body (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/hackathons/api_schema.py:87` |
| `QuoteSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/hackathons/api_schema_details.py:13` |
| `QuoteSerializer.discount_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/hackathons/api_schema_details.py:14` |
| `TicketChoiceSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/hackathons/api_schema_details.py:36` |
| `ApplicationReviewAssignment.state (models.CharField)` | `max_length=12; default='assigned'` | field / model | `backend/apps/events/hackathons/review_models.py:18` |
| `ApplicationReviewAssignment.recusal_code (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/hackathons/review_models.py:23` |
| `ApplicationReviewConflict.reason_code (models.CharField)` | `max_length=40; default='declared'` | field / model | `backend/apps/events/hackathons/review_models.py:50` |
| `ApplicationDecisionBatch.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/hackathons/review_models.py:60` |
| `ApplicationDecision.outcome (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/hackathons/review_models.py:70` |
| `ApplicationDecision.reason_code (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/hackathons/review_models.py:74` |
| `ApplicationDecision.review_override_code (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/hackathons/review_models.py:78` |
| `DateReviewInput.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:16` |
| `DecisionSubjectInput.application_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:31` |
| `DecisionSubjectInput.cohort_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:32` |
| `DecisionSubjectInput.expected_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:33` |
| `DecisionSubjectInput.stage_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:38` |
| `StageInput.decisions (DecisionSubjectInput)` | `min_length=1, max_length=200` | field / model | `backend/apps/events/hackathons/serializers_commands.py:49` |
| `BatchInput.batch_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:53` |
| `ReviewAssignInput.subjects (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/events/hackathons/serializers_commands.py:57` |
| `ReviewAssignInput.reviewer_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:58` |
| `ReviewAssignInput.reviewer_ids (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/events/hackathons/serializers_commands.py:58` |
| `ReviewInput.scores (serializers.IntegerField)` | `min_value=1, max_value=5` | field / model | `backend/apps/events/hackathons/serializers_commands.py:62` |
| `ReviewInput.notes (serializers.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/events/hackathons/serializers_commands.py:63` |
| `TeamInput.name (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/hackathons/serializers_commands.py:73` |
| `TeamInput.finder_intro (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/hackathons/serializers_commands.py:75` |
| `TeamInput.skills (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/hackathons/serializers_commands.py:76` |
| `TeamInput.skills (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/hackathons/serializers_commands.py:76` |
| `InviteInput.email (serializers.EmailField)` | `max_length=254; default=''` | field / model | `backend/apps/events/hackathons/serializers_commands.py:80` |
| `AcceptInput.request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:86` |
| `AcceptInput.token (serializers.CharField)` | `min_length=32, max_length=128` | field / model | `backend/apps/events/hackathons/serializers_commands.py:87` |
| `DeclineRequestInput.request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:96` |
| `CommentInput.body (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/hackathons/serializers_commands.py:100` |
| `FinderInput.intro (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/hackathons/serializers_commands.py:105` |
| `FinderInput.skills (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/hackathons/serializers_commands.py:106` |
| `FinderInput.skills (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/hackathons/serializers_commands.py:106` |
| `HandoverInput.new_leader_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:115` |
| `RemoveMemberInput.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:119` |
| `TeamRenameInput.name (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/hackathons/serializers_commands.py:123` |
| `TeamMoveInput.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:127` |
| `TeamMoveInput.to_team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_commands.py:128` |
| `ConfigInput.team_min (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/hackathons/serializers_config.py:15` |
| `ConfigInput.team_max (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/hackathons/serializers_config.py:16` |
| `ConfigInput.review_count (serializers.IntegerField)` | `min_value=1, max_value=20` | field / model | `backend/apps/events/hackathons/serializers_config.py:19` |
| `ConfigInput.rsvp_days (serializers.IntegerField)` | `min_value=1, max_value=30` | field / model | `backend/apps/events/hackathons/serializers_config.py:23` |
| `ConfigInput.offer_capacity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/hackathons/serializers_config.py:24` |
| `ConfigInput.submission_grace_minutes (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/events/hackathons/serializers_config.py:27` |
| `ConfigInput.upload_policy (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/serializers_config.py:30` |
| `ConfigInput.upload_policy_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_config.py:31` |
| `ConfigInput.storage_budget_bytes (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_config.py:32` |
| `ConfigInput.coc_body (serializers.CharField)` | `max_length=50000` | field / model | `backend/apps/events/hackathons/serializers_config.py:33` |
| `CriterionSerializer.label (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/hackathons/serializers_stages.py:10` |
| `CriterionSerializer.guidance (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/hackathons/serializers_stages.py:11` |
| `StageFields.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/hackathons/serializers_stages.py:15` |
| `StageFields.reviews_per_application (serializers.IntegerField)` | `min_value=1, max_value=20` | field / model | `backend/apps/events/hackathons/serializers_stages.py:16` |
| `StageFields.criteria (CriterionSerializer)` | `max_length=10` | field / model | `backend/apps/events/hackathons/serializers_stages.py:18` |
| `StageFields.guidance (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/events/hackathons/serializers_stages.py:19` |
| `StageCreateInput.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/hackathons/serializers_stages.py:26` |
| `PanelInput.reviewer_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/hackathons/serializers_stages.py:34` |
| `PanelInput.reviewer_ids (serializers.ListField)` | `max_length=200` | field / model | `backend/apps/events/hackathons/serializers_stages.py:34` |
| `StageReviewInput.scores (serializers.IntegerField)` | `min_value=1, max_value=5` | field / model | `backend/apps/events/hackathons/serializers_stages.py:49` |
| `StageReviewInput.notes (serializers.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/events/hackathons/serializers_stages.py:50` |
| `HackathonTeam.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/hackathons/team_models.py:12` |
| `HackathonTeam.normalized_name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/hackathons/team_models.py:13` |
| `HackathonTeam.state (models.CharField)` | `max_length=12; default='forming'` | field / model | `backend/apps/events/hackathons/team_models.py:15` |
| `HackathonTeam.zone (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/team_models.py:17` |
| `HackathonTeam.table (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/hackathons/team_models.py:18` |
| `HackathonTeam.finder_intro (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/hackathons/team_models.py:20` |
| `HackathonTeam.roster_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/team_models.py:23` |
| `HackathonTeamMember.state (models.CharField)` | `max_length=12; default='requested'` | field / model | `backend/apps/events/hackathons/team_models.py:41` |
| `HackathonTeamInvite.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/team_models.py:55` |
| `HackathonTeamInvite.email_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/team_models.py:56` |
| `HackathonFinderProfile.intro (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/hackathons/team_models.py:70` |
| `HackathonTeamException.rule (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/hackathons/team_models.py:91` |
| `HackathonTeamException.roster_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/hackathons/team_models.py:93` |
| `HackathonTeamException.reason_code (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/hackathons/team_models.py:94` |
| `CardScanRequestSerializer.payload (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/id_cards_openapi.py:17` |
| `ParticipantSponsorResumeConsent.asset_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_consent.py:14` |
| `ParticipantSponsorResumeConsent.purpose (models.CharField)` | `max_length=16; default='recruiting'` | field / model | `backend/apps/events/judging/models_consent.py:15` |
| `ParticipantSponsorResumeConsent.state (models.CharField)` | `max_length=8; default='revoked'` | field / model | `backend/apps/events/judging/models_consent.py:16` |
| `SponsorResumeConsentHistory.state (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/judging/models_consent.py:36` |
| `SponsorResumeConsentHistory.asset_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_consent.py:37` |
| `SponsorResumeConsentHistory.reason_code (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/judging/models_consent.py:40` |
| `HackathonTrack.name (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/models_definitions.py:11` |
| `HackathonTrack.description (models.TextField)` | `max_length=4000` | field / model | `backend/apps/events/judging/models_definitions.py:12` |
| `HackathonPrize.name (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/models_definitions.py:27` |
| `HackathonPrize.description (models.TextField)` | `max_length=4000` | field / model | `backend/apps/events/judging/models_definitions.py:28` |
| `HackathonPrize.winner_selection_mode (models.CharField)` | `max_length=20; default='manager'` | field / model | `backend/apps/events/judging/models_definitions.py:39` |
| `HackathonPrize.amount_per_winner (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_definitions.py:42` |
| `HackathonPrize.kind (models.CharField)` | `max_length=8; default='cash'` | field / model | `backend/apps/events/judging/models_definitions.py:45` |
| `HackathonPrize.value_text (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/models_definitions.py:46` |
| `HackathonPrize.estimated_value (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_definitions.py:47` |
| `HackathonPrize.funding (models.CharField)` | `max_length=16; default='space'` | field / model | `backend/apps/events/judging/models_definitions.py:48` |
| `JudgingRound.key (models.SlugField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_definitions.py:62` |
| `JudgingRound.mode (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/judging/models_definitions.py:63` |
| `JudgingRound.state (models.CharField)` | `max_length=16; default='draft'` | field / model | `backend/apps/events/judging/models_definitions.py:65` |
| `JudgingRound.normalization (models.CharField)` | `max_length=8; default='none'` | field / model | `backend/apps/events/judging/models_definitions.py:69` |
| `JudgingRound.algorithm_version (models.CharField)` | `max_length=40; default='spaceworks-judging-v1'` | field / model | `backend/apps/events/judging/models_definitions.py:75` |
| `JudgingRound.visibility (models.CharField)` | `max_length=12; default='assigned'` | field / model | `backend/apps/events/judging/models_definitions.py:79` |
| `JudgingCriterion.key (models.SlugField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_definitions.py:115` |
| `JudgingCriterion.label (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/models_definitions.py:116` |
| `JudgingCriterion.weight (models.DecimalField)` | `max_digits=10` | field / model | `backend/apps/events/judging/models_definitions.py:117` |
| `FinalistAdvance.selection (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/judging/models_finalists.py:15` |
| `FinalistAdvance.fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_finalists.py:17` |
| `HackathonProgrammeOptions.deposit_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_options.py:31` |
| `HackathonProgrammeOptions.entry_fee (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_options.py:34` |
| `HackathonProgrammeOptions.team_fee (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_options.py:35` |
| `JudgePairwiseComparison.outcome (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/judging/models_pairwise.py:17` |
| `JudgePairwiseComparison.notes (models.TextField)` | `max_length=2000` | field / model | `backend/apps/events/judging/models_pairwise.py:18` |
| `HackathonPrizePayout.kind (models.CharField)` | `max_length=8; default='payout'` | field / model | `backend/apps/events/judging/models_payouts.py:24` |
| `HackathonPrizePayout.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_payouts.py:26` |
| `HackathonPrizePayout.tds_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/judging/models_payouts.py:28` |
| `HackathonPrizePayout.net_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_payouts.py:29` |
| `HackathonPrizePayout.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/events/judging/models_payouts.py:30` |
| `HackathonPrizePayout.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/judging/models_payouts.py:31` |
| `HackathonPrizePayout.reference (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_payouts.py:32` |
| `PeoplesChoiceConfig.audience (models.CharField)` | `max_length=10; default='members'` | field / model | `backend/apps/events/judging/models_peoples_choice.py:23` |
| `PeoplesChoiceResult.prize_name (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/models_peoples_choice.py:63` |
| `HackathonPrizeShare.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_prize_money.py:34` |
| `HackathonPrizeShare.state (models.CharField)` | `max_length=12; default='proposed'` | field / model | `backend/apps/events/judging/models_prize_money.py:35` |
| `HackathonPrizeClaim.country (models.CharField)` | `max_length=2` | field / model | `backend/apps/events/judging/models_prize_money.py:51` |
| `HackathonPrizeClaim.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/judging/models_prize_money.py:52` |
| `HackathonPrizeClaim.template_key (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/judging/models_prize_money.py:53` |
| `HackathonPrizeOutcome.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/judging/models_prize_money.py:71` |
| `HackathonPrizeOutcome.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/judging/models_prize_money.py:72` |
| `HackathonPrizeOutcome.reference (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_prize_money.py:73` |
| `HackathonPrizeOutcome.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/judging/models_prize_money.py:74` |
| `HackathonPrizeOutcome.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/events/judging/models_prize_money.py:75` |
| `HackathonPrizeOutcome.note (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/models_prize_money.py:77` |
| `EventResultRevision.algorithm_version (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/judging/models_results.py:13` |
| `EventResultRevision.content_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_results.py:15` |
| `EventResultRevision.source_content_sha256 (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/judging/models_results.py:16` |
| `EventAward.prize_name (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/models_results.py:39` |
| `JudgingNotice.kind (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/judging/models_results.py:78` |
| `JudgingReason.body (models.TextField)` | `max_length=2000` | field / model | `backend/apps/events/judging/models_scoring.py:13` |
| `JudgeAssignment.room (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_scoring.py:22` |
| `JudgeAssignment.batch (models.CharField)` | `max_length=64; default='main'` | field / model | `backend/apps/events/judging/models_scoring.py:23` |
| `JudgeAssignment.state (models.CharField)` | `max_length=16; default='assigned'` | field / model | `backend/apps/events/judging/models_scoring.py:24` |
| `JudgeScore.notes (models.TextField)` | `max_length=4000` | field / model | `backend/apps/events/judging/models_scoring.py:48` |
| `JudgeScore.team_feedback (models.TextField)` | `max_length=4000` | field / model | `backend/apps/events/judging/models_scoring.py:50` |
| `JudgeRankingBallot.batch (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/models_scoring.py:58` |
| `CommandInput.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/judging/serializers.py:20` |
| `IdList.serializers.IntegerField` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:30` |
| `IdList.super().__init__` | `max_length=2000` | field / model | `backend/apps/events/judging/serializers.py:30` |
| `TrackInput.name (serializers.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/serializers.py:42` |
| `TrackInput.description (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/events/judging/serializers.py:43` |
| `TrackInput.website_section_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:44` |
| `TrackInput.criteria (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/judging/serializers.py:45` |
| `TrackInput.capacity (serializers.IntegerField)` | `min_value=0, max_value=100000` | field / model | `backend/apps/events/judging/serializers.py:47` |
| `TrackInput.eligibility_rules (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/serializers.py:48` |
| `TrackInput.eligibility_rules (serializers.ListField)` | `max_length=30` | field / model | `backend/apps/events/judging/serializers.py:48` |
| `TrackInput.order (serializers.IntegerField)` | `min_value=0, max_value=10000` | field / model | `backend/apps/events/judging/serializers.py:50` |
| `PrizeInput.amount_per_winner (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers.py:73` |
| `PrizeInput.track_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:75` |
| `PrizeInput.sponsor_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:76` |
| `PrizeInput.award_count (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/judging/serializers.py:77` |
| `PrizeInput.value_text (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/serializers.py:81` |
| `PrizeInput.estimated_value (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers.py:83` |
| `CriterionInput.label (serializers.CharField)` | `max_length=160` | field / model | `backend/apps/events/judging/serializers.py:92` |
| `CriterionInput.weight (serializers.DecimalField)` | `max_digits=10, min_value=Decimal('0.0001')` | field / model | `backend/apps/events/judging/serializers.py:93` |
| `CriterionInput.anchors (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/judging/serializers.py:94` |
| `RoundInput.key (serializers.SlugField)` | `max_length=64` | field / model | `backend/apps/events/judging/serializers.py:103` |
| `RoundInput.min_reviews (serializers.IntegerField)` | `min_value=3, max_value=20` | field / model | `backend/apps/events/judging/serializers.py:105` |
| `RoundInput.minutes_per_view (serializers.IntegerField)` | `min_value=1, max_value=120` | field / model | `backend/apps/events/judging/serializers.py:107` |
| `RoundInput.judging_minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/events/judging/serializers.py:108` |
| `RoundInput.criteria (CriterionInput)` | `max_length=30` | field / model | `backend/apps/events/judging/serializers.py:111` |
| `RoundInput.guidance (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/judging/serializers.py:112` |
| `RoundInput.exploration (serializers.DecimalField)` | `max_digits=3, min_value=Decimal('0'), max_value=Decimal('0.30')` | field / model | `backend/apps/events/judging/serializers.py:114` |
| `RoundInput.submission_stage_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:122` |
| `AssignInput.max_load (serializers.IntegerField)` | `min_value=1, max_value=2000; default=100` | field / model | `backend/apps/events/judging/serializers.py:134` |
| `AssignInput.seed (serializers.CharField)` | `max_length=64; default='0'` | field / model | `backend/apps/events/judging/serializers.py:135` |
| `AssignInput.plan_fingerprint (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/serializers.py:140` |
| `FinalizeRoundInput.coverage_exception_reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/judging/serializers.py:145` |
| `ScoreInput.scores (serializers.IntegerField)` | `min_value=1, max_value=5` | field / model | `backend/apps/events/judging/serializers.py:149` |
| `ScoreInput.notes (serializers.CharField)` | `max_length=4000; default=''` | field / model | `backend/apps/events/judging/serializers.py:150` |
| `ScoreInput.team_feedback (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/events/judging/serializers.py:151` |
| `ReasonInput.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/judging/serializers.py:168` |
| `AwardInput.prize_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:172` |
| `AwardInput.snapshot_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:173` |
| `AwardInput.rank (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/judging/serializers.py:174` |
| `AwardInput.tie_reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/judging/serializers.py:176` |
| `ResultsInput.awards (AwardInput)` | `max_length=1000; default=list` | field / model | `backend/apps/events/judging/serializers.py:181` |
| `ResultsInput.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/judging/serializers.py:183` |
| `PublishResultInput.result_revision_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:187` |
| `SponsorGrantInput.sponsor_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:191` |
| `SponsorGrantInput.asset_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:192` |
| `SponsorGrantInput.purpose (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/events/judging/serializers.py:193` |
| `SponsorGrantInput.disclosure_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:195` |
| `SponsorProposalInput.snapshot_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers.py:211` |
| `FinalistSelection.source_round_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_l21b.py:13` |
| `FinalistSelection.target_round_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_l21b.py:14` |
| `FinalistSelection.top_n (serializers.IntegerField)` | `min_value=1, max_value=500` | field / model | `backend/apps/events/judging/serializers_l21b.py:16` |
| `FinalistPublishInput.advance_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_l21b.py:32` |
| `PayoutInput.award_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_l21b.py:114` |
| `PayoutInput.recipient_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_l21b.py:115` |
| `PayoutInput.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers_l21b.py:117` |
| `PayoutInput.reference (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/serializers_l21b.py:119` |
| `PayoutInput.receipt_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_l21b.py:121` |
| `PayoutInput.tds_amount (MoneyField)` | `max_digits=13, min_value=Decimal('0')` | field / model | `backend/apps/events/judging/serializers_l21b.py:122` |
| `PayoutReverseInput.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/serializers_l21b.py:128` |
| `PayoutRead.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:142` |
| `PayoutRead.tds_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:143` |
| `PayoutRead.net_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:144` |
| `PrizeTaxProposal.rate (serializers.DecimalField)` | `max_digits=5` | field / model | `backend/apps/events/judging/serializers_l21b.py:156` |
| `PrizeTaxProposal.threshold (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:157` |
| `PrizeShareRow.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:163` |
| `PrizePayableAwardRead.amount_per_winner (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:173` |
| `OptionsInput.entry_fee (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers_l21b.py:199` |
| `OptionsInput.team_fee (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers_l21b.py:201` |
| `OptionsInput.entry_fee_stage (serializers.IntegerField)` | `min_value=1, max_value=10` | field / model | `backend/apps/events/judging/serializers_l21b.py:205` |
| `OptionsInput.prize_claim_days (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/events/judging/serializers_l21b.py:208` |
| `OptionsInput.deposit_amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers_l21b.py:210` |
| `OptionsRead.entry_fee (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:226` |
| `OptionsRead.team_fee (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:227` |
| `OptionsRead.deposit_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_l21b.py:230` |
| `CompareInput.notes (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/judging/serializers_pairwise.py:10` |
| `SkipInput.notes (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/judging/serializers_pairwise.py:14` |
| `PeoplesChoiceConfigInput.prize_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_peoples_choice.py:24` |
| `PeoplesChoiceVoidInput.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/serializers_peoples_choice.py:35` |
| `PeoplesChoicePayoutInput.standing_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_peoples_choice.py:40` |
| `PeoplesChoicePayableWinnerRead.amount_per_winner (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/judging/serializers_peoples_choice.py:141` |
| `ShareRow.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_prize.py:18` |
| `ShareRow.amount (MoneyField)` | `min_value=Decimal('0.001')` | field / model | `backend/apps/events/judging/serializers_prize.py:19` |
| `SplitInput.shares (ShareRow)` | `min_length=1, max_length=50` | field / model | `backend/apps/events/judging/serializers_prize.py:23` |
| `PrizeClaimInput.details (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/judging/serializers_prize.py:33` |
| `PrizeClaimInput.pan (serializers.CharField)` | `max_length=12` | field / model | `backend/apps/events/judging/serializers_prize.py:34` |
| `FulfilInput.reference (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/serializers_prize.py:52` |
| `FulfilInput.note (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/serializers_prize.py:54` |
| `ForfeitInput.share_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_prize.py:59` |
| `ForfeitInput.note (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/serializers_prize.py:61` |
| `RecoveryResolveInput.reference (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/judging/serializers_prize.py:67` |
| `RecoveryResolveInput.receipt_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/serializers_prize.py:68` |
| `RecoveryResolveInput.note (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/judging/serializers_prize.py:69` |
| `ShortlistSignalRead.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/judging/views_signals.py:11` |
| `ShortlistSignalRead.fresh_nominations (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/judging/views_signals.py:12` |
| `ShortlistSignalRead.repeat_nominations (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/judging/views_signals.py:13` |
| `ShortlistSignalRead.final_rating_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/judging/views_signals.py:14` |
| `ShortlistSignalRead.final_rating_mean (serializers.DecimalField)` | `max_digits=8` | field / model | `backend/apps/events/judging/views_signals.py:15` |
| `ShortlistSignalRead.top_two_picks (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/judging/views_signals.py:16` |
| `MAX_LOANS` | `500` | fixed / see setting | `backend/apps/events/linked_change_notices.py:31` |
| `MAX_LINKS` | `50` | fixed / see setting | `backend/apps/events/machine_booking_links.py:35` |
| `HISTORY_LIMIT` | `50` | fixed / see setting | `backend/apps/events/member_history.py:63` |
| `MAX_BYTES` | `1000000` | fixed / see setting | `backend/apps/events/mentoring/import_parser.py:8` |
| `MentorAssignmentRun.mode (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/mentoring/models_operations.py:9` |
| `MentorTeamAssignment.mode (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/mentoring/models_queue.py:24` |
| `MentorTeamAssignment.state (models.CharField)` | `max_length=8; default='active'` | field / model | `backend/apps/events/mentoring/models_queue.py:26` |
| `EventHelpType.key (models.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/models_queue.py:41` |
| `EventHelpType.label (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/mentoring/models_queue.py:42` |
| `EventHelpType.organizer_contact_action (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/mentoring/models_queue.py:46` |
| `EventHelpRequest.origin (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/mentoring/models_queue.py:66` |
| `EventHelpRequest.state (models.CharField)` | `max_length=10; default='open'` | field / model | `backend/apps/events/mentoring/models_queue.py:69` |
| `EventHelpRequest.dedup_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/mentoring/models_queue.py:82` |
| `EventHelpAction.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/mentoring/models_queue.py:106` |
| `EventHelpComment.origin (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/mentoring/models_queue.py:115` |
| `OfficeHoursBooking.state (models.CharField)` | `max_length=10; default='booked'` | field / model | `backend/apps/events/mentoring/models_queue.py:126` |
| `MentorRound.key (models.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/models_rounds.py:10` |
| `MentorRound.label (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/mentoring/models_rounds.py:11` |
| `MentorRound.state (models.CharField)` | `max_length=8; default='draft'` | field / model | `backend/apps/events/mentoring/models_rounds.py:14` |
| `MentorConflict.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/events/mentoring/models_rounds.py:69` |
| `MentorImportPreview.mapping_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/mentoring/models_rounds.py:91` |
| `MentorNotificationIntent.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/mentoring/models_rounds.py:101` |
| `ZoneSerializer.table (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers.py:7` |
| `ZoneSerializer.zone (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers.py:8` |
| `HelpCreateSerializer.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:13` |
| `HelpCreateSerializer.type_key (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers.py:14` |
| `HelpCreateSerializer.summary (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers.py:15` |
| `CommentInputSerializer.body (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers.py:21` |
| `ResolveInputSerializer.resolution_note (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers.py:25` |
| `ReopenInputSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers.py:29` |
| `AssignHelpSerializer.mentor_assignment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:33` |
| `BookingInputSerializer.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:68` |
| `ManualAssignmentSerializer.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:78` |
| `ManualAssignmentSerializer.mentor_assignment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:79` |
| `AssignmentInputSerializer.team_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:83` |
| `AssignmentInputSerializer.team_ids (serializers.ListField)` | `min_length=1, max_length=500` | field / model | `backend/apps/events/mentoring/serializers.py:83` |
| `AssignmentInputSerializer.skill_weights (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/mentoring/serializers.py:85` |
| `AssignmentInputSerializer.manual (ManualAssignmentSerializer)` | `max_length=500; default=list` | field / model | `backend/apps/events/mentoring/serializers.py:86` |
| `RoundWriteSerializer.index (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/mentoring/serializers.py:125` |
| `RoundWriteSerializer.key (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers.py:126` |
| `RoundWriteSerializer.label (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/mentoring/serializers.py:127` |
| `RoundWriteSerializer.note_keys (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/events/mentoring/serializers.py:131` |
| `RoundWriteSerializer.note_keys (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/mentoring/serializers.py:131` |
| `RoundWriteSerializer.rating_keys (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/events/mentoring/serializers.py:132` |
| `RoundWriteSerializer.rating_keys (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/mentoring/serializers.py:132` |
| `RoundWriteSerializer.help_trigger_rules (serializers.ListField)` | `max_length=10` | field / model | `backend/apps/events/mentoring/serializers.py:136` |
| `ClaimInputSerializer.override_reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers.py:157` |
| `LeaseInputSerializer.generation (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers.py:162` |
| `RoundSubmitSerializer.override_reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers.py:168` |
| `MentorProfileWriteSerializer.skills (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:6` |
| `MentorProfileWriteSerializer.skills (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:6` |
| `MentorProfileWriteSerializer.affiliation (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:7` |
| `MentorProfileWriteSerializer.availability (WindowSerializer)` | `max_length=50` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:8` |
| `MentorProfileWriteSerializer.max_active_teams (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:9` |
| `HelpTypeWriteSerializer.key (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:21` |
| `HelpTypeWriteSerializer.label (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:22` |
| `HelpTypeWriteSerializer.skill_tags (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:23` |
| `HelpTypeWriteSerializer.skill_tags (serializers.SlugField)` | `max_length=40` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:23` |
| `HelpTypeWriteSerializer.priority (serializers.IntegerField)` | `min_value=0, max_value=100` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:24` |
| `HelpTypeWriteSerializer.open_limit (serializers.IntegerField)` | `min_value=1, max_value=10` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:25` |
| `HelpTypeWriteSerializer.claim_minutes (serializers.IntegerField)` | `min_value=1, max_value=60` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:26` |
| `HelpTypeWriteSerializer.expiry_minutes (serializers.IntegerField)` | `min_value=15, max_value=10080` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:27` |
| `HelpTypeWriteSerializer.organizer_contact_action (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:28` |
| `ConflictWriteSerializer.mentor_assignment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:43` |
| `ConflictWriteSerializer.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:44` |
| `ConflictWriteSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:47` |
| `MuteSerializer.minutes (serializers.IntegerField)` | `min_value=0, max_value=120` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:59` |
| `NominationSerializer.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:67` |
| `RenewHelpSerializer.claim_generation (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers_configuration.py:72` |
| `ImportRowSerializer.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers_operations.py:54` |
| `ImportRowSerializer.member_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/serializers_operations.py:55` |
| `ImportRowSerializer.member_ids (serializers.ListField)` | `min_length=1, max_length=50` | field / model | `backend/apps/events/mentoring/serializers_operations.py:55` |
| `ImportRowSerializer.alias (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/mentoring/serializers_operations.py:56` |
| `ImportPreviewSerializer.rows (ImportRowSerializer)` | `min_length=1, max_length=500` | field / model | `backend/apps/events/mentoring/serializers_operations.py:60` |
| `MentorAlertRoutesWriteSerializer.destination_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/mentoring/views_chat_alerts.py:28` |
| `MentorAlertRoutesWriteSerializer.destination_ids (serializers.ListField)` | `max_length=10` | field / model | `backend/apps/events/mentoring/views_chat_alerts.py:28` |
| `EventAddon.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/models_addons.py:25` |
| `EventAddon.description (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/models_addons.py:26` |
| `EventAddon.kind (models.CharField)` | `max_length=8; default=Kind.OTHER` | field / model | `backend/apps/events/models_addons.py:27` |
| `EventAddon.amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_addons.py:28` |
| `EventAddon.amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_addons.py:28` |
| `EventAddonVariant.label (models.CharField)` | `max_length=60` | field / model | `backend/apps/events/models_addons.py:42` |
| `EventCheckInEvent.source (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/models_attendance.py:41` |
| `EventBadgePrint.method (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/models_badge_prints.py:29` |
| `EventBadgePrint.stock (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/events/models_badge_prints.py:30` |
| `EventBadgePrint.role (models.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/events/models_badge_prints.py:31` |
| `EventBookingDecision.billing_owner (models.CharField)` | `max_length=12; default='booking'` | field / model | `backend/apps/events/models_booking_decision.py:19` |
| `EventBroadcast.status (models.CharField)` | `max_length=10; default=Status.DRAFT` | field / model | `backend/apps/events/models_broadcasts.py:20` |
| `EventBroadcast.attendance (models.CharField)` | `max_length=12; default='any'` | field / model | `backend/apps/events/models_broadcasts.py:23` |
| `EventBroadcast.design (models.CharField)` | `max_length=12; default='classic'` | field / model | `backend/apps/events/models_broadcasts.py:27` |
| `EventBroadcastPreview.content_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_broadcasts.py:55` |
| `EventBroadcastPreview.revision (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_broadcasts.py:56` |
| `MemberCalendarFeed.token_digest (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/events/models_calendar.py:16` |
| `MemberCalendarFeed.token_hint (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/models_calendar.py:17` |
| `PersonalCalendarFeed.kind (models.CharField)` | `max_length=10` | field / model | `backend/apps/events/models_calendar_personal.py:22` |
| `PersonalCalendarFeed.token_digest (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/events/models_calendar_personal.py:23` |
| `PersonalCalendarFeed.token_hint (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/models_calendar_personal.py:24` |
| `EventCategory.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/models_categories.py:6` |
| `EventCategory.slug (models.SlugField)` | `max_length=100` | field / model | `backend/apps/events/models_categories.py:7` |
| `EventCertificateArtwork.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/models_certificate_templates.py:13` |
| `EventCertificateArtwork.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_certificate_templates.py:15` |
| `EventCertificateArtwork.version_id (models.CharField)` | `max_length=1024` | field / model | `backend/apps/events/models_certificate_templates.py:16` |
| `EventCertificateTemplateRevision.certificate_kind (models.CharField)` | `max_length=24; default=''` | field / model | `backend/apps/events/models_certificate_templates.py:37` |
| `EventAttendanceCertificate.kind (models.CharField)` | `max_length=24; default=Kind.ATTENDANCE` | field / model | `backend/apps/events/models_certificates.py:30` |
| `EventAttendanceCertificate.event_title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_certificates.py:70` |
| `EventAttendanceCertificate.event_timezone_name (models.CharField)` | `max_length=64; default='UTC'` | field / model | `backend/apps/events/models_certificates.py:73` |
| `EventAttendanceCertificate.issuer_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_certificates.py:74` |
| `EventAttendanceCertificate.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/models_certificates.py:75` |
| `EventAttendanceCertificate.content_type (models.CharField)` | `max_length=64; default='application/pdf'` | field / model | `backend/apps/events/models_certificates.py:76` |
| `EventAttendanceCertificate.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_certificates.py:78` |
| `EventAttendanceCertificate.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/events/models_certificates.py:79` |
| `EventAttendanceCertificate.revocation_reason (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/models_certificates.py:97` |
| `EventCheckInList.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/models_checkin_lists.py:25` |
| `EventCheckInList.kind (models.CharField)` | `max_length=10; default=Kind.OTHER` | field / model | `backend/apps/events/models_checkin_lists.py:26` |
| `EventCheckoutHold.release_reason (models.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/events/models_checkout_holds.py:27` |
| `EventCollaborator.status (models.CharField)` | `max_length=8; default=Status.INVITED` | field / model | `backend/apps/events/models_collaborators.py:27` |
| `EventCommandReceipt.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_commands.py:10` |
| `Event.accent_preset (models.CharField)` | `max_length=24; default=''` | field / model | `backend/apps/events/models_event.py:22` |
| `Event.registration_audience (models.CharField)` | `max_length=32; default=RegistrationAudience.MEMBERS` | field / model | `backend/apps/events/models_event.py:36` |
| `Event.timezone_name (models.CharField)` | `max_length=64; default=settings.TIME_ZONE` | field / model | `backend/apps/events/models_event.py:67` |
| `Event.series_occurrence_key (models.CharField)` | `max_length=48` | field / model | `backend/apps/events/models_event.py:81` |
| `Event.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_event.py:84` |
| `Event.location (models.CharField)` | `max_length=255` | field / model | `backend/apps/events/models_event.py:88` |
| `Event.venue_address (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/events/models_event.py:89` |
| `Event.venue_map_url (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/events/models_event.py:90` |
| `Event.location_kind (models.CharField)` | `max_length=8; default=LocationKind.OTHER` | field / model | `backend/apps/events/models_event.py:91` |
| `Event.payment_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_event.py:103` |
| `Event.payment_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_event.py:107` |
| `Event.cancellation_cutoff_hours (MaxValueValidator)` | `max_value=8760` | field / model | `backend/apps/events/models_event.py:110` |
| `Event.listing (models.CharField)` | `max_length=10; default=Listing.LISTED` | field / model | `backend/apps/events/models_event.py:121` |
| `Event.page_state (models.CharField)` | `max_length=8; default=PageState.LIVE` | field / model | `backend/apps/events/models_event.py:122` |
| `Event.delivery_mode (models.CharField)` | `max_length=10; default=DeliveryMode.IN_PERSON` | field / model | `backend/apps/events/models_event.py:123` |
| `Event.image_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/models_event.py:129` |
| `Event.equipment_return_hours (MaxValueValidator)` | `max_value=720` | field / model | `backend/apps/events/models_event.py:133` |
| `Event.status (models.CharField)` | `max_length=16; default=Status.DRAFT` | field / model | `backend/apps/events/models_event.py:134` |
| `EventFeedbackSurvey.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_feedback.py:28` |
| `EventIdCard.role (models.CharField)` | `max_length=10; default=Role.ATTENDEE` | field / model | `backend/apps/events/models_id_cards.py:34` |
| `EventIdCard.photo_object_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/models_id_cards.py:38` |
| `EventIdCard.photo_content_type (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/models_id_cards.py:39` |
| `EventIdCard.photo_consent_version (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/events/models_id_cards.py:42` |
| `EventIdCard.status (models.CharField)` | `max_length=8; default=Status.ACTIVE` | field / model | `backend/apps/events/models_id_cards.py:43` |
| `EventIdCard.email_format (models.CharField)` | `max_length=3; default='pdf'` | field / model | `backend/apps/events/models_id_cards.py:55` |
| `EventInvite.code_digest (models.CharField)` | `max_length=64; default=secrets.token_hex` | field / model | `backend/apps/events/models_invites.py:19` |
| `EventInvite.email_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/models_invites.py:20` |
| `MAX_REVISION` | `9007199254740991` | fixed / see setting | `backend/apps/events/models_loan_context.py:5` |
| `MachineEventLink.source (models.CharField)` | `max_length=10` | field / model | `backend/apps/events/models_machine_use.py:39` |
| `MachineEventCostApproval.decision (models.CharField)` | `max_length=10` | field / model | `backend/apps/events/models_machine_use.py:58` |
| `MachineEventCostApproval.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/models_machine_use.py:60` |
| `MachineEventCostApproval.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/events/models_machine_use.py:61` |
| `MachineEventCostApproval.note (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/models_machine_use.py:64` |
| `EventSalesSettings.booking_fee_fixed (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_orders.py:30` |
| `EventSalesSettings.booking_fee_bps (MaxValueValidator)` | `max_value=10000` | field / model | `backend/apps/events/models_orders.py:31` |
| `EventSalesSettings.max_tickets_per_order (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/events/models_orders.py:32` |
| `EventSalesSettings.partial_percent (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/events/models_orders.py:42` |
| `EventSalesSettings.cancellation_fee (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_orders.py:43` |
| `EventSalesSettings.policy_text (models.TextField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/models_orders.py:45` |
| `EventOrder.kind (models.CharField)` | `max_length=12; default=Kind.TICKETS` | field / model | `backend/apps/events/models_orders.py:79` |
| `EventOrder.status (models.CharField)` | `max_length=12; default=Status.PENDING` | field / model | `backend/apps/events/models_orders.py:80` |
| `EventOrder.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/events/models_orders.py:81` |
| `EventOrder.digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/models_orders.py:88` |
| `EventOrderLine.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/events/models_orders.py:129` |
| `EventOrderLine.label (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_orders.py:138` |
| `EventOrderLine.quantity (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/events/models_orders.py:139` |
| `EventOrderSeat.status (models.CharField)` | `max_length=10; default=Status.UNCLAIMED` | field / model | `backend/apps/events/models_orders.py:166` |
| `EventOrderSeat.claim_token_digest (models.CharField)` | `max_length=64; default=secrets.token_hex` | field / model | `backend/apps/events/models_orders.py:170` |
| `EventOrderDue.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/models_orders.py:200` |
| `EventAttendanceRound.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/events/models_participation.py:45` |
| `EventAttendanceRound.state (models.CharField)` | `max_length=8; default=State.QUEUED` | field / model | `backend/apps/events/models_participation.py:46` |
| `EventAttendanceReply.answer (models.CharField)` | `max_length=4; default=''` | field / model | `backend/apps/events/models_participation.py:74` |
| `EventAttendanceReply.effect (models.CharField)` | `max_length=16; default=Effect.NONE` | field / model | `backend/apps/events/models_participation.py:77` |
| `EventPassType.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/models_passes.py:18` |
| `EventPassType.amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_passes.py:19` |
| `EventPassType.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/models_passes.py:19` |
| `EventPassType.occurrence_refund_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_passes.py:23` |
| `EventPassType.occurrence_refund_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_passes.py:24` |
| `EventPromoCode.code_digest (models.CharField)` | `max_length=64; default=secrets.token_hex` | field / model | `backend/apps/events/models_promos.py:14` |
| `EventPromoCode.percent_off (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/events/models_promos.py:15` |
| `EventPromoCode.amount_off (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_promos.py:16` |
| `EventPromoCode.amount_off (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_promos.py:16` |
| `EventPromoCode.kind (models.CharField)` | `max_length=8; default='discount'` | field / model | `backend/apps/events/models_promos.py:25` |
| `EventPromoCode.applies_per (models.CharField)` | `max_length=8; default='ticket'` | field / model | `backend/apps/events/models_promos.py:27` |
| `SubmissionIntegrityCheck.state (models.CharField)` | `max_length=16; default=State.PENDING` | field / model | `backend/apps/events/models_r2_l2.py:31` |
| `SubmissionIntegrityCheck.after_deadline_state (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/events/models_r2_l2.py:36` |
| `SubmissionStorageCleanupReceipt.key_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_r2_l2.py:49` |
| `EventRegistration.credential_mode (models.CharField)` | `max_length=8; default='legacy'` | field / model | `backend/apps/events/models_registration.py:22` |
| `EventRegistration.registration_audience (models.CharField)` | `max_length=32; default=Event.RegistrationAudience.MEMBERS` | field / model | `backend/apps/events/models_registration.py:41` |
| `EventRegistration.quoted_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/models_registration.py:46` |
| `EventRegistration.discount_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_registration.py:47` |
| `EventRegistration.host_waiver_version_accepted (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_registration.py:96` |
| `EventRegistration.email_exact_hash (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/events/models_registration.py:99` |
| `EventRegistration.status (models.CharField)` | `max_length=20; default=Status.REGISTERED` | field / model | `backend/apps/events/models_registration.py:105` |
| `EventRegistration.status_before_cancel (models.CharField)` | `max_length=20; default=''` | field / model | `backend/apps/events/models_registration.py:113` |
| `EventSeries.registration_audience (models.CharField)` | `max_length=32; default='members'` | field / model | `backend/apps/events/models_series.py:31` |
| `EventSeries.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_series.py:32` |
| `EventSeries.location (models.CharField)` | `max_length=255` | field / model | `backend/apps/events/models_series.py:34` |
| `EventSeries.venue_address (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/events/models_series.py:35` |
| `EventSeries.venue_map_url (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/events/models_series.py:36` |
| `EventSeries.location_kind (models.CharField)` | `max_length=8; default='other'` | field / model | `backend/apps/events/models_series.py:37` |
| `EventSeries.payment_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_series.py:45` |
| `EventSeries.payment_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_series.py:46` |
| `EventSeries.cancellation_cutoff_hours (MaxValueValidator)` | `max_value=8760` | field / model | `backend/apps/events/models_series.py:49` |
| `EventSeries.listing (models.CharField)` | `max_length=10; default='listed'` | field / model | `backend/apps/events/models_series.py:53` |
| `EventSeries.image_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/models_series.py:55` |
| `EventSeries.recurrence_timezone (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/models_series.py:57` |
| `EventSeries.recurrence_rule (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/models_series.py:60` |
| `EventSeries.status (models.CharField)` | `max_length=16; default=Status.DRAFT` | field / model | `backend/apps/events/models_series.py:63` |
| `EventSeries.last_generation_error_code (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/models_series.py:65` |
| `EventSeriesCollaborator.status (models.CharField)` | `max_length=8; default=Status.INVITED` | field / model | `backend/apps/events/models_series.py:121` |
| `EventShortLink.code (models.CharField)` | `max_length=7` | field / model | `backend/apps/events/models_short_links.py:20` |
| `_EventStaffScope.role_label (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/events/models_staff_grants.py:31` |
| `EventTicketType.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/models_tickets.py:19` |
| `EventTicketType.amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_tickets.py:20` |
| `EventTicketType.amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_tickets.py:20` |
| `EventTicketType.audience (models.CharField)` | `max_length=8; default=Audience.PUBLIC` | field / model | `backend/apps/events/models_tickets.py:21` |
| `EventTicketType.purpose (models.CharField)` | `max_length=16; default='participant'` | field / model | `backend/apps/events/models_tickets.py:23` |
| `EventTicketType.contributor_capacity_policy (models.CharField)` | `max_length=32; default='event_capacity'` | field / model | `backend/apps/events/models_tickets.py:25` |
| `EventTicketType.tier_group (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/models_tickets.py:33` |
| `EventTicketType.pricing_mode (models.CharField)` | `max_length=8; default='fixed'` | field / model | `backend/apps/events/models_tickets.py:35` |
| `EventTicketType.min_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_tickets.py:38` |
| `EventTicketType.min_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/events/models_tickets.py:38` |
| `EventTicketType.seats_per_ticket (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/events/models_tickets.py:40` |
| `EventTicketType.min_quantity (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/events/models_tickets.py:43` |
| `EventTicketTransfer.token_digest (models.CharField)` | `max_length=64; default=secrets.token_hex` | field / model | `backend/apps/events/models_transfers.py:31` |
| `EventTicketTransfer.status (models.CharField)` | `max_length=10; default=Status.PENDING` | field / model | `backend/apps/events/models_transfers.py:32` |
| `EventVenueFee.mode (models.CharField)` | `max_length=8; default=Mode.INHERIT` | field / model | `backend/apps/events/models_venue_fees.py:42` |
| `EventVenueFee.basis (models.CharField)` | `max_length=8; default=Basis.FLAT` | field / model | `backend/apps/events/models_venue_fees.py:43` |
| `EventVenueFee.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/events/models_venue_fees.py:44` |
| `EventVenueFee.amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/events/models_venue_fees.py:45` |
| `EventVenueFee.status (models.CharField)` | `max_length=12; default=Status.CONFIGURED` | field / model | `backend/apps/events/models_venue_fees.py:46` |
| `EventPage.tagline (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/models_website.py:18` |
| `EventPage.accent_color (models.CharField)` | `max_length=7` | field / model | `backend/apps/events/models_website.py:19` |
| `EventPageAsset.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/models_website.py:40` |
| `EventPageAsset.alt_text (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_website.py:42` |
| `EventPageSection.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/models_website.py:68` |
| `EventPageSection.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/events/models_website.py:69` |
| `EventPageSection.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_website.py:70` |
| `EventPageSection.body (models.CharField)` | `max_length=10000` | field / model | `backend/apps/events/models_website.py:71` |
| `EventPageSection.url (models.URLField)` | `max_length=500` | field / model | `backend/apps/events/models_website.py:72` |
| `EventPageSection.visibility (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/models_website.py:74` |
| `EventPageSection.headline (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_website.py:76` |
| `EventPageSection.organization (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_website.py:77` |
| `EventPageSection.website_url (models.URLField)` | `max_length=500` | field / model | `backend/apps/events/models_website.py:78` |
| `EventPageSection.linkedin_url (models.URLField)` | `max_length=500` | field / model | `backend/apps/events/models_website.py:79` |
| `EventPageSection.x_url (models.URLField)` | `max_length=500` | field / model | `backend/apps/events/models_website.py:80` |
| `EventPageSection.sponsor_tier (models.CharField)` | `max_length=24; default='community_partner'` | field / model | `backend/apps/events/models_website.py:81` |
| `EventPageSection.icon (models.CharField)` | `max_length=40` | field / model | `backend/apps/events/models_website.py:83` |
| `EventSession.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/events/models_website.py:95` |
| `EventSession.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/models_website.py:96` |
| `EventSession.body (models.CharField)` | `max_length=10000` | field / model | `backend/apps/events/models_website.py:97` |
| `EventSession.visibility (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/models_website.py:103` |
| `EventSessionAlias.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/events/models_website_revisions.py:16` |
| `EventPageRevisionAsset.slot (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/models_website_revisions.py:36` |
| `MAX_JOIN_URL` | `2000` | fixed / see setting | `backend/apps/events/online_delivery.py:28` |
| `EventMemberPresentation.source_revision (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/profile_photos/models.py:17` |
| `EventMemberCard.scope (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/profile_photos/models.py:50` |
| `EventPresentationCommand.request_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/profile_photos/models.py:59` |
| `PresentationWriteSerializer.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/profile_photos/serializers.py:8` |
| `PresentationWriteSerializer.profile_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/profile_photos/serializers.py:9` |
| `PresentationWriteSerializer.membership_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/profile_photos/serializers.py:10` |
| `PresentationWriteSerializer.source_revision (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/profile_photos/serializers.py:11` |
| `PresentationWriteSerializer.public_card_scopes (serializers.ListField)` | `max_length=3; default=list` | field / model | `backend/apps/events/profile_photos/serializers.py:14` |
| `MAX_BYTES` | `10 * 1024 * 1024` | fixed / see setting | `backend/apps/events/profile_photos/snapshot.py:16` |
| `MAX_PIXELS` | `16000000` | fixed / see setting | `backend/apps/events/profile_photos/snapshot.py:17` |
| `FunnelStageSerializer.stage_position (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/analytics_serializers.py:10` |
| `FunnelStageSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:11` |
| `FunnelStageSerializer.denominator (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:12` |
| `FunnelStageSerializer.percent (serializers.FloatField)` | `min_value=0, max_value=100` | field / model | `backend/apps/events/programme/analytics_serializers.py:13` |
| `SignupDaySerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:18` |
| `SignupDaySerializer.previous_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:19` |
| `CapacitySerializer.limit (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:23` |
| `CapacitySerializer.going (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:24` |
| `CapacitySerializer.remaining (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:25` |
| `ArrivalWindowSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:51` |
| `CheckinMethodSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:56` |
| `AnswerCountSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:61` |
| `AnswerChartSerializer.total (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:69` |
| `SignupDaySerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:74` |
| `WrittenAnswerCountSerializer.answered (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:81` |
| `WaitlistConversionSerializer.ever_waitlisted (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:85` |
| `WaitlistConversionSerializer.promoted (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:86` |
| `WaitlistConversionSerializer.still_waiting (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:87` |
| `SeriesTurnoutSerializer.registered (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:95` |
| `SeriesTurnoutSerializer.attended (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:96` |
| `VisitDaySerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/analytics_serializers.py:101` |
| `MAX_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/events/programme/cover.py:11` |
| `MAX_PIXELS` | `16000000` | fixed / see setting | `backend/apps/events/programme/cover.py:12` |
| `EventFormRevision.form_key (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/programme/form_models.py:9` |
| `EventFormRevision.selector_kind (models.CharField)` | `max_length=8; default='none'` | field / model | `backend/apps/events/programme/form_models.py:11` |
| `MAX_BUCKETS` | `96` | fixed / see setting | `backend/apps/events/programme/live.py:15` |
| `CommandSerializer.expected_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/serializers.py:28` |
| `PublishingInput.website_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/serializers.py:42` |
| `ReadinessItemSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/serializers.py:75` |
| `ArrivalSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/serializers.py:85` |
| `LiveSerializer.seconds_until_doors (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/serializers.py:92` |
| `LiveSerializer.going (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/serializers.py:94` |
| `LiveSerializer.checked_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/serializers.py:95` |
| `FormSelector.posting_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/serializers.py:101` |
| `FormSelector.round_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/serializers.py:102` |
| `FormSelector.track_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/serializers.py:103` |
| `GuestFilter.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/series_guests.py:27` |
| `GuestFilter.page (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/programme/series_guests.py:30` |
| `TopEventSerializer.attended (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/programme/views_insights.py:33` |
| `EventWriteSerializer.category_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_admin.py:19` |
| `EventWriteSerializer.tags (serializers.CharField)` | `max_length=50` | field / model | `backend/apps/events/serializers_admin.py:20` |
| `EventWriteSerializer.tags (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/serializers_admin.py:20` |
| `EventWriteSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_admin.py:21` |
| `EventWriteSerializer.timezone_name (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_admin.py:25` |
| `EventWriteSerializer.location (serializers.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/events/serializers_admin.py:26` |
| `EventWriteSerializer.venue_address (serializers.CharField)` | `max_length=ADDRESS_MAX` | field / model | `backend/apps/events/serializers_admin.py:37` |
| `EventWriteSerializer.venue_map_url (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/serializers_admin.py:38` |
| `EventWriteSerializer.capacity (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/events/serializers_admin.py:41` |
| `EventWriteSerializer.payment_amount (MoneyField)` | `max_digits=13, min_value=0; default=0` | field / model | `backend/apps/events/serializers_admin.py:42` |
| `EventWriteSerializer.cancellation_cutoff_hours (serializers.IntegerField)` | `min_value=0, max_value=8760; default=None` | field / model | `backend/apps/events/serializers_admin.py:54` |
| `EventWriteSerializer.registration_cutoff_lead_minutes (serializers.IntegerField)` | `min_value=0; default=None` | field / model | `backend/apps/events/serializers_admin.py:61` |
| `EventCreateSerializer.organization_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/serializers_admin.py:122` |
| `EventCreateSerializer.organization_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_admin.py:123` |
| `EventCreateSerializer.audience_organization_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/serializers_admin.py:126` |
| `EventCreateSerializer.audience_organization_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_admin.py:127` |
| `EventCreateSerializer.collaborator_slugs (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/serializers_admin.py:130` |
| `EventCreateSerializer.host_makerspace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_admin.py:134` |
| `BadgeReceiptSerializer.registration_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_badge_prints.py:10` |
| `BadgeReceiptSerializer.stock (serializers.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/events/serializers_badge_prints.py:14` |
| `BadgeTemplateSerializer.fields (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/events/serializers_badges.py:23` |
| `BadgeTemplateSerializer.grid_mm (serializers.FloatField)` | `min_value=0.5, max_value=10` | field / model | `backend/apps/events/serializers_badges.py:29` |
| `BadgePdfRequestSerializer.registration_ids (serializers.ListField)` | `max_length=MAX_BADGES` | field / model | `backend/apps/events/serializers_badges.py:34` |
| `BadgePdfRequestSerializer.registration_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_badges.py:35` |
| `BroadcastCtaSerializer.label (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/events/serializers_broadcasts.py:18` |
| `BroadcastCtaSerializer.url (serializers.URLField)` | `max_length=2048` | field / model | `backend/apps/events/serializers_broadcasts.py:19` |
| `EventBroadcastInputSerializer.subject (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_broadcasts.py:27` |
| `EventBroadcastInputSerializer.body (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/events/serializers_broadcasts.py:28` |
| `EventBroadcastInputSerializer.statuses (serializers.ListField)` | `min_length=1, max_length=6; default=['registered', 'attended']` | field / model | `backend/apps/events/serializers_broadcasts.py:29` |
| `EventBroadcastInputSerializer.ctas (BroadcastCtaSerializer)` | `max_length=3; default=list` | field / model | `backend/apps/events/serializers_broadcasts.py:34` |
| `BulkInviteInputSerializer.emails (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/events/serializers_broadcasts.py:64` |
| `BroadcastCommandSerializer.expected_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_broadcasts.py:75` |
| `BroadcastDraftContentSerializer.subject (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_broadcasts.py:79` |
| `BroadcastDraftContentSerializer.body (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/events/serializers_broadcasts.py:80` |
| `BroadcastDraftContentSerializer.statuses (serializers.ListField)` | `min_length=1, max_length=6` | field / model | `backend/apps/events/serializers_broadcasts.py:81` |
| `BroadcastDraftContentSerializer.ctas (BroadcastCtaSerializer)` | `max_length=3; default=list` | field / model | `backend/apps/events/serializers_broadcasts.py:85` |
| `BroadcastTestSerializer.preview_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_broadcasts.py:93` |
| `BroadcastSendSerializer.recipient_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_broadcasts.py:98` |
| `BroadcastTalliesSerializer.total (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_broadcasts.py:109` |
| `BroadcastTalliesSerializer.delivered (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_broadcasts.py:110` |
| `BroadcastTalliesSerializer.waiting (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_broadcasts.py:111` |
| `BroadcastTalliesSerializer.failed (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_broadcasts.py:112` |
| `BroadcastTalliesSerializer.skipped (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_broadcasts.py:113` |
| `BroadcastTestResultSerializer.allowed_actions (serializers.ListField)` | `max_length=0` | field / model | `backend/apps/events/serializers_broadcasts.py:146` |
| `CertificateParametersSerializer.version (serializers.IntegerField)` | `min_value=1, max_value=2` | field / model | `backend/apps/events/serializers_certificate_templates.py:12` |
| `CertificateParametersSerializer.page_width_mm (serializers.FloatField)` | `min_value=100, max_value=420` | field / model | `backend/apps/events/serializers_certificate_templates.py:13` |
| `CertificateParametersSerializer.page_height_mm (serializers.FloatField)` | `min_value=100, max_value=420` | field / model | `backend/apps/events/serializers_certificate_templates.py:14` |
| `CertificateParametersSerializer.grid_mm (serializers.FloatField)` | `min_value=0.5, max_value=10` | field / model | `backend/apps/events/serializers_certificate_templates.py:15` |
| `CertificateParametersSerializer.layers (CertificateLayerSerializer)` | `max_length=20` | field / model | `backend/apps/events/serializers_certificate_templates.py:17` |
| `CertificateTemplateWriteSerializer.artwork_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/serializers_certificate_templates.py:45` |
| `CertificatePreviewSerializer.sample_name (serializers.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/events/serializers_certificate_templates.py:54` |
| `CertificateTemplateCommandSerializer.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_certificate_templates.py:60` |
| `SIGNATURE_MAX_BYTES` | `2 * 1024 * 1024` | fixed / see setting | `backend/apps/events/serializers_certificate_templates.py:82` |
| `CertificateArtworkPresignSerializer.content_length (serializers.IntegerField)` | `min_value=1, max_value=MAX_BYTES` | field / model | `backend/apps/events/serializers_certificate_templates.py:87` |
| `EventCheckInResolveRequestSerializer.credential (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/events/serializers_checkin.py:7` |
| `OfflineCheckInOperationSerializer.checkin_token (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_checkin_offline.py:11` |
| `OfflineCheckInSyncRequestSerializer.lease_token (serializers.CharField)` | `max_length=8192` | field / model | `backend/apps/events/serializers_checkin_offline.py:16` |
| `CollaborativeEventRegistrationInputSerializer.host_waiver_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_collaborators.py:35` |
| `CollaborativeEventRegistrationInputSerializer.host_waiver_version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_collaborators.py:38` |
| `CollaborativeEventSerializer.payment_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/serializers_collaborators.py:100` |
| `CollaborativeEventSerializer.capacity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_collaborators.py:114` |
| `FeedbackSurveyWriteSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_feedback.py:11` |
| `FeedbackSurveyWriteSerializer.thank_you_text (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/serializers_feedback.py:12` |
| `MAX_SAFE_INTEGER` | `9007199254740991` | fixed / see setting | `backend/apps/events/serializers_loan_context.py:6` |
| `EventOrganizerReplaceSerializer.organization_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/serializers_organizers.py:7` |
| `EventOrganizerReplaceSerializer.organization_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_organizers.py:8` |
| `AttendanceReplyInput.note (serializers.CharField)` | `max_length=1000; default=''` | field / model | `backend/apps/events/serializers_participation.py:43` |
| `CrewAddInput.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:65` |
| `CrewAddInput.crew_role (serializers.CharField)` | `max_length=60; default=''` | field / model | `backend/apps/events/serializers_participation.py:66` |
| `CrewUpdateInput.expected_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:72` |
| `CrewUpdateInput.crew_role (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/events/serializers_participation.py:73` |
| `CrewReorderInput.ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:80` |
| `CrewReorderInput.ids (serializers.ListField)` | `max_length=500` | field / model | `backend/apps/events/serializers_participation.py:80` |
| `CrewDecisionInput.expected_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:85` |
| `CrewSignupInput.crew_role (serializers.CharField)` | `max_length=60; default=''` | field / model | `backend/apps/events/serializers_participation.py:89` |
| `CrewSignupInput.dietary (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/serializers_participation.py:90` |
| `CrewSignupInput.notes (serializers.CharField)` | `max_length=1000; default=''` | field / model | `backend/apps/events/serializers_participation.py:91` |
| `CheckInListInput.name (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/events/serializers_participation.py:150` |
| `CheckInListInput.addon_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:153` |
| `CheckInListInput.per_person (serializers.IntegerField)` | `min_value=1, max_value=20` | field / model | `backend/apps/events/serializers_participation.py:154` |
| `CheckInListReorderInput.ordered_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:160` |
| `CheckInListReorderInput.ordered_ids (serializers.ListField)` | `min_length=0, max_length=100` | field / model | `backend/apps/events/serializers_participation.py:160` |
| `CheckInListScanInput.registration_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_participation.py:182` |
| `PublicEventSerializer.capacity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_public.py:117` |
| `PublicEventSerializer.payment_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/serializers_public.py:120` |
| `PublicEventRegistrationInputSerializer.host_waiver_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_public.py:202` |
| `PublicEventRegistrationInputSerializer.host_waiver_version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_public.py:203` |
| `PublicEventRegistrationInputSerializer.phone (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_public.py:205` |
| `PublicEventRegistrationInputSerializer.invite_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/serializers_public.py:207` |
| `PublicEventRegistrationInputSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_public.py:208` |
| `PublicEventRegistrationInputSerializer.promo_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/serializers_public.py:209` |
| `PublicEventRegistrationInputSerializer.stage_forms (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/events/serializers_public.py:212` |
| `EventPublicSurfaceInput.join_url (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/serializers_public_surface.py:42` |
| `EventStaffRegistrationSerializer.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_registration_admin.py:82` |
| `EventStaffRegistrationSerializer.invite_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/serializers_registration_admin.py:83` |
| `EventStaffRegistrationSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_registration_admin.py:84` |
| `EventStaffRegistrationSerializer.promo_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/serializers_registration_admin.py:85` |
| `EventStaffRegistrationSerializer.phone (serializers.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/events/serializers_registration_admin.py:90` |
| `EventEligibleMemberSerializer.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_registration_admin.py:100` |
| `RegistrationFormInput.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_registration_form.py:13` |
| `EventSeriesWriteSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_series.py:28` |
| `EventSeriesWriteSerializer.location (serializers.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/events/serializers_series.py:30` |
| `EventSeriesWriteSerializer.venue_address (serializers.CharField)` | `max_length=ADDRESS_MAX` | field / model | `backend/apps/events/serializers_series.py:31` |
| `EventSeriesWriteSerializer.venue_map_url (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/serializers_series.py:32` |
| `EventSeriesWriteSerializer.capacity (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/events/serializers_series.py:39` |
| `EventSeriesWriteSerializer.payment_amount (MoneyField)` | `max_digits=13, min_value=0; default=0` | field / model | `backend/apps/events/serializers_series.py:40` |
| `EventSeriesWriteSerializer.cancellation_cutoff_hours (serializers.IntegerField)` | `min_value=0, max_value=8760; default=None` | field / model | `backend/apps/events/serializers_series.py:44` |
| `EventSeriesWriteSerializer.registration_cutoff_lead_minutes (serializers.IntegerField)` | `min_value=0; default=None` | field / model | `backend/apps/events/serializers_series.py:47` |
| `EventSeriesWriteSerializer.recurrence_timezone (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_series.py:53` |
| `EventSeriesWriteSerializer.recurrence_rule (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/events/serializers_series.py:56` |
| `EventSeriesWriteSerializer.duration_minutes (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_series.py:57` |
| `SpeakerAssignInputSerializer.user_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_speakers.py:43` |
| `SpeakerAssignInputSerializer.display_name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/events/serializers_speakers.py:44` |
| `SpeakerAssignInputSerializer.section_slug (serializers.SlugField)` | `max_length=80; default=''` | field / model | `backend/apps/events/serializers_speakers.py:45` |
| `SpeakerInviteInputSerializer.display_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_speakers.py:50` |
| `SpeakerInviteInputSerializer.section_slug (serializers.SlugField)` | `max_length=80; default=''` | field / model | `backend/apps/events/serializers_speakers.py:51` |
| `SpeakerClaimInputSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_speakers.py:72` |
| `StaffGrantPermissionsSerializer.permissions (serializers.ListField)` | `min_length=1, max_length=5` | field / model | `backend/apps/events/serializers_staff_grants.py:20` |
| `StaffGrantInviteInputSerializer.track_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_staff_grants.py:40` |
| `StaffGrantInviteInputSerializer.track_ids (serializers.ListField)` | `max_length=50; default=list` | field / model | `backend/apps/events/serializers_staff_grants.py:40` |
| `StaffGrantRedeemSerializer.token (serializers.CharField)` | `min_length=32, max_length=128` | field / model | `backend/apps/events/serializers_staff_grants.py:70` |
| `InviteInputSerializer.max_uses (serializers.IntegerField)` | `min_value=1; default=1` | field / model | `backend/apps/events/serializers_ticketing.py:9` |
| `PromoInputSerializer.code (serializers.CharField)` | `max_length=128, min_length=8` | field / model | `backend/apps/events/serializers_ticketing.py:23` |
| `PromoInputSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing.py:27` |
| `PromoInputSerializer.percent_off (serializers.IntegerField)` | `min_value=0, max_value=100; default=0` | field / model | `backend/apps/events/serializers_ticketing.py:28` |
| `PromoInputSerializer.amount_off (MoneyField)` | `max_digits=13, min_value=0; default=0` | field / model | `backend/apps/events/serializers_ticketing.py:29` |
| `PromoInputSerializer.max_uses (serializers.IntegerField)` | `min_value=1; default=1` | field / model | `backend/apps/events/serializers_ticketing.py:30` |
| `OrderTicketItemSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing_orders.py:14` |
| `OrderTicketItemSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/serializers_ticketing_orders.py:15` |
| `OrderTicketItemSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/events/serializers_ticketing_orders.py:16` |
| `OrderAddonItemSerializer.addon_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing_orders.py:21` |
| `OrderAddonItemSerializer.variant_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing_orders.py:22` |
| `OrderAddonItemSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/events/serializers_ticketing_orders.py:23` |
| `OrderRequestSerializer.promo_code (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/serializers_ticketing_orders.py:31` |
| `OrderRequestSerializer.access_codes (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/serializers_ticketing_orders.py:32` |
| `OrderRequestSerializer.access_codes (serializers.ListField)` | `max_length=5; default=list` | field / model | `backend/apps/events/serializers_ticketing_orders.py:32` |
| `OrderRequestSerializer.attendees (serializers.ListField)` | `max_length=50; default=list` | field / model | `backend/apps/events/serializers_ticketing_orders.py:35` |
| `OrderRequestSerializer.digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_ticketing_orders.py:37` |
| `OrderQuoteResponseSerializer.promo_saving (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/serializers_ticketing_orders.py:43` |
| `TicketClaimInputSerializer.host_waiver_version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/serializers_ticketing_orders.py:129` |
| `EventRefundPolicyInputSerializer.full_before_minutes (serializers.IntegerField)` | `min_value=0, max_value=525600` | field / model | `backend/apps/events/serializers_ticketing_staff.py:70` |
| `EventRefundPolicyInputSerializer.partial_before_minutes (serializers.IntegerField)` | `min_value=0, max_value=525600` | field / model | `backend/apps/events/serializers_ticketing_staff.py:71` |
| `EventRefundPolicyInputSerializer.partial_percent (serializers.IntegerField)` | `min_value=0, max_value=100` | field / model | `backend/apps/events/serializers_ticketing_staff.py:72` |
| `EventRefundPolicyInputSerializer.cancellation_fee (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/events/serializers_ticketing_staff.py:73` |
| `EventRefundPolicyInputSerializer.policy_text (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/serializers_ticketing_staff.py:74` |
| `VenueFeeInputSerializer.payer_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing_staff.py:85` |
| `VenueFeeInputSerializer.organization_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing_staff.py:86` |
| `VenueFeeInputSerializer.room_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_ticketing_staff.py:87` |
| `VenueFeeInputSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/events/serializers_ticketing_staff.py:90` |
| `DeskCollectSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/serializers_ticketing_staff.py:121` |
| `WebsiteSectionInput.slug (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/events/serializers_website.py:19` |
| `WebsiteSectionInput.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_website.py:20` |
| `WebsiteSectionInput.body (serializers.CharField)` | `max_length=10000; default=''` | field / model | `backend/apps/events/serializers_website.py:21` |
| `WebsiteSectionInput.headline (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_website.py:23` |
| `WebsiteSectionInput.organization (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_website.py:24` |
| `WebsiteSectionInput.icon (serializers.CharField)` | `max_length=40` | field / model | `backend/apps/events/serializers_website.py:29` |
| `WebsiteSectionInput.asset_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/serializers_website.py:30` |
| `WebsiteSectionInput.position (serializers.IntegerField)` | `min_value=0, max_value=1000; default=0` | field / model | `backend/apps/events/serializers_website.py:32` |
| `WebsiteSessionInput.slug (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/events/serializers_website.py:43` |
| `WebsiteSessionInput.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_website.py:44` |
| `WebsiteSessionInput.body (serializers.CharField)` | `max_length=10000; default=''` | field / model | `backend/apps/events/serializers_website.py:45` |
| `WebsiteSessionInput.track (serializers.SlugField)` | `max_length=80; default=None` | field / model | `backend/apps/events/serializers_website.py:48` |
| `WebsiteSessionInput.room (serializers.SlugField)` | `max_length=80; default=None` | field / model | `backend/apps/events/serializers_website.py:49` |
| `WebsiteSessionInput.speakers (serializers.ListField)` | `max_length=20; default=list` | field / model | `backend/apps/events/serializers_website.py:50` |
| `WebsiteSessionInput.speakers (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/events/serializers_website.py:50` |
| `WebsiteContentInput.revision (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_website.py:55` |
| `WebsiteContentInput.sections (WebsiteSectionInput)` | `max_length=100` | field / model | `backend/apps/events/serializers_website.py:56` |
| `WebsiteContentInput.sessions (WebsiteSessionInput)` | `max_length=200` | field / model | `backend/apps/events/serializers_website.py:57` |
| `WebsiteReleaseInput.revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_website.py:67` |
| `WebsiteDelayInput.revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_website.py:71` |
| `WebsiteDelayInput.delay_minutes (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/events/serializers_website.py:73` |
| `WebsiteAssetInput.revision (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/serializers_website.py:77` |
| `WebsiteAssetInput.alt_text (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/serializers_website.py:79` |
| `WebsiteAssetInput.replace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_website.py:80` |
| `HttpLinkField.super().__init__` | `max_length=500` | field / model | `backend/apps/events/serializers_website_content.py:14` |
| `WebsiteVenueSerializer.name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/events/serializers_website_content.py:24` |
| `WebsiteVenueSerializer.address (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/events/serializers_website_content.py:25` |
| `WebsiteVenueSerializer.city (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/events/serializers_website_content.py:26` |
| `WebsiteVenueSerializer.country (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/events/serializers_website_content.py:27` |
| `WebsiteVenueSerializer.latitude (serializers.FloatField)` | `min_value=-90, max_value=90; default=None` | field / model | `backend/apps/events/serializers_website_content.py:28` |
| `WebsiteVenueSerializer.longitude (serializers.FloatField)` | `min_value=-180, max_value=180; default=None` | field / model | `backend/apps/events/serializers_website_content.py:29` |
| `WebsiteVenueSerializer.directions (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/serializers_website_content.py:31` |
| `WebsiteVenueSerializer.parking (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/serializers_website_content.py:32` |
| `WebsiteVenueSerializer.public_transport (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/serializers_website_content.py:33` |
| `WebsiteVenueSerializer.accessibility_notes (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/serializers_website_content.py:34` |
| `WebsitePageFields.tagline (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/serializers_website_content.py:51` |
| `WebsitePageFields.section_order (serializers.ListField)` | `min_length=len(PAGE_GROUPS) - 1, max_length=len(PAGE_GROUPS)` | field / model | `backend/apps/events/serializers_website_content.py:53` |
| `EventWebsitePublishInput.website_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/serializers_website_publish.py:9` |
| `WebsiteDelayTarget.working_delay_minutes (s.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/events/serializers_website_state.py:42` |
| `WebsiteDelayTarget.public_delay_minutes (s.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/events/serializers_website_state.py:43` |
| `MAX_BATCH` | `200` | fixed / see setting | `backend/apps/events/series_invites.py:24` |
| `add.payload (serializers.ListField)` | `min_length=1, max_length=MAX_BATCH` | field / model | `backend/apps/events/series_invites.py:45` |
| `MAX_AUDIENCE_ORGANIZATIONS` | `50` | fixed / see setting | `backend/apps/events/services_audience_organizations.py:18` |
| `bulk_invites.payload (serializers.ListField)` | `min_length=1, max_length=200` | field / model | `backend/apps/events/services_bulk_invites.py:30` |
| `MAX_ORGANIZERS` | `50` | fixed / see setting | `backend/apps/events/services_organizers.py:14` |
| `MAX_CANDIDATES` | `500` | fixed / see setting | `backend/apps/events/services_recurrence.py:10` |
| `MAX_FUTURE_OCCURRENCES` | `48` | fixed / see setting | `backend/apps/events/services_recurrence.py:11` |
| `EventSpeaker.display_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/speaker_identity_models.py:33` |
| `EventSpeaker.linked_via (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/events/speaker_identity_models.py:34` |
| `EventSpeaker.claim_token_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/events/speaker_identity_models.py:37` |
| `EventStageForm.slug (models.SlugField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/definition_models.py:18` |
| `EventStageForm.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/staged_forms/definition_models.py:19` |
| `EventStageForm.stage (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/staged_forms/definition_models.py:20` |
| `EventStageForm.activation_point (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/events/staged_forms/definition_models.py:22` |
| `EventStageForm.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/staged_forms/definition_models.py:24` |
| `EventStageForm.opening_mode (models.CharField)` | `max_length=16; default='trigger'` | field / model | `backend/apps/events/staged_forms/definition_models.py:29` |
| `EventStageForm.due_mode (models.CharField)` | `max_length=16; default='after_trigger'` | field / model | `backend/apps/events/staged_forms/definition_models.py:32` |
| `EventStageForm.missed_action (models.CharField)` | `max_length=8; default='none'` | field / model | `backend/apps/events/staged_forms/definition_models.py:38` |
| `MAX_BYTES` | `10 * 1024 * 1024` | fixed / see setting | `backend/apps/events/staged_forms/file_validation.py:7` |
| `EventStageMilestone.kind (models.CharField)` | `max_length=16; default='shortlisted'` | field / model | `backend/apps/events/staged_forms/milestone_models.py:12` |
| `StageFormAssignment.trigger_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/response_models.py:15` |
| `StageFormAssignment.state (models.CharField)` | `max_length=12; default='scheduled'` | field / model | `backend/apps/events/staged_forms/response_models.py:18` |
| `StageFormAssignment.cancellation_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/response_models.py:36` |
| `StageFormAssignment.reassignment_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/response_models.py:40` |
| `StageFormResponse.state (models.CharField)` | `max_length=12; default='draft'` | field / model | `backend/apps/events/staged_forms/response_models.py:61` |
| `StageCommand.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/staged_forms/serializers.py:11` |
| `StageSettingsSerializer.slug (serializers.SlugField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/serializers.py:24` |
| `StageSettingsSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/staged_forms/serializers.py:25` |
| `StageSettingsSerializer.opening_offset_seconds (serializers.IntegerField)` | `min_value=-31536000, max_value=31536000` | field / model | `backend/apps/events/staged_forms/serializers.py:30` |
| `StageSettingsSerializer.due_after_seconds (serializers.IntegerField)` | `min_value=1, max_value=31536000` | field / model | `backend/apps/events/staged_forms/serializers.py:33` |
| `StageSettingsSerializer.due_event_offset_seconds (serializers.IntegerField)` | `min_value=-31536000, max_value=31536000` | field / model | `backend/apps/events/staged_forms/serializers.py:34` |
| `StageSettingsSerializer.reminder_offsets (serializers.IntegerField)` | `min_value=-31536000, max_value=-1` | field / model | `backend/apps/events/staged_forms/serializers.py:35` |
| `StageSettingsSerializer.reminder_offsets (serializers.ListField)` | `max_length=10` | field / model | `backend/apps/events/staged_forms/serializers.py:35` |
| `StageSettingsSerializer.blocked_actions (serializers.ListField)` | `max_length=3` | field / model | `backend/apps/events/staged_forms/serializers.py:38` |
| `StageResponseCommand.expected_assignment_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:49` |
| `StageResponseCommand.saved_detail_versions (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/staged_forms/serializers.py:54` |
| `StageResponseCommand.event_date_revision (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:55` |
| `StageActivationCommand.participant_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:66` |
| `StageActivationCommand.participant_ids (serializers.ListField)` | `max_length=1000` | field / model | `backend/apps/events/staged_forms/serializers.py:66` |
| `CancelStageAssignmentCommand.expected_response_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:70` |
| `CancelStageAssignmentCommand.expected_stage_form_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:71` |
| `CancelStageAssignmentCommand.reason (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/events/staged_forms/serializers.py:73` |
| `ReassignStageAssignmentCommand.replacement_form_revision_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:78` |
| `ShortlistCommand.participant_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers.py:87` |
| `ShortlistCommand.participant_ids (serializers.ListField)` | `max_length=100` | field / model | `backend/apps/events/staged_forms/serializers.py:87` |
| `StageFileCreateCommand.expected_response_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers_uploads.py:7` |
| `StageFileCreateCommand.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/events/staged_forms/serializers_uploads.py:9` |
| `StageFileCreateCommand.size_bytes (serializers.IntegerField)` | `min_value=1, max_value=10485760` | field / model | `backend/apps/events/staged_forms/serializers_uploads.py:10` |
| `StageFileCompleteCommand.generation (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/staged_forms/serializers_uploads.py:15` |
| `StageFormAsset.question_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/upload_models.py:14` |
| `StageFormAsset.purpose (models.CharField)` | `max_length=16; default='stage_form_file'` | field / model | `backend/apps/events/staged_forms/upload_models.py:15` |
| `StageFormAsset.state (models.CharField)` | `max_length=12; default='initiated'` | field / model | `backend/apps/events/staged_forms/upload_models.py:16` |
| `StageFormAsset.declared_mime (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/staged_forms/upload_models.py:22` |
| `StageFormAsset.canonical_mime (models.CharField)` | `max_length=100` | field / model | `backend/apps/events/staged_forms/upload_models.py:23` |
| `StageFormAsset.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/upload_models.py:24` |
| `StageFormAsset.staging_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/staged_forms/upload_models.py:26` |
| `StageFormAsset.staging_version_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/staged_forms/upload_models.py:27` |
| `StageFormAsset.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/staged_forms/upload_models.py:28` |
| `StageFormAsset.final_version_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/staged_forms/upload_models.py:29` |
| `StageFormAsset.scan_status (models.CharField)` | `max_length=8; default='pending'` | field / model | `backend/apps/events/staged_forms/upload_models.py:30` |
| `StageFormAsset.scanner_policy (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/upload_models.py:31` |
| `StageFormAsset.scanner_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/upload_models.py:32` |
| `StageFormAsset.error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/upload_models.py:33` |
| `StageFileCleanup.bucket (models.CharField)` | `max_length=255` | field / model | `backend/apps/events/staged_forms/upload_models.py:63` |
| `StageFileCleanup.staging_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/staged_forms/upload_models.py:64` |
| `StageFileCleanup.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/events/staged_forms/upload_models.py:65` |
| `StageFileCleanup.last_error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/upload_models.py:72` |
| `StageActivationJob.command_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/staged_forms/work_models.py:20` |
| `StageActivationJob.state (models.CharField)` | `max_length=12; default='pending'` | field / model | `backend/apps/events/staged_forms/work_models.py:24` |
| `GalleryConsentRevision.action (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/submissions/gallery_models.py:39` |
| `GalleryConsentRevision.scope (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/submissions/gallery_models.py:40` |
| `GalleryEntry.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/submissions/gallery_models.py:61` |
| `GalleryEntry.description (models.TextField)` | `max_length=12000` | field / model | `backend/apps/events/submissions/gallery_models.py:62` |
| `GalleryEntryLink.url (models.URLField)` | `max_length=2048` | field / model | `backend/apps/events/submissions/gallery_models.py:87` |
| `GalleryEntryLink.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/events/submissions/gallery_models.py:88` |
| `GalleryGrantInput.snapshot_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/gallery_serializers.py:10` |
| `GalleryWithdrawInput.scope (serializers.CharField)` | `max_length=8` | field / model | `backend/apps/events/submissions/gallery_serializers.py:23` |
| `GalleryPublishInput.result_revision_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/submissions/gallery_serializers.py:38` |
| `GalleryHideInput.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/submissions/gallery_serializers.py:43` |
| `GalleryAmendInput.snapshot_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/gallery_serializers.py:47` |
| `GalleryAmendInput.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/submissions/gallery_serializers.py:48` |
| `GalleryResultCorrectionInput.result_revision_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/gallery_serializers.py:52` |
| `GalleryResultCorrectionInput.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/events/submissions/gallery_serializers.py:53` |
| `MAX_ATTEMPTS` | `3` | fixed / see setting | `backend/apps/events/submissions/integrity_jobs.py:24` |
| `AssetFields.kind (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/submissions/models_assets.py:13` |
| `AssetFields.purpose (models.CharField)` | `max_length=32; default='project'` | field / model | `backend/apps/events/submissions/models_assets.py:14` |
| `AssetFields.original_filename (models.CharField)` | `max_length=240` | field / model | `backend/apps/events/submissions/models_assets.py:16` |
| `AssetFields.extension (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/submissions/models_assets.py:17` |
| `AssetFields.subtype (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/submissions/models_assets.py:18` |
| `AssetFields.policy_name (models.CharField)` | `max_length=64; default='hackathon-maker-v1'` | field / model | `backend/apps/events/submissions/models_assets.py:19` |
| `AssetFields.declared_mime (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/submissions/models_assets.py:22` |
| `AssetFields.canonical_mime (models.CharField)` | `max_length=160` | field / model | `backend/apps/events/submissions/models_assets.py:24` |
| `AssetFields.staging_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/submissions/models_assets.py:26` |
| `AssetFields.verification_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/submissions/models_assets.py:27` |
| `AssetFields.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/submissions/models_assets.py:28` |
| `AssetFields.source_version_id (models.CharField)` | `max_length=256` | field / model | `backend/apps/events/submissions/models_assets.py:29` |
| `AssetFields.verification_version_id (models.CharField)` | `max_length=256` | field / model | `backend/apps/events/submissions/models_assets.py:30` |
| `AssetFields.final_version_id (models.CharField)` | `max_length=256` | field / model | `backend/apps/events/submissions/models_assets.py:31` |
| `AssetFields.source_etag (models.CharField)` | `max_length=256` | field / model | `backend/apps/events/submissions/models_assets.py:32` |
| `AssetFields.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:33` |
| `AssetFields.original_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:34` |
| `AssetFields.state (models.CharField)` | `max_length=24; default='reserved'` | field / model | `backend/apps/events/submissions/models_assets.py:35` |
| `AssetFields.scan_backend (models.CharField)` | `max_length=16; default='none'` | field / model | `backend/apps/events/submissions/models_assets.py:36` |
| `AssetFields.scan_status (models.CharField)` | `max_length=24; default='pending'` | field / model | `backend/apps/events/submissions/models_assets.py:37` |
| `AssetFields.scan_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:38` |
| `AssetFields.failure_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:52` |
| `HackathonParticipantAsset.purpose (models.CharField)` | `max_length=32; default='resume'` | field / model | `backend/apps/events/submissions/models_assets.py:85` |
| `EventAssetUsage.retention_anchor_kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/submissions/models_assets.py:103` |
| `SubmissionAssetWork.state (models.CharField)` | `max_length=24; default='pending'` | field / model | `backend/apps/events/submissions/models_assets.py:113` |
| `SubmissionAssetWork.last_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:118` |
| `EventAssetObligation.asset_label (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:136` |
| `EventAssetObligation.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/submissions/models_assets.py:140` |
| `EventAssetObligation.staging_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/submissions/models_assets.py:141` |
| `EventAssetObligation.verification_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/events/submissions/models_assets.py:142` |
| `EventAssetObligation.last_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:156` |
| `EventProgrammeSweepCursor.namespace (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_assets.py:168` |
| `HackathonSubmission.state (models.CharField)` | `max_length=24; default='draft'` | field / model | `backend/apps/events/submissions/models_projects.py:14` |
| `HackathonSubmission.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/events/submissions/models_projects.py:17` |
| `HackathonSubmission.tagline (models.CharField)` | `max_length=300` | field / model | `backend/apps/events/submissions/models_projects.py:18` |
| `HackathonSubmission.triage (models.CharField)` | `max_length=16; default='pending'` | field / model | `backend/apps/events/submissions/models_projects.py:32` |
| `HackathonSubmission.triage_reason (models.TextField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/models_projects.py:33` |
| `SubmissionSnapshot.content_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_projects.py:54` |
| `SubmissionSnapshot.source_content_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_projects.py:55` |
| `SubmissionSnapshot.amendment_reason (models.TextField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/models_projects.py:58` |
| `SubmissionLink.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/submissions/models_projects.py:75` |
| `SubmissionLink.url (models.URLField)` | `max_length=2048` | field / model | `backend/apps/events/submissions/models_projects.py:76` |
| `SubmissionLink.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/submissions/models_projects.py:77` |
| `SnapshotLink.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/events/submissions/models_projects.py:98` |
| `SnapshotLink.url (models.URLField)` | `max_length=2048` | field / model | `backend/apps/events/submissions/models_projects.py:99` |
| `SnapshotLink.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/events/submissions/models_projects.py:100` |
| `SubmissionIntegrityFlag.rule_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_projects.py:129` |
| `SubmissionIntegrityFlag.severity (models.CharField)` | `max_length=16; default='informational'` | field / model | `backend/apps/events/submissions/models_projects.py:130` |
| `SubmissionIntegrityFlag.state (models.CharField)` | `max_length=16; default='open'` | field / model | `backend/apps/events/submissions/models_projects.py:133` |
| `SubmissionIntegrityFlag.reason (models.TextField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/models_projects.py:135` |
| `MAX_STAGES` | `50` | fixed / see setting | `backend/apps/events/submissions/models_stages.py:20` |
| `SubmissionStage.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/events/submissions/models_stages.py:26` |
| `SubmissionStage.description (models.TextField)` | `max_length=2000` | field / model | `backend/apps/events/submissions/models_stages.py:27` |
| `SubmissionStage.late_policy (models.CharField)` | `max_length=16; default='reject'` | field / model | `backend/apps/events/submissions/models_stages.py:31` |
| `SubmissionStage.resubmission (models.CharField)` | `max_length=16; default='until_deadline'` | field / model | `backend/apps/events/submissions/models_stages.py:32` |
| `SubmissionStage.content_mode (models.CharField)` | `max_length=16; default='files_and_links'` | field / model | `backend/apps/events/submissions/models_stages.py:34` |
| `SubmissionStage.shortlist_label (models.CharField)` | `max_length=60` | field / model | `backend/apps/events/submissions/models_stages.py:44` |
| `SubmissionStageEntry.triage (models.CharField)` | `max_length=16; default='pending'` | field / model | `backend/apps/events/submissions/models_stages.py:94` |
| `StageExtension.reason (models.TextField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/models_stages.py:108` |
| `StageShortlist.selection (models.CharField)` | `max_length=8` | field / model | `backend/apps/events/submissions/models_stages.py:131` |
| `StageShortlist.fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/models_stages.py:136` |
| `SUBMISSION_CAP` | `1536 * MIB` | fixed / see setting | `backend/apps/events/submissions/quota.py:9` |
| `MAX_ASSETS` | `100` | fixed / see setting | `backend/apps/events/submissions/quota.py:10` |
| `GROUP_CAPS` | `{'video': 500, 'deck': 50, 'images': 50, 'source': 200, 'hardware-pcb': 150, 'hardware-cad': 500, 'firmware': 50, 'fab-2d': 150, 'fab-3dprint': 500, 'fab-cnc': 300, 'embroidery': 50, 'archives': 200, 'resume': 1536}` | fixed / see setting | `backend/apps/events/submissions/quota.py:11` |
| `CommandSerializer.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/submissions/serializers.py:19` |
| `SubmitSerializer.stage_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:23` |
| `DeclarationSerializer.details (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/events/submissions/serializers.py:29` |
| `LinkSerializer.url (serializers.URLField)` | `max_length=2048` | field / model | `backend/apps/events/submissions/serializers.py:34` |
| `ProjectPatchSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/events/submissions/serializers.py:39` |
| `ProjectPatchSerializer.tagline (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/events/submissions/serializers.py:40` |
| `ProjectPatchSerializer.problem (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/events/submissions/serializers.py:41` |
| `ProjectPatchSerializer.description (serializers.CharField)` | `max_length=30000` | field / model | `backend/apps/events/submissions/serializers.py:42` |
| `ProjectPatchSerializer.challenges (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/events/submissions/serializers.py:43` |
| `ProjectPatchSerializer.tech_tags (serializers.CharField)` | `max_length=50` | field / model | `backend/apps/events/submissions/serializers.py:44` |
| `ProjectPatchSerializer.tech_tags (serializers.ListField)` | `max_length=30` | field / model | `backend/apps/events/submissions/serializers.py:44` |
| `ProjectPatchSerializer.track_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:48` |
| `ProjectPatchSerializer.track_ids (serializers.ListField)` | `max_length=30` | field / model | `backend/apps/events/submissions/serializers.py:48` |
| `ProjectPatchSerializer.prize_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:49` |
| `ProjectPatchSerializer.prize_ids (serializers.ListField)` | `max_length=30` | field / model | `backend/apps/events/submissions/serializers.py:49` |
| `ProjectPatchSerializer.asset_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:50` |
| `ProjectPatchSerializer.asset_ids (serializers.ListField)` | `max_length=100` | field / model | `backend/apps/events/submissions/serializers.py:50` |
| `ProjectPatchSerializer.public_asset_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:51` |
| `ProjectPatchSerializer.public_asset_ids (serializers.ListField)` | `max_length=100` | field / model | `backend/apps/events/submissions/serializers.py:51` |
| `ProjectPatchSerializer.links (LinkSerializer)` | `max_length=30` | field / model | `backend/apps/events/submissions/serializers.py:53` |
| `AmendSerializer.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/serializers.py:57` |
| `AmendSerializer.stage_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:59` |
| `TriageSerializer.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/serializers.py:65` |
| `TriageSerializer.stage_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:66` |
| `UploadSerializer.filename (serializers.CharField)` | `max_length=240` | field / model | `backend/apps/events/submissions/serializers.py:71` |
| `UploadSerializer.mime (serializers.CharField)` | `max_length=160` | field / model | `backend/apps/events/submissions/serializers.py:72` |
| `UploadSerializer.bytes (serializers.IntegerField)` | `min_value=1, max_value=2 * 1024 ** 3` | field / model | `backend/apps/events/submissions/serializers.py:73` |
| `UploadSerializer.subtype (serializers.CharField)` | `max_length=32; default='auto'` | field / model | `backend/apps/events/submissions/serializers.py:76` |
| `ResumeUploadSerializer.filename (serializers.CharField)` | `max_length=240` | field / model | `backend/apps/events/submissions/serializers.py:80` |
| `ResumeUploadSerializer.bytes (serializers.IntegerField)` | `min_value=1, max_value=10 * 1024 ** 2` | field / model | `backend/apps/events/submissions/serializers.py:81` |
| `FromSavedSerializer.saved_asset_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:86` |
| `FromSavedSerializer.saved_detail_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:87` |
| `AssetCommandSerializer.generation (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers.py:91` |
| `PartsSerializer.part_numbers (serializers.IntegerField)` | `min_value=1, max_value=10000` | field / model | `backend/apps/events/submissions/serializers.py:95` |
| `PartsSerializer.part_numbers (serializers.ListField)` | `max_length=100` | field / model | `backend/apps/events/submissions/serializers.py:95` |
| `StageCustomFieldInput.label (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/submissions/serializers_stages.py:15` |
| `StageCustomFieldInput.choices (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/events/submissions/serializers_stages.py:18` |
| `StageCustomFieldInput.choices (serializers.ListField)` | `max_length=20; default=list` | field / model | `backend/apps/events/submissions/serializers_stages.py:18` |
| `StageCustomFieldInput.help (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/submissions/serializers_stages.py:19` |
| `SubmissionStageInput.id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:32` |
| `SubmissionStageInput.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/events/submissions/serializers_stages.py:33` |
| `SubmissionStageInput.description (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/events/submissions/serializers_stages.py:34` |
| `SubmissionStageInput.grace_minutes (serializers.IntegerField)` | `min_value=0, max_value=1440; default=0` | field / model | `backend/apps/events/submissions/serializers_stages.py:37` |
| `SubmissionStageInput.required_link_kinds (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/events/submissions/serializers_stages.py:43` |
| `SubmissionStageInput.required_link_kinds (serializers.ListField)` | `max_length=8; default=list` | field / model | `backend/apps/events/submissions/serializers_stages.py:43` |
| `SubmissionStageInput.min_files (serializers.IntegerField)` | `min_value=0, max_value=100; default=0` | field / model | `backend/apps/events/submissions/serializers_stages.py:45` |
| `SubmissionStageInput.max_files (serializers.IntegerField)` | `min_value=1, max_value=100; default=None` | field / model | `backend/apps/events/submissions/serializers_stages.py:46` |
| `SubmissionStageInput.max_links (serializers.IntegerField)` | `min_value=1, max_value=30; default=None` | field / model | `backend/apps/events/submissions/serializers_stages.py:47` |
| `SubmissionStageInput.accepted_families (serializers.ListField)` | `max_length=len(FAMILIES); default=list` | field / model | `backend/apps/events/submissions/serializers_stages.py:48` |
| `SubmissionStageInput.max_bytes_per_file (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/events/submissions/serializers_stages.py:50` |
| `SubmissionStageInput.video_hosts (serializers.ListField)` | `max_length=len(VIDEO_HOSTS); default=list` | field / model | `backend/apps/events/submissions/serializers_stages.py:51` |
| `SubmissionStageInput.custom_fields (StageCustomFieldInput)` | `max_length=20; default=list` | field / model | `backend/apps/events/submissions/serializers_stages.py:53` |
| `SubmissionStageInput.shortlist_label (serializers.CharField)` | `max_length=60; default=''` | field / model | `backend/apps/events/submissions/serializers_stages.py:55` |
| `StagePlanInput.expected_fingerprint (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/serializers_stages.py:69` |
| `StagePlanInput.preset (serializers.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/events/submissions/serializers_stages.py:70` |
| `StagePlanInput.stages (SubmissionStageInput)` | `min_length=1, max_length=MAX_STAGES` | field / model | `backend/apps/events/submissions/serializers_stages.py:71` |
| `ShortlistPreviewInput.top_n (serializers.IntegerField)` | `min_value=1, max_value=1000` | field / model | `backend/apps/events/submissions/serializers_stages.py:125` |
| `ShortlistPreviewInput.source_round_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:126` |
| `ShortlistPreviewInput.submission_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:127` |
| `ShortlistPreviewInput.submission_ids (serializers.ListField)` | `max_length=2000; default=list` | field / model | `backend/apps/events/submissions/serializers_stages.py:127` |
| `ShortlistApplyInput.fingerprint (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/submissions/serializers_stages.py:138` |
| `ShortlistPublishInput.shortlist_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:143` |
| `ShortlistPromoteInput.withdrawn_submission_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:148` |
| `ExtensionInput.team_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:204` |
| `ExtensionInput.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/serializers_stages.py:206` |
| `BulkTriageInput.submission_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/serializers_stages.py:221` |
| `BulkTriageInput.submission_ids (serializers.ListField)` | `min_length=1, max_length=500` | field / model | `backend/apps/events/submissions/serializers_stages.py:221` |
| `BulkTriageInput.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/serializers_stages.py:223` |
| `ANSWER_LIMITS` | `{'short_text': 200, 'long_text': 5000, 'url': 2048, 'choice': 80}` | fixed / see setting | `backend/apps/events/submissions/stage_rules.py:11` |
| `SINGLE_LIMIT` | `25 * 1024 ** 2` | fixed / see setting | `backend/apps/events/submissions/storage.py:15` |
| `ProgrammeChargeReadSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/submissions/views_fees.py:24` |
| `ReinstateSerializer.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/submissions/views_reinstate.py:15` |
| `ReinstateSerializer.stage_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/submissions/views_reinstate.py:16` |
| `MAX_CONFLICTS` | `20` | fixed / see setting | `backend/apps/events/venue_conflicts.py:25` |
| `MAX_SAFE` | `9007199254740991` | fixed / see setting | `backend/apps/events/venue_fee_history.py:9` |
| `MAX_PAYMENTS` | `1000` | fixed / see setting | `backend/apps/events/venue_fee_history.py:11` |
| `MAX_AUDITS` | `4000` | fixed / see setting | `backend/apps/events/venue_fee_history.py:12` |
| `EventAudienceOrganizationReplaceSerializer.organization_ids (serializers.ListField)` | `max_length=MAX_AUDIENCE_ORGANIZATIONS` | field / model | `backend/apps/events/views_audience_organizations.py:16` |
| `EventAudienceOrganizationReplaceSerializer.organization_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/views_audience_organizations.py:17` |
| `MAX_SAFE` | `9007199254740991` | fixed / see setting | `backend/apps/events/views_booking_decision.py:25` |
| `DecisionInput.expected_revision (serializers.IntegerField)` | `min_value=0, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:36` |
| `DecisionInput.existing_booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:40` |
| `HistoryEntry.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:53` |
| `DecisionOutput.revision (serializers.IntegerField)` | `min_value=0, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:59` |
| `DecisionOutput.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:63` |
| `DecisionOutput.current_booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:76` |
| `DecisionOutput.current_space_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision.py:92` |
| `ReplacementInput.expected_booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision_replacement.py:24` |
| `ReplacementInput.space_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision_replacement.py:26` |
| `ReplacementInput.member_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision_replacement.py:27` |
| `ReplacementInput.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/events/views_booking_decision_replacement.py:31` |
| `ReplacementOutput.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision_replacement.py:37` |
| `ReplacementOutput.replaces_booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_booking_decision_replacement.py:38` |
| `EventReturnWindowInput.equipment_return_hours (serializers.IntegerField)` | `min_value=0, max_value=720` | field / model | `backend/apps/events/views_equipment_desk.py:62` |
| `PlanLineSerializer.product_id (serializers.IntegerField)` | `min_value=1, max_value=SAFE` | field / model | `backend/apps/events/views_equipment_window.py:85` |
| `PlanLineSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=99` | field / model | `backend/apps/events/views_equipment_window.py:86` |
| `PlanParticipantSerializer.registration_id (serializers.IntegerField)` | `min_value=1, max_value=SAFE` | field / model | `backend/apps/events/views_equipment_window.py:90` |
| `PlanParticipantSerializer.lines (PlanLineSerializer)` | `max_length=20` | field / model | `backend/apps/events/views_equipment_window.py:91` |
| `EventEquipmentPlanSerializer.requested_for (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/events/views_equipment_window.py:97` |
| `EventEquipmentPlanSerializer.lines (PlanLineSerializer)` | `max_length=20` | field / model | `backend/apps/events/views_equipment_window.py:98` |
| `EventEquipmentPlanSerializer.participants (PlanParticipantSerializer)` | `min_length=1, max_length=MAX_PARTICIPANTS` | field / model | `backend/apps/events/views_equipment_window.py:99` |
| `EmbedPolicySerializer.allowed_origins (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/events/views_event_surface_settings.py:35` |
| `EmbedPolicySerializer.allowed_origins (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/events/views_event_surface_settings.py:35` |
| `MAX_SAFE` | `9007199254740991` | fixed / see setting | `backend/apps/events/views_event_with_room.py:17` |
| `RoomStepSerializer.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/events/views_event_with_room.py:30` |
| `IntegrationOrderLineSerializer.unit_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:30` |
| `IntegrationOrderLineSerializer.discount_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:31` |
| `IntegrationOrderLineSerializer.line_total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:32` |
| `IntegrationOrderSerializer.subtotal (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:44` |
| `IntegrationOrderSerializer.discount_total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:45` |
| `IntegrationOrderSerializer.fee_total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:46` |
| `IntegrationOrderSerializer.total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_integration_orders.py:47` |
| `WorkshopMachineLinkInput.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:30` |
| `WorkshopMachineLinkInput.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/views_machine_booking_links.py:32` |
| `MachineReplacementInput.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/events/views_machine_booking_links.py:38` |
| `WorkshopMachineHistory.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:50` |
| `WorkshopMachineLink.link_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:55` |
| `WorkshopMachineLink.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:57` |
| `WorkshopMachineLink.current_booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:59` |
| `WorkshopMachineLink.current_space_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:62` |
| `WorkshopMachineList.withheld (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/views_machine_booking_links.py:84` |
| `WorkshopMachineUnlinked.link_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE` | field / model | `backend/apps/events/views_machine_booking_links.py:157` |
| `MachineEventWrite.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/views_machine_use.py:44` |
| `CostDecisionWrite.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/events/views_machine_use_event.py:67` |
| `SeriesInviteInput.emails (serializers.ListField)` | `min_length=1, max_length=series_invites.MAX_BATCH` | field / model | `backend/apps/events/views_series_invites.py:24` |
| `VisitDaySerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/views_short_links_admin.py:27` |
| `ShortLinkSerializer.total_visits (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/events/views_short_links_admin.py:35` |
| `TypeChangeInputSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/views_ticketing_claims.py:89` |
| `TypeChangeInputSerializer.digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/views_ticketing_claims.py:90` |
| `PassBuySerializer.pass_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/events/views_ticketing_claims.py:123` |
| `PassBuySerializer.digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/events/views_ticketing_claims.py:124` |
| `ShopTierSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_ticketing_shop.py:26` |
| `ShopTicketSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_ticketing_shop.py:32` |
| `ShopTicketSerializer.min_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_ticketing_shop.py:35` |
| `ShopAddonSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_ticketing_shop.py:55` |
| `AccessCodesSerializer.access_codes (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/events/views_ticketing_shop.py:62` |
| `AccessCodesSerializer.access_codes (serializers.ListField)` | `min_length=1, max_length=5` | field / model | `backend/apps/events/views_ticketing_shop.py:62` |
| `TicketShopSerializer.booking_fee_fixed (MoneyField)` | `max_digits=13` | field / model | `backend/apps/events/views_ticketing_shop.py:71` |

</details>

<details>
<summary>evidence (21 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `EvidencePhoto.evidence_type (models.CharField)` | `max_length=20` | field / model | `backend/apps/evidence/models.py:38` |
| `EvidencePhoto.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/evidence/models.py:39` |
| `EvidencePhoto.content_type (models.CharField)` | `max_length=128` | field / model | `backend/apps/evidence/models.py:40` |
| `EvidencePhoto.consumption_state (models.CharField)` | `max_length=16; default=ConsumptionState.LEGACY_UNKNOWN` | field / model | `backend/apps/evidence/models.py:47` |
| `EvidenceUploadFinalization.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/evidence/models.py:93` |
| `EvidenceUploadFinalization.content_type (models.CharField)` | `max_length=128` | field / model | `backend/apps/evidence/models.py:100` |
| `MAX_RETENTION_DAYS` | `3650` | fixed / see setting | `backend/apps/evidence/retention_models.py:8` |
| `MAX_ABANDONED_UPLOAD_DAYS` | `3650` | fixed / see setting | `backend/apps/evidence/retention_models.py:10` |
| `EvidenceRetentionPolicy.object_retention_days (MinValueValidator)` | `min_value=MIN_RETENTION_DAYS` | field / model | `backend/apps/evidence/retention_models.py:29` |
| `EvidenceRetentionPolicy.object_retention_days (MaxValueValidator)` | `max_value=MAX_RETENTION_DAYS` | field / model | `backend/apps/evidence/retention_models.py:30` |
| `EvidenceRetentionPolicy.abandoned_upload_retention_days (MinValueValidator)` | `min_value=MIN_ABANDONED_UPLOAD_DAYS` | field / model | `backend/apps/evidence/retention_models.py:38` |
| `EvidenceRetentionPolicy.abandoned_upload_retention_days (MaxValueValidator)` | `max_value=MAX_ABANDONED_UPLOAD_DAYS` | field / model | `backend/apps/evidence/retention_models.py:39` |
| `EvidenceObjectRetentionState.status (models.CharField)` | `max_length=16; default=Status.EXPIRING` | field / model | `backend/apps/evidence/retention_models.py:83` |
| `EvidenceObjectRetentionState.last_error (models.CharField)` | `max_length=500` | field / model | `backend/apps/evidence/retention_models.py:92` |
| `EvidenceAbandonedUploadReceipt.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/evidence/retention_models.py:154` |
| `EvidenceAbandonedUploadReceipt.storage_identity (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/evidence/retention_models.py:155` |
| `EvidenceAbandonedUploadReceipt.last_error (models.CharField)` | `max_length=500` | field / model | `backend/apps/evidence/retention_models.py:158` |
| `EvidenceUrlRequestSerializer.size_bytes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/evidence/serializers.py:11` |
| `EvidenceRetentionPatchSerializer.object_retention_days (serializers.IntegerField)` | `min_value=30, max_value=3650` | field / model | `backend/apps/evidence/serializers.py:60` |
| `EvidenceRetentionPatchSerializer.abandoned_upload_retention_days (serializers.IntegerField)` | `min_value=1, max_value=3650` | field / model | `backend/apps/evidence/serializers.py:64` |
| `EvidenceRetentionPreviewRequestSerializer.limit (serializers.IntegerField)` | `min_value=1, max_value=1000; default=100` | field / model | `backend/apps/evidence/serializers.py:83` |

</details>

<details>
<summary>forms_schema (2 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_MINOR` | `9007199254740991` | fixed / see setting | `backend/apps/forms_schema/money_values.py:5` |
| `MAX_SECTIONS` | `20` | fixed / see setting | `backend/apps/forms_schema/schema_items_static.py:15` |

</details>

<details>
<summary>hardware_requests (89 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `HardwareRequestItemAsset.outcome (models.CharField)` | `max_length=20; default=Outcome.ISSUED` | field / model | `backend/apps/hardware_requests/asset_link_models.py:22` |
| `EVIDENCE_GRANT_MAX_AGE` | `60 * 60` | fixed / see setting | `backend/apps/hardware_requests/contact_identity.py:27` |
| `MAX_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/hardware_requests/contact_verification.py:36` |
| `MAX_SAFE_ID` | `9007199254740991` | fixed / see setting | `backend/apps/hardware_requests/contextual_equipment_serializers.py:7` |
| `KitSelectionSerializer.id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:11` |
| `KitSelectionSerializer.version (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:12` |
| `ContextualBaseSerializer.event_registration_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID; default=None` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:17` |
| `ContextualBaseSerializer.items (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:20` |
| `ContextualStaffSerializer.booking_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID; default=None` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:42` |
| `ContextualStaffSerializer.borrower_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID; default=None` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:45` |
| `ContextualSelfResultSerializer.plan_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:60` |
| `ContextualStaffResultSerializer.request_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:66` |
| `ContextualStaffResultSerializer.plan_id (serializers.IntegerField)` | `min_value=1, max_value=MAX_SAFE_ID` | field / model | `backend/apps/hardware_requests/contextual_equipment_serializers.py:68` |
| `DirectLoanItemSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=2147483647` | field / model | `backend/apps/hardware_requests/direct_loan_serializers.py:13` |
| `DirectLoanIssueSerializer.qr_payloads (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/hardware_requests/direct_loan_serializers.py:22` |
| `DirectLoanIssueSerializer.qr_payloads (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/direct_loan_serializers.py:23` |
| `DirectLoanIssueSerializer.items (DirectLoanItemSerializer)` | `max_length=20` | field / model | `backend/apps/hardware_requests/direct_loan_serializers.py:28` |
| `DirectLoanReturnSerializer.qr_payload (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/direct_loan_serializers.py:46` |
| `_RequestRef.request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/kiosk_serializers.py:27` |
| `_LoanRef.loan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/kiosk_serializers.py:31` |
| `KioskWorkPackageRequestSerializer.id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/kiosk_serializers.py:82` |
| `KioskEvidencePrepareSerializer.size_bytes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/hardware_requests/kiosk_serializers.py:110` |
| `ContactKitPreviewInputSerializer.payload (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/kit_contact_preview.py:24` |
| `ContactKitPreviewInputSerializer.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hardware_requests/kit_contact_preview.py:26` |
| `KitPreviewInputSerializer.request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/kit_views.py:37` |
| `KitPreviewInputSerializer.loan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/kit_views.py:38` |
| `KitPreviewInputSerializer.container_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/kit_views.py:40` |
| `KitPreviewInputSerializer.qr_payloads (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/kit_views.py:41` |
| `KitPreviewInputSerializer.qr_payloads (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/hardware_requests/kit_views.py:41` |
| `KitPreviewInputSerializer.items (DirectLoanItemSerializer)` | `max_length=20` | field / model | `backend/apps/hardware_requests/kit_views.py:42` |
| `KitPreviewInputSerializer.rejects (IssueRejectSerializer)` | `max_length=20` | field / model | `backend/apps/hardware_requests/kit_views.py:43` |
| `KitPreviewInputSerializer.resolutions (ReturnItemResolutionSerializer)` | `max_length=70` | field / model | `backend/apps/hardware_requests/kit_views.py:44` |
| `MemberKitPreviewInputSerializer.payload (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/kit_views.py:106` |
| `MAX_SAFE` | `9007199254740991` | fixed / see setting | `backend/apps/hardware_requests/loan_context_access.py:10` |
| `CancelRequestSerializer.reason (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/hardware_requests/loan_depth_views.py:26` |
| `WaitlistJoinSerializer.product_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/loan_depth_views.py:62` |
| `WaitlistJoinSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=99; default=1` | field / model | `backend/apps/hardware_requests/loan_depth_views.py:63` |
| `HardwareRequest.anonymous_idempotency_key_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/hardware_requests/models.py:40` |
| `HardwareRequest.anonymous_payload_fingerprint (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/hardware_requests/models.py:45` |
| `HardwareRequest.status (models.CharField)` | `max_length=32; default=Status.PENDING_APPROVAL` | field / model | `backend/apps/hardware_requests/models.py:50` |
| `LoanReservationPolicy.pickup_window_hours (MaxValueValidator)` | `max_value=720` | field / model | `backend/apps/hardware_requests/models_loans.py:18` |
| `LoanReservationPolicy.reservation_max_days_ahead (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/hardware_requests/models_loans.py:20` |
| `LoanReservationPolicy.reservation_max_days_ahead (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/hardware_requests/models_loans.py:20` |
| `LoanReservationPolicy.waitlist_offer_hours (MaxValueValidator)` | `max_value=336` | field / model | `backend/apps/hardware_requests/models_loans.py:22` |
| `LoanReservationPolicy.waitlist_offer_hours (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/hardware_requests/models_loans.py:22` |
| `LoanWaitlistEntry.quantity (MaxValueValidator)` | `max_value=99` | field / model | `backend/apps/hardware_requests/models_loans.py:53` |
| `LoanWaitlistEntry.quantity (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/hardware_requests/models_loans.py:53` |
| `LoanWaitlistEntry.status (models.CharField)` | `max_length=12; default=Status.WAITING` | field / model | `backend/apps/hardware_requests/models_loans.py:54` |
| `ReplayCommand.payload_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/models_replay.py:32` |
| `ReplayCommand.operation_kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/hardware_requests/models_replay.py:33` |
| `ReplayCommand.state (models.CharField)` | `max_length=12; default=State.PREPARED` | field / model | `backend/apps/hardware_requests/models_replay.py:40` |
| `ReplayCommand.failure_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/models_replay.py:49` |
| `ReplayCommand.failure_detail (models.CharField)` | `max_length=200` | field / model | `backend/apps/hardware_requests/models_replay.py:50` |
| `ReplayCommand.resolution_code (models.CharField)` | `max_length=24` | field / model | `backend/apps/hardware_requests/models_replay.py:71` |
| `ReplayDirectReturnSerializer.loan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/replay_payload_serializers.py:27` |
| `ReplayEnvelopeSerializer.version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/hardware_requests/replay_serializers.py:17` |
| `ReplayEnvelopeSerializer.sequence (serializers.IntegerField)` | `min_value=1, max_value=10000` | field / model | `backend/apps/hardware_requests/replay_serializers.py:19` |
| `RequesterAccountability.issue_type (models.CharField)` | `max_length=20` | field / model | `backend/apps/hardware_requests/return_models.py:75` |
| `PublicToolLoan.target_type (models.CharField)` | `max_length=20` | field / model | `backend/apps/hardware_requests/self_checkout_models.py:44` |
| `PublicToolLoan.target_label (models.CharField)` | `max_length=200` | field / model | `backend/apps/hardware_requests/self_checkout_models.py:46` |
| `PublicToolLoan.status (models.CharField)` | `max_length=20; default=Status.CHECKED_OUT` | field / model | `backend/apps/hardware_requests/self_checkout_models.py:52` |
| `PublicToolLoan.source (models.CharField)` | `max_length=32; default=Source.PUBLIC_SELF_CHECKOUT` | field / model | `backend/apps/hardware_requests/self_checkout_models.py:58` |
| `PublicProblemReport.outcome (models.CharField)` | `max_length=20; default=''` | field / model | `backend/apps/hardware_requests/self_checkout_models.py:130` |
| `PublicToolScanSerializer.payload (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:10` |
| `PublicToolCheckoutSerializer.payload (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:30` |
| `PublicToolEvidenceUrlRequestSerializer.size_bytes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:38` |
| `_ContactFields.contact_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:71` |
| `_ContactFields.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:72` |
| `_ContactFields.contact_phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:73` |
| `_ContactFields.evidence_grant (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:75` |
| `ContactEvidenceUrlRequestSerializer.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hardware_requests/self_checkout_serializers.py:87` |
| `RequestItemInputSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=99` | field / model | `backend/apps/hardware_requests/serializers.py:17` |
| `RequestSubmitSerializer.requested_for (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/hardware_requests/serializers.py:25` |
| `RequestSubmitSerializer.items (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/hardware_requests/serializers.py:31` |
| `RequestSubmitSerializer.waitlist_entry_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/hardware_requests/serializers.py:39` |
| `ContactRequestSubmitSerializer.contact_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hardware_requests/serializers.py:59` |
| `ContactRequestSubmitSerializer.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hardware_requests/serializers.py:60` |
| `ContactRequestSubmitSerializer.contact_phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/hardware_requests/serializers.py:61` |
| `PublicRequestSubmitSchemaSerializer.contact_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hardware_requests/serializers.py:72` |
| `PublicRequestSubmitSchemaSerializer.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hardware_requests/serializers.py:73` |
| `PublicRequestSubmitSchemaSerializer.contact_phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/hardware_requests/serializers.py:74` |
| `ContactCodeRequestSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hardware_requests/serializers.py:79` |
| `AcceptQuantitySerializer.quantity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/hardware_requests/serializers_handover.py:8` |
| `IssueRejectSerializer.broken (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/hardware_requests/serializers_handover.py:36` |
| `ReturnItemResolutionSerializer.returned (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/hardware_requests/serializers_handover.py:71` |
| `ReturnItemResolutionSerializer.damaged (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/hardware_requests/serializers_handover.py:72` |
| `ReturnItemResolutionSerializer.missing (serializers.IntegerField)` | `min_value=0; default=0` | field / model | `backend/apps/hardware_requests/serializers_handover.py:73` |
| `DEFAULT_LIMIT` | `200` | fixed / see setting | `backend/apps/hardware_requests/timeline_service_requests.py:14` |
| `MAX_LIMIT` | `500` | fixed / see setting | `backend/apps/hardware_requests/timeline_service_requests.py:15` |

</details>

<details>
<summary>hosting_requests (45 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `HostingRequest.status (models.CharField)` | `max_length=24` | field / model | `backend/apps/hosting_requests/models.py:41` |
| `HostingRequest.requested_kind (models.CharField)` | `max_length=16; default=RequestedKind.MAKERSPACE` | field / model | `backend/apps/hosting_requests/models.py:43` |
| `HostingRequest.source (models.CharField)` | `max_length=16` | field / model | `backend/apps/hosting_requests/models.py:46` |
| `HostingRequest.inviter_kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/hosting_requests/models.py:47` |
| `HostingRequest.applicant_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/models.py:48` |
| `HostingRequest.applicant_email (models.EmailField)` | `max_length=254` | field / model | `backend/apps/hosting_requests/models.py:49` |
| `HostingRequest.applicant_phone (models.CharField)` | `max_length=32` | field / model | `backend/apps/hosting_requests/models.py:50` |
| `HostingRequest.space_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/models.py:51` |
| `HostingRequest.proposed_slug (models.SlugField)` | `max_length=50` | field / model | `backend/apps/hosting_requests/models.py:52` |
| `HostingRequest.location (models.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/models.py:53` |
| `HostingRequest.space_website_url (models.URLField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/models.py:54` |
| `HostingRequest.description (models.TextField)` | `max_length=2000` | field / model | `backend/apps/hosting_requests/models.py:55` |
| `HostingRequest.organization_choice (models.CharField)` | `max_length=8; default=OrganizationChoice.OWN` | field / model | `backend/apps/hosting_requests/models.py:58` |
| `HostingRequest.new_organization_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/models.py:61` |
| `HostingRequest.invite_note (models.CharField)` | `max_length=500` | field / model | `backend/apps/hosting_requests/models.py:72` |
| `HostingRequest.invite_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/hosting_requests/models.py:73` |
| `HostingRequest.access_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/hosting_requests/models.py:75` |
| `HostingRequest.rejection_reason (models.TextField)` | `max_length=2000` | field / model | `backend/apps/hosting_requests/models.py:84` |
| `HostingRequest.changes_note (models.TextField)` | `max_length=2000` | field / model | `backend/apps/hosting_requests/models.py:86` |
| `HostingRequestRevision.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/hosting_requests/models.py:146` |
| `HostingRequestRevision.note (models.TextField)` | `max_length=2000` | field / model | `backend/apps/hosting_requests/models.py:147` |
| `MAX_LOOPS` | `10` | fixed / see setting | `backend/apps/hosting_requests/retention.py:33` |
| `HostingRequestSubmitSerializer.applicant_name (serializers.CharField)` | `min_length=2, max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:12` |
| `HostingRequestSubmitSerializer.applicant_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hosting_requests/serializers.py:13` |
| `HostingRequestSubmitSerializer.applicant_phone (serializers.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:14` |
| `HostingRequestSubmitSerializer.space_name (serializers.CharField)` | `min_length=2, max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:19` |
| `HostingRequestSubmitSerializer.location (serializers.CharField)` | `min_length=2, max_length=200; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:20` |
| `HostingRequestSubmitSerializer.space_website_url (serializers.URLField)` | `max_length=200; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:21` |
| `HostingRequestSubmitSerializer.description (serializers.CharField)` | `min_length=20, max_length=2000` | field / model | `backend/apps/hosting_requests/serializers.py:22` |
| `HostingRequestSubmitSerializer.proposed_slug (serializers.SlugField)` | `max_length=50; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:23` |
| `HostingRequestSubmitSerializer.expected_members (serializers.IntegerField)` | `min_value=1, max_value=100000; default=None` | field / model | `backend/apps/hosting_requests/serializers.py:24` |
| `HostingRequestSubmitSerializer.new_organization_name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:28` |
| `HostingInvitationSubmitSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:44` |
| `HostingTokenSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:51` |
| `HostingResubmitSerializer.token (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:102` |
| `HostingResubmitSerializer.space_name (serializers.CharField)` | `min_length=2, max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:103` |
| `HostingResubmitSerializer.location (serializers.CharField)` | `min_length=2, max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:104` |
| `HostingResubmitSerializer.space_website_url (serializers.URLField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:105` |
| `HostingResubmitSerializer.description (serializers.CharField)` | `min_length=20, max_length=2000` | field / model | `backend/apps/hosting_requests/serializers.py:106` |
| `HostingResubmitSerializer.proposed_slug (serializers.SlugField)` | `max_length=50` | field / model | `backend/apps/hosting_requests/serializers.py:107` |
| `HostingResubmitSerializer.new_organization_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/hosting_requests/serializers.py:108` |
| `HostingResubmitSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:109` |
| `HostingInvitationCreateSerializer.invitee_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/hosting_requests/serializers.py:122` |
| `HostingInvitationCreateSerializer.space_name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:123` |
| `HostingInvitationCreateSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/hosting_requests/serializers.py:124` |

</details>

<details>
<summary>id_programmes (32 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_DECISION` | `500` | fixed / see setting | `backend/apps/id_programmes/cards.py:22` |
| `MAX_BYTES` | `2 * 1024 * 1024` | fixed / see setting | `backend/apps/id_programmes/imports.py:23` |
| `MAX_CELL` | `500` | fixed / see setting | `backend/apps/id_programmes/imports.py:23` |
| `MAX_COLUMNS` | `40` | fixed / see setting | `backend/apps/id_programmes/imports.py:23` |
| `MAX_ROWS` | `2000` | fixed / see setting | `backend/apps/id_programmes/imports.py:23` |
| `IdProgramme.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/id_programmes/models.py:34` |
| `IdProgramme.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/id_programmes/models.py:35` |
| `IdProgramme.status (models.CharField)` | `max_length=8; default=Status.DRAFT` | field / model | `backend/apps/id_programmes/models.py:37` |
| `IdProgramme.id_prefix (models.CharField)` | `max_length=6` | field / model | `backend/apps/id_programmes/models.py:40` |
| `IdProgramme.validity_mode (models.CharField)` | `max_length=12; default=Validity.NONE` | field / model | `backend/apps/id_programmes/models.py:43` |
| `IdProgramme.photo_mode (models.CharField)` | `max_length=8; default=PhotoMode.OPTIONAL` | field / model | `backend/apps/id_programmes/models.py:46` |
| `IdProgrammeCard.email_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/id_programmes/models.py:94` |
| `IdProgrammeCard.photo_object_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/id_programmes/models.py:96` |
| `IdProgrammeCard.photo_content_type (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/id_programmes/models.py:97` |
| `IdProgrammeCard.photo_consent_version (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/id_programmes/models.py:100` |
| `IdProgrammeCard.status (models.CharField)` | `max_length=10; default=Status.PENDING` | field / model | `backend/apps/id_programmes/models.py:101` |
| `IdProgrammeCard.source (models.CharField)` | `max_length=8; default=Source.FORM` | field / model | `backend/apps/id_programmes/models.py:103` |
| `IdProgrammeCard.invite_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/id_programmes/models.py:105` |
| `IdProgrammeCard.id_number (models.CharField)` | `max_length=32` | field / model | `backend/apps/id_programmes/models.py:106` |
| `IdProgrammeCard.email_format (models.CharField)` | `max_length=3; default='pdf'` | field / model | `backend/apps/id_programmes/models.py:116` |
| `IdProgrammeImport.source_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/id_programmes/models.py:143` |
| `MAX_VALUE` | `500` | fixed / see setting | `backend/apps/id_programmes/prefill.py:19` |
| `MAX_QUESTIONS` | `12` | fixed / see setting | `backend/apps/id_programmes/questions.py:17` |
| `IdProgrammeCreateSerializer.name (serializers.CharField)` | `min_length=2, max_length=80` | field / model | `backend/apps/id_programmes/serializers.py:43` |
| `IdProgrammeCardCreateSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/id_programmes/serializers.py:80` |
| `IdProgrammeCardEditSerializer.name (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/id_programmes/serializers.py:86` |
| `DecisionSerializer.ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/id_programmes/serializers.py:92` |
| `DecisionSerializer.ids (serializers.ListField)` | `max_length=500` | field / model | `backend/apps/id_programmes/serializers.py:92` |
| `DecisionSerializer.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/id_programmes/serializers.py:94` |
| `JoinSerializer.photo_object_key (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/id_programmes/serializers.py:111` |
| `InviteAcceptSerializer.card (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/id_programmes/views_public.py:122` |
| `InviteAcceptSerializer.invite (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/id_programmes/views_public.py:123` |

</details>

<details>
<summary>integrations (270 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `BroadcastCampaign.status (models.CharField)` | `max_length=10; default=Status.DRAFT` | field / model | `backend/apps/integrations/broadcasts_models.py:22` |
| `BroadcastDelivery.status (models.CharField)` | `max_length=8; default='pending'` | field / model | `backend/apps/integrations/broadcasts_models.py:38` |
| `DeliveryFilters.event (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/delivery_serializers.py:12` |
| `DeliveryFilters.destination (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/integrations/delivery_serializers.py:13` |
| `RetrySerializer.generation (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/integrations/delivery_serializers.py:40` |
| `DeliveryTestSerializer.destination_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/integrations/delivery_serializers.py:44` |
| `SuppressionWriteSerializer.address (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/integrations/delivery_serializers.py:54` |
| `TOKEN_MAX_AGE` | `60 * 60 * 24 * 365` | fixed / see setting | `backend/apps/integrations/email_preferences.py:15` |
| `MAX_ATTEMPTS` | `6` | fixed / see setting | `backend/apps/integrations/fanout_jobs.py:34` |
| `MessagingSettingsSerializer.sms_from_number (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/messaging/serializers.py:21` |
| `MessagingSettingsSerializer.sms_auth_token (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/integrations/messaging/serializers.py:22` |
| `MessagingSettingsSerializer.whatsapp_access_token (serializers.CharField)` | `max_length=8192` | field / model | `backend/apps/integrations/messaging/serializers.py:25` |
| `MessagingSettingsSerializer.whatsapp_app_secret (serializers.CharField)` | `max_length=4096` | field / model | `backend/apps/integrations/messaging/serializers.py:26` |
| `ConsentWriteSerializer.makerspace (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/integrations/messaging/serializers.py:59` |
| `get.field (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/integrations/messaging/views_member.py:19` |
| `ChatTemplate.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_chat_templates.py:30` |
| `ChatTemplate.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_chat_templates.py:31` |
| `NotificationEnvelope.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_contract.py:12` |
| `NotificationEnvelope.stream (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_contract.py:13` |
| `NotificationEnvelope.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_contract.py:14` |
| `NotificationEnvelope.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_contract.py:15` |
| `NotificationEnvelope.subject_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_contract.py:18` |
| `NotificationEnvelope.source_kind (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_contract.py:24` |
| `NotificationEnvelope.source_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_contract.py:25` |
| `NotificationEnvelope.revision (models.CharField)` | `max_length=64; default='1'` | field / model | `backend/apps/integrations/models_contract.py:26` |
| `NotificationEnvelope.dedup_key (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_contract.py:27` |
| `NotificationEnvelope.timing_policy (models.CharField)` | `max_length=16; default='immediate'` | field / model | `backend/apps/integrations/models_contract.py:28` |
| `NotificationDelivery.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_contract.py:51` |
| `NotificationDelivery.target_key (models.CharField)` | `max_length=80` | field / model | `backend/apps/integrations/models_contract.py:54` |
| `NotificationDelivery.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_contract.py:55` |
| `NotificationDelivery.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_contract.py:57` |
| `NotificationDelivery.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_contract.py:58` |
| `NotificationDelivery.provider_source (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_contract.py:59` |
| `NotificationDelivery.recipient_phone_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_contract.py:61` |
| `NotificationDelivery.recipient_alias_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_contract.py:62` |
| `NotificationDelivery.state (models.CharField)` | `max_length=16; default=State.RETRYING` | field / model | `backend/apps/integrations/models_contract.py:72` |
| `NotificationDelivery.provider_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_contract.py:73` |
| `NotificationDelivery.last_error (models.CharField)` | `max_length=100` | field / model | `backend/apps/integrations/models_contract.py:77` |
| `NotificationCutover.route (models.CharField)` | `max_length=16; default='receipt_only'` | field / model | `backend/apps/integrations/models_cutover.py:13` |
| `NotificationIngress.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_cutover.py:34` |
| `NotificationIngress.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_cutover.py:35` |
| `NotificationIngress.transport (models.CharField)` | `max_length=24` | field / model | `backend/apps/integrations/models_cutover.py:36` |
| `NotificationIngress.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_cutover.py:37` |
| `NotificationIngress.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_cutover.py:40` |
| `NotificationIngress.dedupe_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_cutover.py:41` |
| `NotificationIngress.state (models.CharField)` | `max_length=16; default='pending'` | field / model | `backend/apps/integrations/models_cutover.py:45` |
| `NotificationIngress.last_error (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_cutover.py:49` |
| `NotificationLegacyMapping.legacy_model (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_cutover.py:64` |
| `NotificationLegacyMapping.canonical_model (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_cutover.py:66` |
| `NotificationLegacyMapping.disposition (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_cutover.py:69` |
| `NotificationCredentialVersion.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_cutover.py:83` |
| `NotificationCredentialVersion.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_cutover.py:84` |
| `NotificationCredentialVersion.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_cutover.py:85` |
| `NotificationProviderReference.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_cutover.py:99` |
| `NotificationProviderReference.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_cutover.py:100` |
| `NotificationProviderReference.provider_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_cutover.py:101` |
| `NotificationProviderReference.phone_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_cutover.py:102` |
| `NotificationDestination.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_destinations.py:52` |
| `NotificationDestination.label (models.CharField)` | `max_length=80` | field / model | `backend/apps/integrations/models_destinations.py:53` |
| `NotificationDestination.telegram_chat_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/integrations/models_destinations.py:57` |
| `EmailTemplate.stream (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:28` |
| `EmailTemplate.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:29` |
| `EmailTemplate.key (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_email.py:30` |
| `EmailTemplate.subject (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_email.py:36` |
| `PlatformEmailSettings.email_provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:72` |
| `PlatformEmailSettings.smtp_host (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_email.py:77` |
| `PlatformEmailSettings.smtp_username (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_email.py:79` |
| `PlatformEmailSettings.smtp_password (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_email.py:80` |
| `EmailLog.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_email.py:133` |
| `EmailLog.source_kind (models.CharField)` | `max_length=48` | field / model | `backend/apps/integrations/models_email.py:135` |
| `EmailLog.stream (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_email.py:141` |
| `EmailLog.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_email.py:142` |
| `EmailLog.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:143` |
| `EmailLog.provider_source (models.CharField)` | `max_length=8` | field / model | `backend/apps/integrations/models_email.py:144` |
| `EmailLog.provider_message_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_email.py:145` |
| `EmailLog.connection_kind (models.CharField)` | `max_length=16; default='makerspace'` | field / model | `backend/apps/integrations/models_email.py:148` |
| `EmailLog.status (models.CharField)` | `max_length=8; default=Status.PENDING` | field / model | `backend/apps/integrations/models_email.py:149` |
| `EmailLog.provider_name (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:160` |
| `EmailLog.provider_recipient_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_email.py:163` |
| `EmailLog.provider_delivery_status (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:164` |
| `EmailProviderWebhookReceipt.event_key (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_email.py:183` |
| `EmailNotificationMute.target (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_email.py:211` |
| `EmailNotificationMute.stream (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:212` |
| `EmailNotificationMute.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_email.py:213` |
| `EmailNotificationMute.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_email.py:214` |
| `ChannelConfiguration.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_endpoints.py:14` |
| `ChannelConfiguration.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_endpoints.py:19` |
| `ChannelConfiguration.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_endpoints.py:20` |
| `ChannelConfiguration.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_endpoints.py:23` |
| `NotificationEndpoint.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_endpoints.py:51` |
| `NotificationEndpoint.provider (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_endpoints.py:52` |
| `NotificationEndpoint.identity_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_endpoints.py:55` |
| `NotificationEndpoint.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_endpoints.py:57` |
| `NotificationEndpoint.verification_state (models.CharField)` | `max_length=16; default='verified'` | field / model | `backend/apps/integrations/models_endpoints.py:59` |
| `NotificationEndpoint.consent_version (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_endpoints.py:62` |
| `NotificationEndpointChallenge.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_endpoints.py:79` |
| `NotificationEndpointChallenge.code_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_endpoints.py:81` |
| `NotificationEndpointChallenge.consent_version (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_endpoints.py:86` |
| `WhatsAppTemplate.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_endpoints.py:93` |
| `WhatsAppTemplate.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_endpoints.py:94` |
| `WhatsAppTemplate.locale (models.CharField)` | `max_length=16; default='en'` | field / model | `backend/apps/integrations/models_endpoints.py:95` |
| `WhatsAppTemplate.template_name (models.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/models_endpoints.py:96` |
| `WhatsAppTemplate.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_endpoints.py:99` |
| `WhatsAppTemplate.provider_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_endpoints.py:100` |
| `PlatformLegalPage.slug (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_legal.py:16` |
| `PlatformLegalPage.language (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/integrations/models_legal.py:18` |
| `MachineTypeEmailTemplate.stream (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_machine_templates.py:21` |
| `MachineTypeEmailTemplate.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_machine_templates.py:22` |
| `MachineTypeEmailTemplate.key (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_machine_templates.py:23` |
| `MachineTypeEmailTemplate.subject (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_machine_templates.py:34` |
| `MessagingConsent.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_consent.py:25` |
| `MessagingConsent.action (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_consent.py:26` |
| `MessagingConsent.source (models.CharField)` | `max_length=24` | field / model | `backend/apps/integrations/models_messaging_consent.py:29` |
| `MessagingConsent.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_consent.py:30` |
| `MessagingSuppression.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_consent.py:57` |
| `MessagingSuppression.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_consent.py:58` |
| `MessagingSuppression.recipient_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_consent.py:59` |
| `MessagingSuppression.recipient_kind (models.CharField)` | `max_length=8; default='phone'` | field / model | `backend/apps/integrations/models_messaging_consent.py:60` |
| `MessagingSuppression.reason (models.CharField)` | `max_length=24` | field / model | `backend/apps/integrations/models_messaging_consent.py:62` |
| `MessagingRecipientAlias.channel (models.CharField)` | `max_length=16; default='whatsapp'` | field / model | `backend/apps/integrations/models_messaging_consent.py:74` |
| `MessagingRecipientAlias.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_consent.py:75` |
| `MessagingRecipientAlias.alias_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_consent.py:76` |
| `MessagingRecipientAlias.phone_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_consent.py:77` |
| `MessagingRecipientCorrelation.channel (models.CharField)` | `max_length=16; default='whatsapp'` | field / model | `backend/apps/integrations/models_messaging_consent.py:91` |
| `MessagingRecipientCorrelation.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_consent.py:92` |
| `MessagingRecipientCorrelation.phone_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_consent.py:93` |
| `MessagingRecipientCorrelation.state (models.CharField)` | `max_length=16; default=State.PROBING` | field / model | `backend/apps/integrations/models_messaging_consent.py:94` |
| `MessagingDelivery.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:43` |
| `MessagingDelivery.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:45` |
| `MessagingDelivery.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_messaging_delivery.py:46` |
| `MessagingDelivery.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:47` |
| `MessagingDelivery.event_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_delivery.py:48` |
| `MessagingDelivery.source_type (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:51` |
| `MessagingDelivery.source_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:52` |
| `MessagingDelivery.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_delivery.py:53` |
| `MessagingDelivery.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:54` |
| `MessagingDelivery.provider_source (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:55` |
| `MessagingDelivery.provider_message_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_delivery.py:56` |
| `MessagingDelivery.recipient_alias_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:57` |
| `MessagingDelivery.recipient_phone_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:59` |
| `MessagingDelivery.template_name (models.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/models_messaging_delivery.py:60` |
| `MessagingDelivery.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/integrations/models_messaging_delivery.py:64` |
| `MessagingDelivery.skip_reason (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:66` |
| `MessagingDelivery.error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_delivery.py:67` |
| `MessagingWebhookEvent.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:98` |
| `MessagingWebhookEvent.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:99` |
| `MessagingWebhookEvent.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_delivery.py:100` |
| `MessagingWebhookEvent.dedupe_id (models.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/models_messaging_delivery.py:101` |
| `MessagingWebhookEvent.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_delivery.py:102` |
| `MessagingWebhookEvent.state (models.CharField)` | `max_length=16; default=State.PENDING` | field / model | `backend/apps/integrations/models_messaging_delivery.py:104` |
| `PlatformWhatsAppSettings.app_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:33` |
| `PlatformWhatsAppSettings.phone_number_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:34` |
| `PlatformWhatsAppSettings.business_account_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:35` |
| `PlatformWhatsAppSettings.webhook_verify_token (models.CharField)` | `max_length=128; default=verify_token` | field / model | `backend/apps/integrations/models_messaging_settings.py:38` |
| `MakerspaceMessagingSettings.sms_account_sid (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:52` |
| `MakerspaceMessagingSettings.sms_from_number (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_messaging_settings.py:54` |
| `MakerspaceMessagingSettings.sms_sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_settings.py:55` |
| `MakerspaceMessagingSettings.whatsapp_phone_number_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:56` |
| `MakerspaceMessagingSettings.whatsapp_business_account_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:57` |
| `MakerspaceMessagingSettings.whatsapp_webhook_verify_token (models.CharField)` | `max_length=128; default=verify_token` | field / model | `backend/apps/integrations/models_messaging_settings.py:60` |
| `MakerspaceMessagingSettings.whatsapp_sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_settings.py:61` |
| `MessagingSenderIdentity.sender_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_messaging_settings.py:71` |
| `MessagingSenderIdentity.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_settings.py:72` |
| `MessagingSenderIdentity.owner (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_settings.py:73` |
| `MessagingSenderCredential.verify_token (models.CharField)` | `max_length=128` | field / model | `backend/apps/integrations/models_messaging_settings.py:84` |
| `WhatsAppTemplateBinding.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_messaging_settings.py:95` |
| `WhatsAppTemplateBinding.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:96` |
| `WhatsAppTemplateBinding.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_settings.py:97` |
| `WhatsAppTemplateBinding.business_account_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_messaging_settings.py:98` |
| `WhatsAppTemplateBinding.template_name (models.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/models_messaging_settings.py:99` |
| `WhatsAppTemplateBinding.language (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_messaging_settings.py:100` |
| `NotificationMediaGrant.source_revision (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_notification_media.py:10` |
| `NotificationMediaGrant.integration_identity (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_notification_media.py:13` |
| `NotificationMediaGrant.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_notification_media.py:14` |
| `NotificationPreference.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_notifications.py:21` |
| `NotificationPreference.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_notifications.py:22` |
| `NotificationDeliveryLog.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_notifications.py:57` |
| `NotificationDeliveryLog.destination_label (models.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/integrations/models_notifications.py:74` |
| `NotificationDeliveryLog.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_notifications.py:75` |
| `NotificationDeliveryLog.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_notifications.py:76` |
| `NotificationDeliveryLog.status (models.CharField)` | `max_length=8; default=NotificationDeliveryStatus.PENDING` | field / model | `backend/apps/integrations/models_notifications.py:79` |
| `DailyNotificationCounter.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_notifications.py:117` |
| `OrganizationEmailSender.sender_name (models.CharField)` | `max_length=80` | field / model | `backend/apps/integrations/models_org_sender.py:15` |
| `OrganizationEmailSender.reply_to (models.EmailField)` | `max_length=254` | field / model | `backend/apps/integrations/models_org_sender.py:16` |
| `PlatformPushSettings.apns_team_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/integrations/models_push.py:17` |
| `PlatformPushSettings.apns_key_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/integrations/models_push.py:18` |
| `PlatformPushSettings.apns_topic (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/integrations/models_push.py:19` |
| `PushDevice.token_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_push.py:61` |
| `PushDevice.provider (models.CharField)` | `max_length=8` | field / model | `backend/apps/integrations/models_push.py:62` |
| `PushDevice.environment (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_push.py:63` |
| `NotificationRecipient.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_recipients.py:45` |
| `NotificationRecipient.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_recipients.py:46` |
| `NotificationRecipient.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_recipients.py:47` |
| `PlatformSmsSettings.provider (models.CharField)` | `max_length=32; default=SmsProviderChoice.TWILIO` | field / model | `backend/apps/integrations/models_sms.py:22` |
| `PlatformSmsSettings.account_sid (models.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/models_sms.py:27` |
| `PlatformSmsSettings.auth_token (models.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/models_sms.py:28` |
| `PlatformSmsSettings.from_number (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_sms.py:29` |
| `PlatformSmsSettings.notifications_from_number (models.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/models_sms.py:31` |
| `EmailSuppression.address_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/models_suppression.py:16` |
| `EmailSuppression.reason (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_suppression.py:17` |
| `SmsSendLog.purpose (models.CharField)` | `max_length=32; default='authentication'` | field / model | `backend/apps/integrations/models_tracking.py:9` |
| `SmsSendLog.provider_source (models.CharField)` | `max_length=8; default='platform'` | field / model | `backend/apps/integrations/models_tracking.py:10` |
| `SmsSendLog.status (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_tracking.py:11` |
| `PushDeliveryAttempt.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_tracking.py:21` |
| `PushDeliveryAttempt.provider_source (models.CharField)` | `max_length=8; default='platform'` | field / model | `backend/apps/integrations/models_tracking.py:22` |
| `PushDeliveryAttempt.status (models.CharField)` | `max_length=8; default='pending'` | field / model | `backend/apps/integrations/models_tracking.py:23` |
| `PushDeliveryAttempt.last_error (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_tracking.py:28` |
| `EmailProviderEvent.event_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/models_tracking.py:39` |
| `EmailProviderEvent.reason (models.CharField)` | `max_length=16` | field / model | `backend/apps/integrations/models_tracking.py:40` |
| `TemplateSerializer.event (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/notification_api_serializers.py:25` |
| `TemplateSerializer.variables (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/notification_api_serializers.py:29` |
| `TemplateSerializer.variables (serializers.ListField)` | `max_length=30` | field / model | `backend/apps/integrations/notification_api_serializers.py:29` |
| `QuotaSerializer.daily_limit (serializers.IntegerField)` | `min_value=1, max_value=100000` | field / model | `backend/apps/integrations/notification_api_serializers.py:88` |
| `QuotaSerializer.recipient_daily_limit (serializers.IntegerField)` | `min_value=1, max_value=10000` | field / model | `backend/apps/integrations/notification_api_serializers.py:89` |
| `ChannelPatchSerializer.integration_identity (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/notification_api_serializers.py:101` |
| `ChannelPatchSerializer.credentials (serializers.CharField)` | `max_length=8000` | field / model | `backend/apps/integrations/notification_api_serializers.py:102` |
| `ChallengeStartSerializer.consent_version (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/notification_api_serializers.py:160` |
| `ProofVerifySerializer.code (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_api_serializers.py:181` |
| `ProofVerifySerializer.state (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/notification_api_serializers.py:182` |
| `SelectionSerializer.channels (serializers.ListField)` | `max_length=9` | field / model | `backend/apps/integrations/notification_api_serializers.py:188` |
| `ContractTestSerializer.event (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/integrations/notification_api_serializers.py:229` |
| `ContractTestSerializer.endpoint_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/integrations/notification_api_serializers.py:231` |
| `ContractTestSerializer.room_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/integrations/notification_api_serializers.py:232` |
| `MAX_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/integrations/notification_certificate_media.py:12` |
| `MAX_ATTEMPTS` | `4` | fixed / see setting | `backend/apps/integrations/notification_delivery.py:16` |
| `MAX_DOCUMENT_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/integrations/notification_document_transport.py:8` |
| `MAX_MESSAGE_LENGTH` | `{'telegram': 4096, 'slack': 40000, 'mattermost': 16383, 'discord': 2000, 'webhook': 100000}` | fixed / see setting | `backend/apps/integrations/notification_enums.py:78` |
| `OAuthCallbackSerializer.code (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_slack_installation.py:26` |
| `OAuthCallbackSerializer.state (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/integrations/notification_slack_installation.py:27` |
| `MattermostInstallationSerializer.server_url (serializers.URLField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_slack_installation.py:38` |
| `MattermostInstallationSerializer.bot_token (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_slack_installation.py:39` |
| `MattermostInstallationSerializer.client_id (serializers.RegexField)` | `max_length=26` | field / model | `backend/apps/integrations/notification_slack_installation.py:40` |
| `MattermostInstallationSerializer.client_secret (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_slack_installation.py:41` |
| `MattermostInstallationSerializer.webhook_token (serializers.CharField)` | `max_length=256` | field / model | `backend/apps/integrations/notification_slack_installation.py:42` |
| `DiscordInstallationSerializer.bot_token (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_slack_installation.py:52` |
| `DiscordInstallationSerializer.client_secret (serializers.CharField)` | `max_length=2048` | field / model | `backend/apps/integrations/notification_slack_installation.py:56` |
| `MAX_BODY` | `262144` | fixed / see setting | `backend/apps/integrations/notification_wa_meta_callbacks.py:19` |
| `MAX_ITEMS` | `200` | fixed / see setting | `backend/apps/integrations/notification_wa_meta_callbacks.py:20` |
| `MAX_RESPONSE` | `65536` | fixed / see setting | `backend/apps/integrations/notification_wa_twilio_http.py:16` |
| `ApprovalRequestSerializer.content_sids (serializers.ListField)` | `min_length=1, max_length=5` | field / model | `backend/apps/integrations/notification_wa_twilio_views.py:81` |
| `MAX_SKEW_SECONDS` | `300` | fixed / see setting | `backend/apps/integrations/notification_wa_window.py:6` |
| `OrganizationEmailSenderSerializer.sender_name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/integrations/org_sender_views.py:17` |
| `OrganizationEmailSenderSerializer.reply_to (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/integrations/org_sender_views.py:19` |
| `TITLE_LIMIT` | `40` | fixed / see setting | `backend/apps/integrations/push_payload.py:12` |
| `BODY_LIMIT` | `120` | fixed / see setting | `backend/apps/integrations/push_payload.py:13` |
| `SmsCredentialsUpdate.account_sid (_text)` | `max_length=255` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:27` |
| `SmsCredentialsUpdate.from_number (_text)` | `max_length=32` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:28` |
| `SmsCredentialsUpdate.notifications_from_number (_text)` | `max_length=32` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:30` |
| `SmsCredentialsUpdate.auth_token (_secret)` | `max_length=512` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:31` |
| `PushCredentialsUpdate.apns_team_id (_text)` | `max_length=64` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:36` |
| `PushCredentialsUpdate.apns_key_id (_text)` | `max_length=64` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:37` |
| `PushCredentialsUpdate.apns_topic (_text)` | `max_length=255` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:38` |
| `PushCredentialsUpdate.fcm_service_account (_secret)` | `max_length=20000` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:39` |
| `PushCredentialsUpdate.apns_private_key (_secret)` | `max_length=20000` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:41` |
| `WhatsAppCredentialsUpdate.app_id (_text)` | `max_length=64` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:47` |
| `WhatsAppCredentialsUpdate.phone_number_id (_text)` | `max_length=64` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:48` |
| `WhatsAppCredentialsUpdate.business_account_id (_text)` | `max_length=64` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:49` |
| `WhatsAppCredentialsUpdate.access_token (_secret)` | `max_length=8000` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:50` |
| `WhatsAppCredentialsUpdate.app_secret (_secret)` | `max_length=8000` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:52` |
| `AttestationCredentialsUpdate.app_display_name (_text)` | `max_length=100` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:57` |
| `AttestationCredentialsUpdate.play_integrity_service_account (_secret)` | `max_length=20000` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:58` |
| `SmsTestSerializer.to (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/integrations/serializers_platform_credentials.py:92` |
| `PushDeviceRegistrationSerializer.token (serializers.RegexField)` | `max_length=4096` | field / model | `backend/apps/integrations/serializers_push.py:7` |
| `TimingPolicySerializer.channels (serializers.ListField)` | `max_length=9` | field / model | `backend/apps/integrations/serializers_timing.py:8` |
| `TimingPolicySerializer.bounce_secret (serializers.CharField)` | `min_length=32, max_length=200` | field / model | `backend/apps/integrations/serializers_timing.py:13` |
| `BounceSerializer.event_id (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/integrations/views_bounce.py:27` |
| `BounceSerializer.message_id (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/integrations/views_bounce.py:28` |
| `BounceSerializer.address (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/integrations/views_bounce.py:29` |
| `MAX_GRACE_HOURS` | `168` | fixed / see setting | `backend/apps/integrations/webhook_secrets.py:17` |
| `_MAX_REDIRECTS` | `3` | fixed / see setting | `backend/apps/integrations/webhooks.py:24` |

</details>

<details>
<summary>inventory (57 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `NeedsFixQuantityForm.quantity (forms.IntegerField)` | `min_value=1` | field / model | `backend/apps/inventory/admin.py:40` |
| `KitLineInput.product_id (serializers.IntegerField)` | `min_value=1, max_value=SAFE_ID` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:7` |
| `KitLineInput.quantity_per_person (serializers.IntegerField)` | `min_value=1, max_value=99` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:8` |
| `KitCreateInput.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:13` |
| `KitCreateInput.lines (KitLineInput)` | `max_length=50` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:14` |
| `KitVersionInput.expected_revision (serializers.IntegerField)` | `min_value=1, max_value=SAFE_ID` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:18` |
| `KitPublicationInput.expected_revision (serializers.IntegerField)` | `min_value=1, max_value=SAFE_ID` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:22` |
| `KitArchiveInput.expected_revision (serializers.IntegerField)` | `min_value=1, max_value=SAFE_ID` | field / model | `backend/apps/inventory/equipment_kit_serializers.py:27` |
| `MAX_SAFE_REVISION` | `9007199254740991` | fixed / see setting | `backend/apps/inventory/equipment_kit_services.py:18` |
| `MAX_VERSION` | `2147483647` | fixed / see setting | `backend/apps/inventory/equipment_kit_services.py:19` |
| `MAX_SAFE_ID` | `9007199254740991` | fixed / see setting | `backend/apps/inventory/equipment_use_intent.py:11` |
| `KitComponentSerializer.label (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/kit_serializers.py:11` |
| `KitComponentSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=999` | field / model | `backend/apps/inventory/kit_serializers.py:12` |
| `KitDefinitionField.super().__init__` | `max_length=50` | field / model | `backend/apps/inventory/kit_serializers.py:22` |
| `KitCountSerializer.present (serializers.IntegerField)` | `min_value=0, max_value=2147483647` | field / model | `backend/apps/inventory/kit_serializers.py:36` |
| `KitCountsField.super().__init__` | `max_length=3550` | field / model | `backend/apps/inventory/kit_serializers.py:46` |
| `NONCE_MAX_LENGTH` | `128` | fixed / see setting | `backend/apps/inventory/middleware_nonce.py:9` |
| `Category.loan_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/inventory/models.py:25` |
| `Category.loan_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/inventory/models.py:25` |
| `Category.max_renewals (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/inventory/models.py:26` |
| `Category.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/inventory/models.py:32` |
| `Category.slug (models.SlugField)` | `max_length=120` | field / model | `backend/apps/inventory/models.py:33` |
| `Category.icon (models.CharField)` | `max_length=50` | field / model | `backend/apps/inventory/models.py:35` |
| `InventoryProduct.unit_cost (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/inventory/models.py:57` |
| `InventoryProduct.unit_cost (models.DecimalField)` | `max_digits=14` | field / model | `backend/apps/inventory/models.py:57` |
| `InventoryProduct.cost_currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/inventory/models.py:58` |
| `InventoryProduct.cost_unit (models.CharField)` | `max_length=16` | field / model | `backend/apps/inventory/models.py:59` |
| `InventoryProduct.borrowing_terms (models.TextField)` | `max_length=2000` | field / model | `backend/apps/inventory/models.py:60` |
| `InventoryProduct.loan_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/inventory/models.py:61` |
| `InventoryProduct.loan_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/inventory/models.py:61` |
| `InventoryProduct.max_renewals (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/inventory/models.py:62` |
| `InventoryProduct.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models.py:82` |
| `InventoryProduct.manufacturer (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models.py:83` |
| `InventoryProduct.model (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models.py:84` |
| `InventoryProduct.sku (models.CharField)` | `max_length=100` | field / model | `backend/apps/inventory/models.py:85` |
| `InventoryProduct.barcode (models.CharField)` | `max_length=100` | field / model | `backend/apps/inventory/models.py:86` |
| `InventoryProduct.supplier (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models.py:87` |
| `InventoryProduct.image_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/inventory/models.py:101` |
| `InventoryProduct.tracking_mode (models.CharField)` | `max_length=20; default=TrackingMode.QUANTITY` | field / model | `backend/apps/inventory/models.py:104` |
| `InventoryProduct.public_availability_mode (models.CharField)` | `max_length=20; default=PublicAvailabilityMode.STATUS_ONLY` | field / model | `backend/apps/inventory/models.py:121` |
| `InventoryProduct.storage_location (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models.py:126` |
| `InventoryProduct.deposit_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/inventory/models.py:129` |
| `InventoryAsset.asset_tag (models.CharField)` | `max_length=100` | field / model | `backend/apps/inventory/models.py:237` |
| `InventoryAsset.serial_number (models.CharField)` | `max_length=100` | field / model | `backend/apps/inventory/models.py:238` |
| `InventoryAsset.status (models.CharField)` | `max_length=20; default=Status.AVAILABLE` | field / model | `backend/apps/inventory/models.py:239` |
| `EquipmentKitTemplate.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models_equipment_proposals.py:14` |
| `EquipmentKitVersion.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/inventory/models_equipment_proposals.py:26` |
| `EquipmentProposalReceipt.payload_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/inventory/models_equipment_proposals.py:60` |
| `EquipmentProposalReceipt.outcome_kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/inventory/models_equipment_proposals.py:63` |
| `EquipmentConsumableUseReceipt.payload_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/inventory/models_equipment_proposals.py:96` |
| `UPCOMING_LIMIT` | `6` | fixed / see setting | `backend/apps/inventory/public_stats_events.py:14` |
| `ReorderDraftSerializer.product_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/inventory/reorder_views.py:29` |
| `MAX_QUERY_LENGTH` | `200` | fixed / see setting | `backend/apps/inventory/search.py:26` |
| `ConsumableUseSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=100000` | field / model | `backend/apps/inventory/views_consumables.py:39` |
| `ConsumableUseSerializer.note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/inventory/views_consumables.py:40` |
| `ConsumableUseSerializer.allocation_id (serializers.IntegerField)` | `min_value=1, max_value=9007199254740991` | field / model | `backend/apps/inventory/views_consumables.py:42` |
| `ConsumableUseSerializer.plan_id (serializers.IntegerField)` | `min_value=1, max_value=9007199254740991` | field / model | `backend/apps/inventory/views_consumables.py:43` |

</details>

<details>
<summary>machines (272 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_CHOICES` | `100` | fixed / see setting | `backend/apps/machines/consumable_profiles.py:59` |
| `MAX_QUANTITY` | `Decimal('1000000000')` | fixed / see setting | `backend/apps/machines/consumable_profiles.py:60` |
| `MAX_ENTRIES` | `32` | fixed / see setting | `backend/apps/machines/consumable_usage.py:26` |
| `NO_SHOW_LIMIT` | `3` | fixed / see setting | `backend/apps/machines/job_policy.py:22` |
| `MAX_AUTO_REQUEUES` | `2` | fixed / see setting | `backend/apps/machines/job_policy.py:23` |
| `schedules_annotation.decimal (DecimalField)` | `max_digits=20` | field / model | `backend/apps/machines/lockout_batch.py:37` |
| `MachineAccessGrant.source (models.CharField)` | `max_length=12; default=Source.STAFF` | field / model | `backend/apps/machines/models_access_grants.py:35` |
| `MachineType.slug (models.SlugField)` | `max_length=50` | field / model | `backend/apps/machines/models_catalog.py:32` |
| `MachineType.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_catalog.py:33` |
| `MachineType.icon (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_catalog.py:34` |
| `MachineType.managing_action (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/machines/models_catalog.py:39` |
| `MakerspaceMachineTypePricing.rate_per_unit (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/machines/models_catalog.py:80` |
| `MakerspaceMachineTypePricing.flat_fee (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/machines/models_catalog.py:81` |
| `Machine.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_catalog.py:121` |
| `Machine.location (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_catalog.py:122` |
| `Machine.status (models.CharField)` | `max_length=20; default=Status.IDLE` | field / model | `backend/apps/machines/models_catalog.py:124` |
| `Machine.firmware_version (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_catalog.py:127` |
| `Machine.image_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/machines/models_catalog.py:129` |
| `MachineOperator.access_level (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_catalog.py:181` |
| `CertificationType.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_certifications.py:41` |
| `MachineTypeConsumable.key (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:27` |
| `MachineTypeConsumable.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_consumable_profiles.py:28` |
| `MachineTypeConsumable.kind (models.CharField)` | `max_length=12; default=Kind.MATERIAL` | field / model | `backend/apps/machines/models_consumable_profiles.py:29` |
| `MachineTypeConsumable.unit (models.CharField)` | `max_length=12` | field / model | `backend/apps/machines/models_consumable_profiles.py:30` |
| `MachineTypeConsumable.estimate_by (models.CharField)` | `max_length=8; default=EstimateBy.NONE` | field / model | `backend/apps/machines/models_consumable_profiles.py:34` |
| `MachineTypeConsumable.unit_price (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/machines/models_consumable_profiles.py:37` |
| `MachineTypeConsumable.unit_price (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/machines/models_consumable_profiles.py:38` |
| `MachineTypeConsumable.template_key (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:46` |
| `ServiceRequestConsumableUsage.key (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:83` |
| `ServiceRequestConsumableUsage.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_consumable_profiles.py:84` |
| `ServiceRequestConsumableUsage.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/machines/models_consumable_profiles.py:85` |
| `ServiceRequestConsumableUsage.unit (models.CharField)` | `max_length=12` | field / model | `backend/apps/machines/models_consumable_profiles.py:86` |
| `ServiceRequestConsumableUsage.phase (models.CharField)` | `max_length=8` | field / model | `backend/apps/machines/models_consumable_profiles.py:87` |
| `ServiceRequestConsumableUsage.quantity (models.DecimalField)` | `max_digits=16` | field / model | `backend/apps/machines/models_consumable_profiles.py:88` |
| `ServiceRequestConsumableUsage.source (models.CharField)` | `max_length=8` | field / model | `backend/apps/machines/models_consumable_profiles.py:90` |
| `ServiceRequestConsumableUsage.unit_price (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/machines/models_consumable_profiles.py:91` |
| `ServiceRequestConsumableUsage.device_ref (models.CharField)` | `max_length=36` | field / model | `backend/apps/machines/models_consumable_profiles.py:93` |
| `MachineTypeTemplate.key (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:120` |
| `MachineTypeTemplate.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_consumable_profiles.py:121` |
| `MachineTypeTemplate.description (models.CharField)` | `max_length=500` | field / model | `backend/apps/machines/models_consumable_profiles.py:122` |
| `MachineTypeTemplate.category (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:123` |
| `MachineTypeTemplate.icon (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:124` |
| `MachineTypeTemplate.based_on (models.CharField)` | `max_length=50` | field / model | `backend/apps/machines/models_consumable_profiles.py:126` |
| `MachineDowntime.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_downtime.py:22` |
| `MachineDowntime.reason (models.CharField)` | `max_length=300` | field / model | `backend/apps/machines/models_downtime.py:23` |
| `MachineJobBatch.note (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_job_batch.py:17` |
| `JobFlowFields.urgent_reason (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_job_fields.py:17` |
| `JobFlowFields.material_note (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_job_fields.py:26` |
| `JobFlowFields.changes_code (models.CharField)` | `max_length=32` | field / model | `backend/apps/machines/models_job_fields.py:30` |
| `JobFlowFields.reject_code (models.CharField)` | `max_length=32` | field / model | `backend/apps/machines/models_job_fields.py:33` |
| `JobFlowFields.quote_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/machines/models_job_fields.py:36` |
| `JobFlowFields.fail_code (models.CharField)` | `max_length=32` | field / model | `backend/apps/machines/models_job_fields.py:43` |
| `JobFlowFields.fail_fault (models.CharField)` | `max_length=8` | field / model | `backend/apps/machines/models_job_fields.py:44` |
| `JobFlowFields.failure_outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_job_fields.py:45` |
| `JobFlowFields.pickup_code (models.CharField)` | `max_length=8` | field / model | `backend/apps/machines/models_job_fields.py:48` |
| `JobFlowFields.pickup_location (models.CharField)` | `max_length=120` | field / model | `backend/apps/machines/models_job_fields.py:49` |
| `MachineMaterial.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_materials.py:17` |
| `MakerspaceMachineTypePolicy.quote_mode (models.CharField)` | `max_length=8; default=QuoteMode.AUTO` | field / model | `backend/apps/machines/models_policy.py:39` |
| `MakerspaceMachineTypePolicy.quote_above_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/machines/models_policy.py:40` |
| `MakerspaceMachineTypePolicy.payment_timing (models.CharField)` | `max_length=12; default=PaymentTiming.COMPLETION` | field / model | `backend/apps/machines/models_policy.py:41` |
| `MakerspaceMachineTypePolicy.member_fault_charge (models.CharField)` | `max_length=16; default=FailureCharge.NONE` | field / model | `backend/apps/machines/models_policy.py:44` |
| `MachineConsumablePool.unit_cost (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/machines/models_service_consumables.py:23` |
| `MachineConsumablePool.unit_cost (models.DecimalField)` | `max_digits=14` | field / model | `backend/apps/machines/models_service_consumables.py:23` |
| `MachineConsumablePool.cost_currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/machines/models_service_consumables.py:24` |
| `MachineConsumablePool.cost_unit (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_service_consumables.py:25` |
| `MachineConsumablePool.material (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_service_consumables.py:26` |
| `MachineConsumablePool.color (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_service_consumables.py:27` |
| `MachineConsumablePool.color_hex (models.CharField)` | `max_length=7; default=''` | field / model | `backend/apps/machines/models_service_consumables.py:28` |
| `MachineConsumablePool.brand (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_service_consumables.py:29` |
| `MachineConsumablePool.unit (models.CharField)` | `max_length=12; default=ConsumablePoolUnit.GRAMS` | field / model | `backend/apps/machines/models_service_consumables.py:30` |
| `MachineConsumablePool.lot_code (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_service_consumables.py:31` |
| `MachineConsumablePool.initial_grams (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_consumables.py:32` |
| `MachineConsumablePool.remaining_grams (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_consumables.py:33` |
| `MachineConsumablePool.low_threshold_grams (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_consumables.py:34` |
| `MachineConsumableAdjustment.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_service_consumables.py:93` |
| `MachineConsumableAdjustment.quantity_delta (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_consumables.py:94` |
| `MachineConsumableAdjustment.metering_unit (models.CharField)` | `max_length=12; default=MeteringUnit.WEIGHT` | field / model | `backend/apps/machines/models_service_consumables.py:95` |
| `MachineConsumableAdjustment.consumed_quantity (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_service_consumables.py:96` |
| `ServiceRequestConsumption.measurement (models.CharField)` | `max_length=10` | field / model | `backend/apps/machines/models_service_consumables.py:143` |
| `ServiceRequestConsumption.label (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_service_consumables.py:145` |
| `ServiceRequestConsumption.quantity (MinValueValidator)` | `min_value=0.01` | field / model | `backend/apps/machines/models_service_consumables.py:146` |
| `ServiceRequestConsumption.quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_consumables.py:146` |
| `ServiceRequestConsumption.outcome (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_service_consumables.py:149` |
| `ServiceRequestFile.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_service_files.py:22` |
| `ServiceRequestFile.object_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_service_files.py:23` |
| `ServiceRequestFile.content_type (models.CharField)` | `max_length=128` | field / model | `backend/apps/machines/models_service_files.py:24` |
| `ServiceRequestFile.original_filename (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/machines/models_service_files.py:25` |
| `ServiceRequestFile.file_policy_name (models.CharField)` | `max_length=64; default='documents'` | field / model | `backend/apps/machines/models_service_files.py:28` |
| `ServiceQueue.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_service_requests.py:31` |
| `ServiceQueue.allocation_policy (models.CharField)` | `max_length=24; default=AllocationPolicy.STAFF_SELECT` | field / model | `backend/apps/machines/models_service_requests.py:35` |
| `ServiceBucket.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_service_requests.py:60` |
| `MachineServiceRequest.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_service_requests.py:150` |
| `MachineServiceRequest.status (models.CharField)` | `max_length=32; default=Status.PENDING` | field / model | `backend/apps/machines/models_service_requests.py:153` |
| `MachineServiceRequest.estimated_minutes (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/machines/models_service_requests.py:175` |
| `MachineServiceRequest.actual_minutes (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/machines/models_service_requests.py:176` |
| `MachineServiceRequest.fail_percent_complete (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/machines/models_service_requests.py:177` |
| `MachineServiceRequest.fail_percent_complete (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/machines/models_service_requests.py:177` |
| `MachineServiceRequest.planned_grams (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_service_requests.py:179` |
| `MachineServiceRequest.reserved_grams (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_service_requests.py:180` |
| `MachineServiceRequest.actual_consumed_grams (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_service_requests.py:181` |
| `MachineServiceRequest.metering_unit (models.CharField)` | `max_length=12` | field / model | `backend/apps/machines/models_service_requests.py:182` |
| `MachineServiceRequest.planned_quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_requests.py:183` |
| `MachineServiceRequest.reserved_quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_requests.py:184` |
| `MachineServiceRequest.actual_consumed_quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_service_requests.py:185` |
| `MachineServiceRequest.payment_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/machines/models_service_requests.py:190` |
| `MachineServiceRequest.payment_status (models.CharField)` | `max_length=16; default='none'` | field / model | `backend/apps/machines/models_service_requests.py:191` |
| `MachineServiceRequest.run_machine_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_service_requests.py:193` |
| `MachineServiceRequest.run_machine_model (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_service_requests.py:194` |
| `MachineServiceRequest.run_consumable_label (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_service_requests.py:195` |
| `MachineServiceRequest.run_consumable_material (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_service_requests.py:196` |
| `MachineServiceRequest.run_consumable_color (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_service_requests.py:197` |
| `MachineServiceRequest.run_planned_grams (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_service_requests.py:199` |
| `MAX_LENGTH` | `('max_length', gettext_noop('Reached the maximum length'))` | fixed / see setting | `backend/apps/machines/models_sessions.py:27` |
| `MachineSession.source (models.CharField)` | `max_length=12` | field / model | `backend/apps/machines/models_sessions.py:43` |
| `MachineSession.stop_reason (models.CharField)` | `max_length=12` | field / model | `backend/apps/machines/models_sessions.py:46` |
| `MachineSession.quote_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/machines/models_sessions.py:52` |
| `MachineSession.device_job_ref (models.CharField)` | `max_length=64` | field / model | `backend/apps/machines/models_sessions.py:56` |
| `MachineSessionAmendment.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/machines/models_sessions.py:101` |
| `MachineSessionAmendment.reason (models.CharField)` | `max_length=500` | field / model | `backend/apps/machines/models_sessions.py:105` |
| `SupervisedSession.note (models.CharField)` | `max_length=300` | field / model | `backend/apps/machines/models_supervised.py:20` |
| `SupervisedUse.note (models.CharField)` | `max_length=300` | field / model | `backend/apps/machines/models_supervised.py:65` |
| `MachineStatusEvent.from_status (models.CharField)` | `max_length=20` | field / model | `backend/apps/machines/models_tracking.py:33` |
| `MachineStatusEvent.to_status (models.CharField)` | `max_length=20` | field / model | `backend/apps/machines/models_tracking.py:34` |
| `MachineStatusEvent.source (models.CharField)` | `max_length=32` | field / model | `backend/apps/machines/models_tracking.py:36` |
| `ConsumableCostRecord.source_kind (models.CharField)` | `max_length=32` | field / model | `backend/apps/machines/models_tracking.py:50` |
| `ConsumableCostRecord.quantity (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_tracking.py:54` |
| `ConsumableCostRecord.measurement_unit (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_tracking.py:55` |
| `ConsumableCostRecord.unit_price_minor_per_measurement_unit (models.DecimalField)` | `max_digits=24` | field / model | `backend/apps/machines/models_tracking.py:56` |
| `ConsumableCostRecord.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/machines/models_tracking.py:58` |
| `MachineTypeSetup.booking_slot_minutes (MaxValueValidator)` | `max_value=1440` | field / model | `backend/apps/machines/models_type_setup.py:29` |
| `MachineTypeSetup.booking_slot_minutes (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/machines/models_type_setup.py:29` |
| `MachineTypeSetup.booking_buffer_before_minutes (MaxValueValidator)` | `max_value=1440` | field / model | `backend/apps/machines/models_type_setup.py:31` |
| `MachineTypeSetup.booking_buffer_after_minutes (MaxValueValidator)` | `max_value=1440` | field / model | `backend/apps/machines/models_type_setup.py:33` |
| `MachineTypeSetup.booking_approval_mode (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/machines/models_type_setup.py:34` |
| `MachineTypeDocument.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_type_setup.py:50` |
| `MachineTypeDocument.object_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_type_setup.py:51` |
| `MachineTypeDocument.original_filename (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_type_setup.py:52` |
| `MachineTypeDocument.content_type (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_type_setup.py:53` |
| `MachineUsageEntry.hours (models.DecimalField)` | `max_digits=10; default=0` | field / model | `backend/apps/machines/models_usage.py:34` |
| `MachineUsageEntry.source (models.CharField)` | `max_length=16; default=Source.MANUAL` | field / model | `backend/apps/machines/models_usage.py:35` |
| `MachineUsageEntry.note (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_usage.py:38` |
| `MachineUsageEntry.outcome (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/machines/models_usage.py:48` |
| `MachineUsageEntry.consumed_grams (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_usage.py:51` |
| `MachineUsageEntry.metering_unit (models.CharField)` | `max_length=12; default=MeteringUnit.WEIGHT` | field / model | `backend/apps/machines/models_usage.py:52` |
| `MachineUsageEntry.consumed_quantity (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_usage.py:53` |
| `MachineUsageEntry.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_usage.py:58` |
| `MachineDocument.doc_type (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_usage.py:131` |
| `MachineDocument.object_key (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_usage.py:132` |
| `MachineDocument.original_filename (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_usage.py:133` |
| `MachineDocument.content_type (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/models_usage.py:134` |
| `MachineErrorLog.severity (models.CharField)` | `max_length=16` | field / model | `backend/apps/machines/models_usage.py:164` |
| `MachineConsumable.measurement (models.CharField)` | `max_length=10` | field / model | `backend/apps/machines/models_usage.py:190` |
| `MachineConsumable.label (models.CharField)` | `max_length=200` | field / model | `backend/apps/machines/models_usage.py:198` |
| `MachineConsumable.remaining (models.DecimalField)` | `max_digits=12; default=0` | field / model | `backend/apps/machines/models_usage.py:199` |
| `MachineConsumable.low_threshold (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/models_usage.py:200` |
| `MachineConsumable.note (models.CharField)` | `max_length=255` | field / model | `backend/apps/machines/models_usage.py:203` |
| `PrintingCutoverRepair.kind (models.CharField)` | `max_length=32` | field / model | `backend/apps/machines/printing_cutover_models.py:40` |
| `PrintingCutoverRepair.legacy_model (models.CharField)` | `max_length=100` | field / model | `backend/apps/machines/printing_cutover_models.py:41` |
| `PublicPrinterUploadSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/public_printer_service_serializers.py:25` |
| `PublicPrinterUploadSerializer.content_type (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/machines/public_printer_service_serializers.py:26` |
| `PublicPrinterSubmitSerializer.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/machines/public_printer_service_serializers.py:30` |
| `PublicPrinterSubmitSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/machines/public_printer_service_serializers.py:33` |
| `PublicPrinterSubmitSerializer.material (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/public_printer_service_serializers.py:36` |
| `PublicPrinterSubmitSerializer.color (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/public_printer_service_serializers.py:37` |
| `PublicPrinterSubmitSerializer.estimated_filament_grams (serializers.DecimalField)` | `max_digits=8, min_value=0` | field / model | `backend/apps/machines/public_printer_service_serializers.py:39` |
| `PublicPrinterSubmitSerializer.quantity (serializers.IntegerField)` | `min_value=1; default=1` | field / model | `backend/apps/machines/public_printer_service_serializers.py:40` |
| `PublicPrinterSubmitSerializer.source_link (serializers.URLField)` | `max_length=200` | field / model | `backend/apps/machines/public_printer_service_serializers.py:41` |
| `PublicMachineServiceSubmitSerializer.certification_override_reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/machines/public_service_serializers.py:7` |
| `PublicMachineServiceSubmitSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/public_service_serializers.py:9` |
| `PublicMachineServiceSubmitSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/machines/public_service_serializers.py:10` |
| `PublicMachineServiceSubmitSerializer.source_link (serializers.URLField)` | `max_length=200` | field / model | `backend/apps/machines/public_service_serializers.py:12` |
| `SetStatusSerializer.status (serializers.CharField)` | `max_length=20` | field / model | `backend/apps/machines/serializers_actions.py:14` |
| `SetStatusSerializer.reason (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/machines/serializers_actions.py:16` |
| `LogUsageSerializer.member (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_actions.py:25` |
| `LogUsageSerializer.hours (serializers.DecimalField)` | `max_digits=10, min_value=Decimal('0.01')` | field / model | `backend/apps/machines/serializers_actions.py:27` |
| `LogUsageSerializer.note (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/serializers_actions.py:32` |
| `AssignOperatorSerializer.access_level (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/machines/serializers_actions.py:37` |
| `LogErrorSerializer.severity (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/machines/serializers_actions.py:41` |
| `DocumentPresignSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/serializers_actions.py:46` |
| `DocumentPresignSerializer.content_type (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/serializers_actions.py:47` |
| `DocumentFinalizeSerializer.object_key (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/serializers_actions.py:51` |
| `DocumentFinalizeSerializer.doc_type (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/machines/serializers_actions.py:52` |
| `DocumentFinalizeSerializer.original_filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/serializers_actions.py:53` |
| `ConsumableEntrySerializer.quantity (serializers.DecimalField)` | `max_digits=16, min_value=Decimal('0.001')` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:18` |
| `ConsumableEntrySerializer.attributes (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:19` |
| `ConsumableDefinitionSerializer.record_by (serializers.ListField)` | `min_length=1, max_length=3` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:23` |
| `ConsumableDefinitionSerializer.attributes (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:24` |
| `MemberReportableConsumableSerializer.recorded_quantity (serializers.DecimalField)` | `max_digits=16` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:73` |
| `RecordConsumablesSerializer.entries (ConsumableEntrySerializer)` | `max_length=32` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:92` |
| `MachineTypeTemplateSerializer.name (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:98` |
| `MachineTypeTemplateSerializer.description (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:99` |
| `MachineTypeTemplateSerializer.category (serializers.CharField)` | `max_length=50; default=''` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:100` |
| `MachineTypeTemplateSerializer.icon (serializers.CharField)` | `max_length=50; default=''` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:101` |
| `ApplyMachineTypeTemplateSerializer.machine_type_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:110` |
| `ApplyMachineTypeTemplateSerializer.name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:111` |
| `ApplyMachineTypeTemplateSerializer.slug (serializers.CharField)` | `max_length=50; default=''` | field / model | `backend/apps/machines/serializers_consumable_profiles.py:112` |
| `MachineConsumableSerializer.serializers.DecimalField` | `max_digits=12` | field / model | `backend/apps/machines/serializers_consumables.py:40` |
| `LinkMachineConsumableSerializer.label (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/machines/serializers_consumables.py:54` |
| `LinkMachineConsumableSerializer.remaining (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/machines/serializers_consumables.py:55` |
| `LinkMachineConsumableSerializer.low_threshold (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/machines/serializers_consumables.py:58` |
| `LinkMachineConsumableSerializer.note (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/serializers_consumables.py:65` |
| `LogMachineConsumptionSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/machines/serializers_consumables.py:69` |
| `JobSubmitSerializer.queue_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_jobs.py:53` |
| `JobSubmitSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/machines/serializers_jobs.py:54` |
| `JobSubmitSerializer.description (serializers.CharField)` | `max_length=4000; default=''` | field / model | `backend/apps/machines/serializers_jobs.py:55` |
| `JobSubmitSerializer.file_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_jobs.py:57` |
| `JobSubmitSerializer.file_ids (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/machines/serializers_jobs.py:57` |
| `JobSubmitSerializer.copies (serializers.IntegerField)` | `min_value=1, max_value=999; default=1` | field / model | `backend/apps/machines/serializers_jobs.py:58` |
| `JobSubmitSerializer.material_note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/machines/serializers_jobs.py:61` |
| `JobSubmitSerializer.member_estimate_minutes (serializers.IntegerField)` | `min_value=1, max_value=100000; default=None` | field / model | `backend/apps/machines/serializers_jobs.py:62` |
| `JobSubmitSerializer.material (serializers.CharField)` | `max_length=100; default=''` | field / model | `backend/apps/machines/serializers_jobs.py:65` |
| `JobSubmitSerializer.color (serializers.CharField)` | `max_length=100; default=''` | field / model | `backend/apps/machines/serializers_jobs.py:66` |
| `JobSubmitSerializer.consumable_pool_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/machines/serializers_jobs.py:67` |
| `JobSubmitSerializer.estimated_filament_grams (serializers.DecimalField)` | `max_digits=10, min_value=0; default=None` | field / model | `backend/apps/machines/serializers_jobs.py:68` |
| `JobSubmitSerializer.consumable_estimates (serializers.ListField)` | `max_length=32; default=list` | field / model | `backend/apps/machines/serializers_jobs.py:73` |
| `JobSubmitSerializer.event_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/machines/serializers_jobs.py:75` |
| `JobUploadSerializer.queue_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_jobs.py:80` |
| `JobUploadSerializer.filename (serializers.CharField)` | `max_length=240` | field / model | `backend/apps/machines/serializers_jobs.py:81` |
| `JobUploadSerializer.content_type (serializers.CharField)` | `max_length=128` | field / model | `backend/apps/machines/serializers_jobs.py:82` |
| `SessionStartSerializer.digest (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/machines/serializers_sessions.py:168` |
| `SessionStartSerializer.event_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/machines/serializers_sessions.py:169` |
| `StaffSessionStartSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_sessions.py:174` |
| `StaffSessionStartSerializer.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_sessions.py:175` |
| `StaffSessionStartSerializer.event_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/machines/serializers_sessions.py:176` |
| `SessionAmendSerializer.minutes (serializers.IntegerField)` | `min_value=0, max_value=24 * 60` | field / model | `backend/apps/machines/serializers_sessions.py:181` |
| `SessionAmendSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/machines/serializers_sessions.py:182` |
| `SessionAssignSerializer.member_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/serializers_sessions.py:186` |
| `SessionAssignSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/machines/serializers_sessions.py:187` |
| `SessionSettingsSerializer.session_max_minutes (serializers.IntegerField)` | `min_value=5, max_value=24 * 60` | field / model | `backend/apps/machines/serializers_sessions.py:191` |
| `InductionGrantSerializer.user_ids (serializers.ListField)` | `max_length=500` | field / model | `backend/apps/machines/serializers_workshop.py:40` |
| `SupervisedSessionOpenSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/machines/serializers_workshop.py:64` |
| `SupervisedUseStartSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/machines/serializers_workshop.py:73` |
| `ServiceRequestEtaSerializer.start_in_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:19` |
| `ServiceRequestEtaSerializer.finish_in_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:20` |
| `ServiceRequestEtaSerializer.approved_ahead (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:23` |
| `ServiceRequestEtaSerializer.awaiting_review_ahead (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:24` |
| `ServiceRequestEtaSerializer.active_machine_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:25` |
| `ServiceRequestEtaSerializer.missing_estimate_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:26` |
| `MachineQueueSummarySerializer.length (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:32` |
| `MachineQueueSummarySerializer.eta_minutes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/machines/service_queue_eta_serializers.py:33` |
| `build_printer_service_report.rows (DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports.py:113` |
| `build_printer_service_report.manual_hours (DecimalField)` | `max_digits=10` | field / model | `backend/apps/machines/service_reports.py:130` |
| `_consumption_rows.rows (DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports.py:229` |
| `_consumption_rows.rows (DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports.py:230` |
| `MachineServiceConsumptionSerializer.completed_amount (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports_serializers.py:40` |
| `MachineServiceConsumptionSerializer.failed_partial_amount (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports_serializers.py:41` |
| `MachineServiceConsumptionSerializer.total_used (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports_serializers.py:42` |
| `MachineServiceFailureSerializer.failed_count_amount (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports_serializers.py:52` |
| `MachineServiceFailureSerializer.failed_grams_amount (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports_serializers.py:53` |
| `PrinterServiceReportRowSerializer.consumed_grams (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/service_reports_serializers.py:69` |
| `PrinterServiceReportRowSerializer.payment_due (MoneyField)` | `max_digits=13` | field / model | `backend/apps/machines/service_reports_serializers.py:70` |
| `PrinterServiceReportRowSerializer.payment_paid (MoneyField)` | `max_digits=13` | field / model | `backend/apps/machines/service_reports_serializers.py:71` |
| `MAX_CONSUMABLES` | `30` | fixed / see setting | `backend/apps/machines/template_spec.py:28` |
| `MAX_NOTES` | `10000` | fixed / see setting | `backend/apps/machines/type_setup.py:19` |
| `ConsumableStockPoolSerializer.remaining (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/views_consumable_stock.py:24` |
| `ApproveQuoteSerializer.digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/machines/views_jobs_member.py:18` |
| `ResubmitSerializer.note (serializers.CharField)` | `max_length=4000; default=''` | field / model | `backend/apps/machines/views_jobs_member.py:23` |
| `ResubmitSerializer.file_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/machines/views_jobs_member.py:24` |
| `ResubmitSerializer.file_ids (serializers.ListField)` | `max_length=20; default=list` | field / model | `backend/apps/machines/views_jobs_member.py:24` |
| `get_queryset.queryset (DecimalField)` | `max_digits=12` | field / model | `backend/apps/machines/views_public.py:70` |
| `MemberServiceCancelSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/machines/views_service_cancel.py:43` |
| `MemberServiceCancelSerializer.consumed_quantity (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0')` | field / model | `backend/apps/machines/views_service_cancel.py:44` |
| `MAX_RESULTS` | `20` | fixed / see setting | `backend/apps/machines/views_supervised_people.py:22` |
| `MachineTypeSetupSerializer.booking_slot_minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/machines/views_type_setup.py:20` |
| `MachineTypeSetupSerializer.booking_buffer_before_minutes (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/machines/views_type_setup.py:21` |
| `MachineTypeSetupSerializer.booking_buffer_after_minutes (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/machines/views_type_setup.py:23` |
| `MachineTypeSetupSerializer.training_notes (serializers.CharField)` | `max_length=type_setup.MAX_NOTES` | field / model | `backend/apps/machines/views_type_setup.py:25` |
| `TypeDocumentPresignSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/views_type_setup.py:40` |
| `TypeDocumentPresignSerializer.content_type (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/machines/views_type_setup.py:41` |
| `TypeDocumentAttachSerializer.object_key (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/views_type_setup.py:50` |
| `TypeDocumentAttachSerializer.title (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/machines/views_type_setup.py:51` |
| `TypeDocumentAttachSerializer.original_filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/machines/views_type_setup.py:52` |

</details>

<details>
<summary>maintenance (136 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `Incident.kind (models.CharField)` | `max_length=10; default=Kind.INCIDENT` | field / model | `backend/apps/maintenance/incidents/models.py:49` |
| `Incident.severity (models.CharField)` | `max_length=10; default=Severity.LOW` | field / model | `backend/apps/maintenance/incidents/models.py:50` |
| `Incident.status (models.CharField)` | `max_length=12; default=Status.REPORTED` | field / model | `backend/apps/maintenance/incidents/models.py:51` |
| `Incident.area (models.CharField)` | `max_length=10; default=Area.OTHER` | field / model | `backend/apps/maintenance/incidents/models.py:52` |
| `Incident.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/incidents/models.py:53` |
| `Incident.location (models.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/incidents/models.py:55` |
| `IncidentAction.description (models.CharField)` | `max_length=300` | field / model | `backend/apps/maintenance/incidents/models.py:101` |
| `MemberIncidentReportSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/incidents/serializers.py:81` |
| `MemberIncidentReportSerializer.description (serializers.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/maintenance/incidents/serializers.py:82` |
| `MemberIncidentReportSerializer.location (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/maintenance/incidents/serializers.py:83` |
| `StaffIncidentCreateSerializer.involved_note (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/incidents/serializers.py:90` |
| `StaffIncidentCreateSerializer.guest_pass_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/incidents/serializers.py:93` |
| `StaffIncidentUpdateSerializer.resolution_note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/maintenance/incidents/serializers.py:98` |
| `IncidentActionCreateSerializer.description (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/maintenance/incidents/serializers.py:103` |
| `due_queryset.queryset (DecimalField)` | `max_digits=12` | field / model | `backend/apps/maintenance/meters.py:56` |
| `due_queryset.queryset (DecimalField)` | `max_digits=12` | field / model | `backend/apps/maintenance/meters.py:57` |
| `MaintenanceSchedule.trigger (models.CharField)` | `max_length=8; default='days'` | field / model | `backend/apps/maintenance/models.py:17` |
| `MaintenanceSchedule.usage_hours (models.DecimalField)` | `max_digits=12` | field / model | `backend/apps/maintenance/models.py:18` |
| `MaintenanceSchedule.anchor (models.CharField)` | `max_length=16; default=Anchor.COMPLETION` | field / model | `backend/apps/maintenance/models.py:25` |
| `MaintenanceLog.cost (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/maintenance/models.py:81` |
| `MaintenanceLogDocument.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/maintenance/models.py:120` |
| `MaintenanceCalendarFeed.token_digest (models.BinaryField)` | `max_length=32` | field / model | `backend/apps/maintenance/models_feed.py:8` |
| `MaintenanceCalendarFeed.token_hint (models.CharField)` | `max_length=8` | field / model | `backend/apps/maintenance/models_feed.py:9` |
| `WorkOrder.subject_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/maintenance/models_work_orders.py:42` |
| `WorkOrder.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/models_work_orders.py:53` |
| `WorkOrder.priority (models.CharField)` | `max_length=8; default=Priority.NORMAL` | field / model | `backend/apps/maintenance/models_work_orders.py:55` |
| `WorkOrder.status (models.CharField)` | `max_length=12; default=Status.OPEN` | field / model | `backend/apps/maintenance/models_work_orders.py:56` |
| `MAX_CONTACTS` | `10` | fixed / see setting | `backend/apps/maintenance/repairs/dispatch.py:23` |
| `TechnicianContact.kind (models.CharField)` | `max_length=10` | field / model | `backend/apps/maintenance/repairs/models_contacts.py:34` |
| `TechnicianContact.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/models_contacts.py:37` |
| `TechnicianContact.opt_in_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/maintenance/repairs/models_contacts.py:48` |
| `TechnicianCoverage.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/maintenance/repairs/models_contacts.py:78` |
| `TechnicianDefault.area (models.CharField)` | `max_length=10` | field / model | `backend/apps/maintenance/repairs/models_contacts.py:100` |
| `IssueReport.area (models.CharField)` | `max_length=10` | field / model | `backend/apps/maintenance/repairs/models_issues.py:56` |
| `IssueReport.subject_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/maintenance/repairs/models_issues.py:57` |
| `IssueReport.source (models.CharField)` | `max_length=12` | field / model | `backend/apps/maintenance/repairs/models_issues.py:66` |
| `IssueReport.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/models_issues.py:84` |
| `IssueReport.state (models.CharField)` | `max_length=12; default=State.REPORTED` | field / model | `backend/apps/maintenance/repairs/models_issues.py:86` |
| `IssueReport.priority (models.CharField)` | `max_length=8; default='normal'` | field / model | `backend/apps/maintenance/repairs/models_issues.py:87` |
| `IssueReport.quote_state (models.CharField)` | `max_length=10; default=QuoteState.NONE` | field / model | `backend/apps/maintenance/repairs/models_issues.py:91` |
| `IssueReport.quote_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/maintenance/repairs/models_issues.py:92` |
| `IssueReport.quote_currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/maintenance/repairs/models_issues.py:93` |
| `IssueEvent.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/maintenance/repairs/models_records.py:55` |
| `IssueEvent.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/maintenance/repairs/models_records.py:62` |
| `IssueEvent.currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/maintenance/repairs/models_records.py:63` |
| `IssuePhoto.stage (models.CharField)` | `max_length=10` | field / model | `backend/apps/maintenance/repairs/models_records.py:80` |
| `IssuePhoto.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/maintenance/repairs/models_records.py:81` |
| `IssuePhoto.content_type (models.CharField)` | `max_length=64` | field / model | `backend/apps/maintenance/repairs/models_records.py:82` |
| `TechnicianDispatch.channel (models.CharField)` | `max_length=10` | field / model | `backend/apps/maintenance/repairs/models_records.py:109` |
| `TechnicianDispatch.status (models.CharField)` | `max_length=10` | field / model | `backend/apps/maintenance/repairs/models_records.py:110` |
| `TechnicianDispatch.failure_code (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/maintenance/repairs/models_records.py:111` |
| `TechnicianDispatch.provider_message_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/maintenance/repairs/models_records.py:112` |
| `RepairPart.kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/maintenance/repairs/models_records.py:129` |
| `RepairPart.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/models_records.py:132` |
| `RoomOutage.mode (models.CharField)` | `max_length=8; default=Mode.BLOCK` | field / model | `backend/apps/maintenance/repairs/models_service.py:36` |
| `RoomOutage.reason (models.CharField)` | `max_length=300` | field / model | `backend/apps/maintenance/repairs/models_service.py:37` |
| `SubjectMaintenanceSchedule.subject_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/maintenance/repairs/models_service.py:57` |
| `SubjectMaintenanceLog.subject_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/maintenance/repairs/models_service.py:84` |
| `SubjectMaintenanceLog.cost (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/maintenance/repairs/models_service.py:97` |
| `MAX_AGE` | `60 * 60` | fixed / see setting | `backend/apps/maintenance/repairs/photos.py:16` |
| `MAX_PER_STEP` | `6` | fixed / see setting | `backend/apps/maintenance/repairs/photos.py:17` |
| `PHOTOS (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:11` |
| `PHOTOS (serializers.ListField)` | `max_length=6; default=list` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:11` |
| `IssueReportCreateSerializer.makerspace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:26` |
| `IssueReportCreateSerializer.loan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:28` |
| `IssueReportCreateSerializer.booking_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:29` |
| `IssueReportCreateSerializer.machine_job_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:31` |
| `IssueReportCreateSerializer.machine_session_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:32` |
| `IssueReportCreateSerializer.product_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:34` |
| `IssueReportCreateSerializer.asset_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:35` |
| `IssueReportCreateSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:36` |
| `IssueReportCreateSerializer.description (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:37` |
| `PublicIssueReportCreateSerializer.contact_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:49` |
| `PublicIssueReportCreateSerializer.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:50` |
| `PublicIssueReportCreateSerializer.email_code (serializers.CharField)` | `max_length=12` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:51` |
| `IssueOpenSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:63` |
| `IssueOpenSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:64` |
| `IssueOpenSerializer.description (serializers.CharField)` | `max_length=4000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:65` |
| `IssueTriageSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:71` |
| `IssueReportRejectSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:75` |
| `IssueNoteSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:79` |
| `IssueAssignSerializer.contact_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:83` |
| `IssueUnassignSerializer.assignment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:88` |
| `IssueDispatchRequestSerializer.contact_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:92` |
| `IssueDispatchRequestSerializer.contact_ids (serializers.ListField)` | `min_length=1, max_length=10` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:92` |
| `IssueDispatchRequestSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:95` |
| `RepairWorkLogSerializer.note (serializers.CharField)` | `max_length=4000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:100` |
| `RepairWorkLogSerializer.contact_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:102` |
| `RepairPartWriteSerializer.product_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:108` |
| `RepairPartWriteSerializer.name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:109` |
| `RepairPartWriteSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=100000` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:110` |
| `RepairQuoteSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:114` |
| `RepairQuoteSerializer.currency (serializers.CharField)` | `min_length=3, max_length=3` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:115` |
| `RepairQuoteSerializer.contact_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:116` |
| `RepairQuoteSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:117` |
| `RepairQuoteDecisionSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:122` |
| `RepairPayoutSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:126` |
| `RepairPayoutSerializer.currency (serializers.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:127` |
| `RepairPayoutSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:131` |
| `RepairPayoutSerializer.receipt_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:132` |
| `RepairFixSerializer.resolution (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:137` |
| `ServiceStateChangeSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:143` |
| `ServiceStateChangeSerializer.reason (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:145` |
| `ServiceStateChangeSerializer.quantity (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:147` |
| `ServiceStateChangeSerializer.issue_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/maintenance/repairs/serializers_actions.py:149` |
| `TechnicianContactWriteSerializer.person_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_contacts.py:57` |
| `TechnicianContactWriteSerializer.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/repairs/serializers_contacts.py:58` |
| `TechnicianContactWriteSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/maintenance/repairs/serializers_contacts.py:59` |
| `TechnicianContactWriteSerializer.telegram_handle (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/maintenance/repairs/serializers_contacts.py:61` |
| `TechnicianContactWriteSerializer.notes (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/maintenance/repairs/serializers_contacts.py:62` |
| `TechnicianOptInAcceptSerializer.channels (serializers.ListField)` | `min_length=1` | field / model | `backend/apps/maintenance/repairs/serializers_contacts.py:98` |
| `LoanRepairHandoffSerializer.accountability_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/serializers_loan_handoff.py:18` |
| `LoanRepairHandoffSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/maintenance/repairs/serializers_loan_handoff.py:19` |
| `SubjectScheduleWriteSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/views_maintenance.py:42` |
| `SubjectScheduleWriteSerializer.description (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/maintenance/repairs/views_maintenance.py:43` |
| `SubjectScheduleWriteSerializer.interval_days (serializers.IntegerField)` | `min_value=1, max_value=3650` | field / model | `backend/apps/maintenance/repairs/views_maintenance.py:44` |
| `MaintenanceRunSerializer.summary (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/maintenance/repairs/views_maintenance.py:50` |
| `MaintenanceRunSerializer.parts_note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/maintenance/repairs/views_maintenance.py:51` |
| `MaintenanceRunSerializer.cost (MoneyField)` | `max_digits=13, min_value=0; default=None` | field / model | `backend/apps/maintenance/repairs/views_maintenance.py:52` |
| `MemberIssuePhotoSerializer.makerspace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/views_member.py:32` |
| `MAX_ROWS` | `200` | fixed / see setting | `backend/apps/maintenance/repairs/views_outage_impact.py:29` |
| `OutageImpactQuery.room_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/repairs/views_outage_impact.py:33` |
| `PublicIssuePhotoSerializer.contact_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/maintenance/repairs/views_public.py:35` |
| `MaintenanceScheduleWriteSerializer.interval_days (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/serializers.py:36` |
| `MaintenanceScheduleWriteSerializer.usage_hours (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/maintenance/serializers.py:39` |
| `MaintenanceScheduleWriteSerializer.job_count (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/serializers.py:40` |
| `MaintenanceLogWriteSerializer.cost (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/maintenance/serializers.py:95` |
| `MaintenanceLogWriteSerializer.schedule_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/serializers.py:101` |
| `MaintenanceDocumentPresignSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/maintenance/serializers.py:105` |
| `MaintenanceDocumentPresignSerializer.content_type (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/maintenance/serializers.py:106` |
| `MaintenanceDocumentFinalizeSerializer.object_key (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/maintenance/serializers.py:122` |
| `MaintenanceCostFields.cost_currency (serializers.CharField)` | `min_length=3, max_length=3; default=''` | field / model | `backend/apps/maintenance/serializers_cost.py:13` |
| `WorkOrderCreateSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/views_work_orders.py:52` |
| `WorkOrderCreateSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/maintenance/views_work_orders.py:53` |
| `WorkOrderMoveSerializer.cost (MoneyField)` | `max_digits=13, min_value=0; default=None` | field / model | `backend/apps/maintenance/views_work_orders.py:63` |
| `WorkOrderAssignSerializer.assignee_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/maintenance/views_work_orders.py:69` |

</details>

<details>
<summary>maker_formats (4 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_RANGE` | `1024 * 1024` | fixed / see setting | `backend/apps/maker_formats/range_reader.py:4` |
| `MAX_ENTRIES` | `2000` | fixed / see setting | `backend/apps/maker_formats/zip_listing.py:10` |
| `MAX_DIRECTORY` | `1024 * 1024` | fixed / see setting | `backend/apps/maker_formats/zip_listing.py:11` |
| `MAX_EXPANSION` | `1024 * 1024 * 1024` | fixed / see setting | `backend/apps/maker_formats/zip_listing.py:12` |

</details>

<details>
<summary>makerspaces (441 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `RECENT_LIMIT` | `20` | fixed / see setting | `backend/apps/makerspaces/account_profile_activity.py:12` |
| `MAX_TIMELINE` | `100` | fixed / see setting | `backend/apps/makerspaces/account_profile_children_views.py:27` |
| `MAX_ACHIEVEMENTS` | `30` | fixed / see setting | `backend/apps/makerspaces/account_profile_children_views.py:28` |
| `AchievementSerializer.title (serializers.CharField)` | `max_length=160` | field / model | `backend/apps/makerspaces/account_profile_children_views.py:107` |
| `AchievementSerializer.issuer (serializers.CharField)` | `max_length=160` | field / model | `backend/apps/makerspaces/account_profile_children_views.py:108` |
| `AchievementSerializer.description (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/makerspaces/account_profile_children_views.py:109` |
| `AchievementSerializer.url (serializers.URLField)` | `max_length=500` | field / model | `backend/apps/makerspaces/account_profile_children_views.py:110` |
| `AccountProfileWriteSerializer.headline (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:19` |
| `AccountProfileWriteSerializer.status_note (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:21` |
| `AccountProfileWriteSerializer.institution (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:22` |
| `AccountProfileWriteSerializer.bio (serializers.CharField)` | `max_length=MAX_BIO` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:23` |
| `AccountProfileWriteSerializer.domains (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:24` |
| `AccountProfileWriteSerializer.domains (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:24` |
| `AccountProfileWriteSerializer.skills (SkillSerializer)` | `max_length=30` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:25` |
| `AccountProfileWriteSerializer.links (HttpsLinkSerializer)` | `max_length=10` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:26` |
| `AccountProfileWriteSerializer.education (serializers.ListField)` | `max_length=MAX_EDUCATION` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:29` |
| `AccountProfileWriteSerializer.projects (serializers.ListField)` | `max_length=MAX_PROJECTS` | field / model | `backend/apps/makerspaces/account_profile_serializers.py:31` |
| `HandleSerializer.handle (serializers.CharField)` | `max_length=30` | field / model | `backend/apps/makerspaces/account_profile_views.py:34` |
| `MakerspaceAddForm.new_organization_name (forms.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/admin_owner.py:19` |
| `MakerspaceAddForm.hosting_request (forms.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/admin_owner.py:25` |
| `SecurityActionForm.value (forms.CharField)` | `max_length=4000` | field / model | `backend/apps/makerspaces/admin_security.py:36` |
| `SecurityActionForm.note (forms.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/admin_security.py:37` |
| `SecurityActionForm.reason (forms.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/admin_security.py:38` |
| `ClosedNoticeSerializer.public_closed_notice (serializers.CharField)` | `max_length=280` | field / model | `backend/apps/makerspaces/closed_notice.py:44` |
| `HandleCheckSerializer.handle (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/handle_gate.py:59` |
| `HandleCheckSerializer.username (serializers.CharField)` | `max_length=150` | field / model | `backend/apps/makerspaces/handle_gate.py:60` |
| `HandleCheckSerializer.display_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/handle_gate.py:61` |
| `SPACE_QUOTA_LIMIT_KEYS` | `frozenset({'events_monthly', 'bookings_monthly', 'payments_monthly_count', 'payments_monthly_amount'})` | fixed / see setting | `backend/apps/makerspaces/limits_core.py:48` |
| `ACTIVITY_LIMIT` | `50` | fixed / see setting | `backend/apps/makerspaces/member_activity_machine_service.py:11` |
| `RECENT_LIMIT` | `20` | fixed / see setting | `backend/apps/makerspaces/member_activity_service.py:19` |
| `ACTIVITY_LIMIT` | `50` | fixed / see setting | `backend/apps/makerspaces/member_activity_service.py:20` |
| `SYNC_SHEET_LIMIT` | `10` | fixed / see setting | `backend/apps/makerspaces/member_card_admin_views.py:152` |
| `CardNoteSerializer.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/member_card_admin_views_l3.py:42` |
| `CardScanSerializer.payload (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/member_card_admin_views_l3.py:170` |
| `CardScanSerializer.duration_minutes (serializers.IntegerField)` | `min_value=15, max_value=480` | field / model | `backend/apps/makerspaces/member_card_admin_views_l3.py:171` |
| `MemberCardIssueSerializer.printed_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/member_card_serializers.py:54` |
| `MemberCardRevokeSerializer.reason (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/makerspaces/member_card_serializers.py:62` |
| `MemberCardRevokeSerializer.note (serializers.CharField)` | `max_length=500, min_length=3` | field / model | `backend/apps/makerspaces/member_card_serializers.py:64` |
| `MemberCardOwnUpdateSerializer.printed_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/member_card_serializers.py:68` |
| `MemberCardPhotoPresignSerializer.content_type (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/member_card_serializers.py:72` |
| `MemberCardPhotoFinalizeSerializer.object_key (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/member_card_serializers.py:76` |
| `MemberCardPhotoFinalizeSerializer.content_type (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/member_card_serializers.py:77` |
| `MemberCardResolveSerializer.payload (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/member_card_serializers.py:88` |
| `HISTORY_LIMIT` | `20` | fixed / see setting | `backend/apps/makerspaces/member_dashboard_service.py:30` |
| `MAX_ROWS` | `200` | fixed / see setting | `backend/apps/makerspaces/member_register_bulk.py:31` |
| `MemberVerificationRequestSerializer.membership_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/member_verification_views.py:17` |
| `MAX_BULK` | `100` | fixed / see setting | `backend/apps/makerspaces/membership_admission_bulk.py:15` |
| `MAX_ROUNDS` | `1` | fixed / see setting | `backend/apps/makerspaces/membership_admission_changes.py:32` |
| `MAX_PURPOSES` | `20` | fixed / see setting | `backend/apps/makerspaces/membership_consent.py:22` |
| `MAX_USES` | `10000` | fixed / see setting | `backend/apps/makerspaces/membership_invite_links.py:22` |
| `MAX_REMINDERS` | `200` | fixed / see setting | `backend/apps/makerspaces/membership_renewal_desk.py:29` |
| `AccountProfile.headline (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:80` |
| `AccountProfile.status (models.CharField)` | `max_length=24; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:81` |
| `AccountProfile.status_note (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:82` |
| `AccountProfile.institution (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:83` |
| `AccountProfile.avatar_key (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:85` |
| `AccountProfile.github_username (models.CharField)` | `max_length=39; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:92` |
| `AccountProject.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_account_profile.py:115` |
| `AccountProject.subtitle (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:116` |
| `AccountProject.image_key (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:121` |
| `AccountTimelineEntry.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_account_profile.py:146` |
| `AccountTimelineEntry.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_account_profile.py:147` |
| `AccountTimelineEntry.organization (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:148` |
| `AccountTimelineEntry.location (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:149` |
| `ProfileAchievement.title (models.CharField)` | `max_length=160` | field / model | `backend/apps/makerspaces/models_account_profile.py:171` |
| `ProfileAchievement.issuer (models.CharField)` | `max_length=160; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:172` |
| `ProfileAchievement.url (models.URLField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:174` |
| `ProfileAchievement.description (models.TextField)` | `max_length=2000; default=''` | field / model | `backend/apps/makerspaces/models_account_profile.py:175` |
| `MakerspaceMembershipSettings.join_mode (models.CharField)` | `max_length=16; default=JoinMode.APPROVAL` | field / model | `backend/apps/makerspaces/models_admission.py:22` |
| `MakerspaceMembershipSettings.payment_timing (models.CharField)` | `max_length=24; default=PaymentTiming.AFTER` | field / model | `backend/apps/makerspaces/models_admission.py:28` |
| `MakerspaceMembershipSettings.joining_fee (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_admission.py:34` |
| `MakerspaceMembershipSettings.joining_fee (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/makerspaces/models_admission.py:34` |
| `MakerspaceMembershipSettings.joining_fee_currency (models.CharField)` | `max_length=3; default='usd'` | field / model | `backend/apps/makerspaces/models_admission.py:35` |
| `MakerspaceMembershipSettings.rejoin_dues_rule (models.CharField)` | `max_length=16; default=RejoinRule.ONCE` | field / model | `backend/apps/makerspaces/models_admission.py:36` |
| `MakerspaceMembershipSettings.member_number_pattern (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/makerspaces/models_admission.py:42` |
| `MakerspaceMembershipSettings.privacy_notice_version (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/makerspaces/models_admission.py:45` |
| `MakerspaceArchiveRequest.reason (models.TextField)` | `max_length=2000` | field / model | `backend/apps/makerspaces/models_archive_requests.py:35` |
| `MakerspaceArchiveRequest.resolution_note (models.TextField)` | `max_length=2000` | field / model | `backend/apps/makerspaces/models_archive_requests.py:39` |
| `MakerspaceArchiveRequest.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/makerspaces/models_archive_requests.py:40` |
| `CommunityPolicy.minors_minimum_age (MaxValueValidator)` | `max_value=17` | field / model | `backend/apps/makerspaces/models_community_policy.py:24` |
| `CommunityPolicy.adult_age (MaxValueValidator)` | `max_value=21` | field / model | `backend/apps/makerspaces/models_community_policy.py:26` |
| `CommunityPolicy.adult_age (MinValueValidator)` | `min_value=16` | field / model | `backend/apps/makerspaces/models_community_policy.py:26` |
| `CommunityPolicy.consent_valid_days (MaxValueValidator)` | `max_value=1825` | field / model | `backend/apps/makerspaces/models_community_policy.py:31` |
| `CommunityPolicy.consent_valid_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_community_policy.py:31` |
| `CommunityPolicy.volunteer_minutes_per_credit (MaxValueValidator)` | `max_value=100000` | field / model | `backend/apps/makerspaces/models_community_policy.py:34` |
| `CommunityPolicy.volunteer_credit_kind (models.CharField)` | `max_length=12; default=CreditKind.DISCOUNT` | field / model | `backend/apps/makerspaces/models_community_policy.py:35` |
| `CommunityPolicy.volunteer_credit_amount (MoneyDecimalField)` | `max_digits=11; default=0` | field / model | `backend/apps/makerspaces/models_community_policy.py:36` |
| `CommunityPolicy.volunteer_credit_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_community_policy.py:37` |
| `CommunityPolicy.volunteer_credit_days (MaxValueValidator)` | `max_value=366` | field / model | `backend/apps/makerspaces/models_community_policy.py:38` |
| `CommunityPolicy.join_followup_delay_hours (MaxValueValidator)` | `max_value=336` | field / model | `backend/apps/makerspaces/models_community_policy.py:42` |
| `CommunityPolicy.join_followup_delay_hours (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_community_policy.py:42` |
| `GuestPassPolicy.guest_borrowing_mode (models.CharField)` | `max_length=24; default=Borrowing.ON_SITE` | field / model | `backend/apps/makerspaces/models_guest_passes.py:46` |
| `GuestPassPolicy.guest_machine_mode (models.CharField)` | `max_length=24; default=Machines.NONE` | field / model | `backend/apps/makerspaces/models_guest_passes.py:47` |
| `GuestPassPolicy.sponsored_liability (models.CharField)` | `max_length=16; default=Liability.GUEST` | field / model | `backend/apps/makerspaces/models_guest_passes.py:48` |
| `GuestPassPolicy.walk_in_registration_creates (models.CharField)` | `max_length=16; default=WalkIn.GUEST_PASS` | field / model | `backend/apps/makerspaces/models_guest_passes.py:49` |
| `GuestPassPolicy.sponsor_min_tenure_days (MaxValueValidator)` | `max_value=3650` | field / model | `backend/apps/makerspaces/models_guest_passes.py:54` |
| `GuestPassPolicy.max_concurrent_guests_per_sponsor (MaxValueValidator)` | `max_value=50` | field / model | `backend/apps/makerspaces/models_guest_passes.py:56` |
| `GuestPassPolicy.max_concurrent_guests_per_sponsor (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_guest_passes.py:56` |
| `GuestPassPolicy.visits_before_join_prompt (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_guest_passes.py:60` |
| `GuestPassPolicy.hard_visit_cap (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_guest_passes.py:62` |
| `GuestPassPolicy.day_pass_daily_cap (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_guest_passes.py:64` |
| `DayPassProduct.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/models_guest_passes.py:80` |
| `DayPassProduct.amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_guest_passes.py:81` |
| `DayPassProduct.amount (MoneyDecimalField)` | `max_digits=11; default=0` | field / model | `backend/apps/makerspaces/models_guest_passes.py:81` |
| `DayPassProduct.currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/makerspaces/models_guest_passes.py:82` |
| `DayPassProduct.daily_cap (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_guest_passes.py:85` |
| `GuestPass.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/makerspaces/models_guest_passes.py:118` |
| `GuestPass.status (models.CharField)` | `max_length=12; default=Status.ISSUED` | field / model | `backend/apps/makerspaces/models_guest_passes.py:119` |
| `GuestPass.waiver_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_guest_passes.py:139` |
| `GuestPass.revoked_reason (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/makerspaces/models_guest_passes.py:148` |
| `GuestPass.operation_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_guest_passes.py:153` |
| `ImportedUserReconciliation.source_user_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/makerspaces/models_imports.py:25` |
| `ImportedUserReconciliation.source_username (models.CharField)` | `max_length=255` | field / model | `backend/apps/makerspaces/models_imports.py:26` |
| `PendingImportedMembership.archived_role_label (models.CharField)` | `max_length=255` | field / model | `backend/apps/makerspaces/models_imports.py:56` |
| `PendingImportedMembership.status (models.CharField)` | `max_length=16; default='active'` | field / model | `backend/apps/makerspaces/models_imports.py:64` |
| `PendingImportedMembership.waiver_version_accepted (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_imports.py:79` |
| `PendingImportedMembership.witnessed_waiver_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_imports.py:94` |
| `PendingImportedMembership.source_membership_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/makerspaces/models_imports.py:100` |
| `PendingImportedMembership.unresolved_reason (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_imports.py:109` |
| `InvitationRequest.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/makerspaces/models_invitation_requests.py:34` |
| `MakerspaceLoanPolicy.default_loan_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/makerspaces/models_loan_policy.py:31` |
| `MakerspaceLoanPolicy.default_loan_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_loan_policy.py:31` |
| `MakerspaceLoanPolicy.loan_renewal_mode (models.CharField)` | `max_length=16; default=RenewalMode.OFF` | field / model | `backend/apps/makerspaces/models_loan_policy.py:33` |
| `MakerspaceLoanPolicy.loan_max_renewals (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/makerspaces/models_loan_policy.py:34` |
| `MakerspaceLoanPolicy.loan_renewal_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/makerspaces/models_loan_policy.py:36` |
| `MakerspaceLoanPolicy.loan_renewal_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_loan_policy.py:36` |
| `MakerspaceLoanPolicy.loan_escalate_overdue_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/makerspaces/models_loan_policy.py:41` |
| `Makerspace.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:75` |
| `Makerspace.kind (models.CharField)` | `max_length=16; default=Kind.MAKERSPACE` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:76` |
| `Makerspace.public_code (models.CharField)` | `max_length=4; default=generate_public_code` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:78` |
| `Makerspace.location (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:90` |
| `Makerspace.timezone (models.CharField)` | `max_length=100; default=default_timezone` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:91` |
| `Makerspace.default_locale (models.CharField)` | `max_length=16; default='en'` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:94` |
| `Makerspace.country (models.CharField)` | `max_length=2; default=''` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:95` |
| `Makerspace.geofence_latitude (MaxValueValidator)` | `max_value=90` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:98` |
| `Makerspace.geofence_latitude (MinValueValidator)` | `min_value=-90` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:98` |
| `Makerspace.geofence_latitude (models.DecimalField)` | `max_digits=9` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:98` |
| `Makerspace.geofence_longitude (MaxValueValidator)` | `max_value=180` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:99` |
| `Makerspace.geofence_longitude (MinValueValidator)` | `min_value=-180` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:99` |
| `Makerspace.geofence_longitude (models.DecimalField)` | `max_digits=9` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:99` |
| `Makerspace.geofence_radius_m (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:100` |
| `Makerspace.public_print_status_lookup_policy (models.CharField)` | `max_length=32; default=PublicPrintStatusLookupPolicy.TOKEN_ONLY` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:102` |
| `Makerspace.membership_policy (models.CharField)` | `max_length=16; default=MembershipPolicy.REQUEST` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:107` |
| `Makerspace.membership_dues_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:112` |
| `Makerspace.membership_dues_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:116` |
| `Makerspace.financial_year_start_month (MaxValueValidator)` | `max_value=12` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:122` |
| `Makerspace.financial_year_start_month (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:122` |
| `Makerspace.filament_low_stock_threshold_grams (models.DecimalField)` | `max_digits=10; default=0` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:130` |
| `Makerspace.logo_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:145` |
| `Makerspace.cover_image_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:146` |
| `Makerspace.frontend_domain (models.CharField)` | `max_length=255` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:149` |
| `Makerspace.frontend_domain_status (models.CharField)` | `max_length=16; default=DomainStatus.PENDING` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:154` |
| `Makerspace.domain_verification_token (models.CharField)` | `max_length=64; default=generate_domain_verification_token` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:159` |
| `Makerspace.public_api_key (models.CharField)` | `max_length=40; default=generate_publishable_key` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:167` |
| `Makerspace.telegram_group_chat_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:180` |
| `Makerspace.telegram_bot_token (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:181` |
| `Makerspace.email_provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:182` |
| `Makerspace.smtp_host (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:186` |
| `Makerspace.smtp_username (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:188` |
| `Makerspace.smtp_password (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:189` |
| `Makerspace.email_from_name (models.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:199` |
| `Makerspace.smtp_verified_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:201` |
| `Makerspace.lifecycle_state (models.CharField)` | `max_length=16; default=LifecycleState.ACTIVE` | field / model | `backend/apps/makerspaces/models_makerspace_core.py:238` |
| `MemberCard.number_text (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/makerspaces/models_member_cards.py:42` |
| `MemberCard.photo_object_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/makerspaces/models_member_cards.py:44` |
| `MemberCard.photo_content_type (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/makerspaces/models_member_cards.py:45` |
| `MemberCard.photo_consent_version (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/makerspaces/models_member_cards.py:48` |
| `MemberCard.revoked_reason (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/makerspaces/models_member_cards.py:54` |
| `MemberCard.verify_consent_version (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/makerspaces/models_member_cards.py:62` |
| `MemberCard.email_format (models.CharField)` | `max_length=3; default='pdf'` | field / model | `backend/apps/makerspaces/models_member_cards.py:64` |
| `MAX_LEVELS` | `4` | fixed / see setting | `backend/apps/makerspaces/models_member_units.py:25` |
| `MemberUnit.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/models_member_units.py:40` |
| `MemberUnit.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/makerspaces/models_member_units.py:41` |
| `MemberUnit.code (models.CharField)` | `max_length=6` | field / model | `backend/apps/makerspaces/models_member_units.py:42` |
| `MemberUnit.path (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/makerspaces/models_member_units.py:47` |
| `ImportedMemberUnit.review_status (models.CharField)` | `max_length=16; default=Review.NOT_REQUIRED` | field / model | `backend/apps/makerspaces/models_member_units.py:115` |
| `MembershipImportBatch.file_name (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_membership_imports.py:22` |
| `MembershipImportBatch.file_kind (models.CharField)` | `max_length=8; default='csv'` | field / model | `backend/apps/makerspaces/models_membership_imports.py:23` |
| `ImportedMember.status (models.CharField)` | `max_length=16; default=Status.INVITED` | field / model | `backend/apps/makerspaces/models_membership_imports.py:45` |
| `ImportedMember.external_number (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/makerspaces/models_membership_imports.py:51` |
| `ImportedMember.state_code (models.CharField)` | `max_length=2; default=''` | field / model | `backend/apps/makerspaces/models_membership_imports.py:56` |
| `MembershipInviteLink.code_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_membership_invites.py:17` |
| `MembershipInviteLink.label (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/makerspaces/models_membership_invites.py:18` |
| `MembershipPlan.included_booking_hours (MaxValueValidator)` | `max_value=8784` | field / model | `backend/apps/makerspaces/models_membership_plans.py:41` |
| `MembershipPlan.included_machine_hours (MaxValueValidator)` | `max_value=8784` | field / model | `backend/apps/makerspaces/models_membership_plans.py:42` |
| `MembershipPlan.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/models_membership_plans.py:53` |
| `MembershipPlan.interval (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_membership_plans.py:54` |
| `MembershipPlan.amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/makerspaces/models_membership_plans.py:57` |
| `MembershipPlan.amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_membership_plans.py:58` |
| `MembershipPlan.currency (models.CharField)` | `max_length=3; default='usd'` | field / model | `backend/apps/makerspaces/models_membership_plans.py:61` |
| `MembershipPlan.renewal_open_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/makerspaces/models_membership_plans.py:64` |
| `MembershipPlan.renewal_grace_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/makerspaces/models_membership_plans.py:65` |
| `MembershipPlan.renewal_retries (MaxValueValidator)` | `max_value=3` | field / model | `backend/apps/makerspaces/models_membership_plans.py:66` |
| `MembershipPlan.plan_type (models.CharField)` | `max_length=16; default=PlanType.ROLLING` | field / model | `backend/apps/makerspaces/models_membership_plans.py:69` |
| `MembershipPlan.renewal_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/models_membership_plans.py:72` |
| `MembershipPlan.renewal_amount (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_membership_plans.py:73` |
| `MembershipPlan.joining_fee (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/models_membership_plans.py:76` |
| `MembershipPlan.joining_fee (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/makerspaces/models_membership_plans.py:77` |
| `MembershipPlan.rejoin_rule (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_membership_plans.py:79` |
| `MembershipPlan.rejoin_after_days (MaxValueValidator)` | `max_value=3650` | field / model | `backend/apps/makerspaces/models_membership_plans.py:80` |
| `MembershipPlan.payment_timing (models.CharField)` | `max_length=24` | field / model | `backend/apps/makerspaces/models_membership_plans.py:81` |
| `MembershipPlan.join_mode (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_membership_plans.py:82` |
| `MembershipPlan.late_renewal (models.CharField)` | `max_length=16; default=LateRenewal.BACKDATE` | field / model | `backend/apps/makerspaces/models_membership_plans.py:84` |
| `MembershipPlan.sac_code (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/makerspaces/models_membership_plans.py:86` |
| `MembershipPlan.join_photo (models.CharField)` | `max_length=8; default='off'` | field / model | `backend/apps/makerspaces/models_membership_plans.py:88` |
| `MembershipPlan.join_phone (models.CharField)` | `max_length=8; default='hidden'` | field / model | `backend/apps/makerspaces/models_membership_plans.py:89` |
| `MembershipPlan.join_state (models.CharField)` | `max_length=8; default='hidden'` | field / model | `backend/apps/makerspaces/models_membership_plans.py:90` |
| `MembershipPlan.slug (models.SlugField)` | `max_length=80; default=''` | field / model | `backend/apps/makerspaces/models_membership_plans.py:93` |
| `MembershipConsent.purpose (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_membership_privacy.py:29` |
| `MembershipConsent.notice_version (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/makerspaces/models_membership_privacy.py:30` |
| `MembershipConsent.source (models.CharField)` | `max_length=16; default=Source.MEMBER` | field / model | `backend/apps/makerspaces/models_membership_privacy.py:31` |
| `MembershipErasureRequest.status (models.CharField)` | `max_length=16; default=Status.REQUESTED` | field / model | `backend/apps/makerspaces/models_membership_privacy.py:56` |
| `MembershipErasureRequest.decision_note (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_membership_privacy.py:60` |
| `MembershipRecord.state_code (models.CharField)` | `max_length=2; default=''` | field / model | `backend/apps/makerspaces/models_membership_records.py:41` |
| `MembershipTitle.name (models.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/models_membership_records.py:62` |
| `MembershipTitle.colour (models.CharField)` | `max_length=24; default=''` | field / model | `backend/apps/makerspaces/models_membership_records.py:63` |
| `MembershipTerm.status (models.CharField)` | `max_length=16; default=Status.ACTIVE` | field / model | `backend/apps/makerspaces/models_membership_terms.py:42` |
| `MembershipTerm.kind (models.CharField)` | `max_length=16; default=TermKind.NEW` | field / model | `backend/apps/makerspaces/models_membership_terms.py:71` |
| `MembershipTerm.price (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/models_membership_terms.py:73` |
| `MembershipTerm.joining_fee (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/makerspaces/models_membership_terms.py:74` |
| `MembershipTerm.currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/makerspaces/models_membership_terms.py:75` |
| `MembershipTerm.plan_type (models.CharField)` | `max_length=16; default=PlanType.ROLLING` | field / model | `backend/apps/makerspaces/models_membership_terms.py:76` |
| `MembershipTermStatusEvent.status (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_membership_terms.py:115` |
| `MembershipTermStatusEvent.reason (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_membership_terms.py:125` |
| `MakerspaceMembership.track (models.CharField)` | `max_length=16; default=Track.COMMUNITY` | field / model | `backend/apps/makerspaces/models_memberships.py:61` |
| `MakerspaceMembership.role (models.CharField)` | `max_length=32; default=Role.SPACE_MANAGER` | field / model | `backend/apps/makerspaces/models_memberships.py:68` |
| `MakerspaceMembership.status (models.CharField)` | `max_length=16; default='active'` | field / model | `backend/apps/makerspaces/models_memberships.py:93` |
| `MakerspaceMembership.waiver_version_accepted (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_memberships.py:117` |
| `MakerspaceMembership.witnessed_waiver_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_memberships.py:126` |
| `MakerspaceMembership.source (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/makerspaces/models_memberships.py:139` |
| `GuardianConsentTerms.version (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_minors.py:22` |
| `GuardianConsent.terms_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_minors.py:71` |
| `GuardianConsent.method (models.CharField)` | `max_length=20` | field / model | `backend/apps/makerspaces/models_minors.py:72` |
| `GuardianConsent.operation_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_minors.py:84` |
| `PublicPageObjectCleanup.owner_kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_page_cleanup.py:8` |
| `PublicPageObjectCleanup.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/models_page_cleanup.py:12` |
| `MemberProfile.headline (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:58` |
| `MemberProfile.institution (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:59` |
| `MemberProfile.avatar_key (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:61` |
| `MemberProfile.github_username (models.CharField)` | `max_length=39; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:68` |
| `MemberProject.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_profiles.py:90` |
| `MemberProject.subtitle (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:91` |
| `MemberProject.image_key (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:95` |
| `PublicHandle.handle (models.CharField)` | `max_length=30` | field / model | `backend/apps/makerspaces/models_profiles.py:123` |
| `PublicHandleRedirect.handle (models.CharField)` | `max_length=30` | field / model | `backend/apps/makerspaces/models_profiles.py:150` |
| `ProfileTimelineEntry.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_profiles.py:179` |
| `ProfileTimelineEntry.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_profiles.py:180` |
| `ProfileTimelineEntry.organization (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:181` |
| `ProfileTimelineEntry.location (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_profiles.py:182` |
| `MakerspacePublicPageAsset.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/models_public_pages.py:30` |
| `MakerspacePublicPageAsset.alt_text (models.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/models_public_pages.py:32` |
| `MakerspacePublicPageRevisionAsset.slot (models.CharField)` | `max_length=80` | field / model | `backend/apps/makerspaces/models_public_pages.py:40` |
| `PublicSiteSettings.event_default_registration_audience (models.CharField)` | `max_length=32; default='members'` | field / model | `backend/apps/makerspaces/models_public_site.py:8` |
| `PublicSiteSettings.public_landing_page (models.CharField)` | `max_length=16; default='auto'` | field / model | `backend/apps/makerspaces/models_public_site.py:14` |
| `PublicSiteSettings.public_stats_sections (models.CharField)` | `max_length=120; default='machines,printing,lending'` | field / model | `backend/apps/makerspaces/models_public_site.py:24` |
| `PublicSiteSettings.public_stats_period (models.CharField)` | `max_length=8; default='month'` | field / model | `backend/apps/makerspaces/models_public_site.py:25` |
| `PublicSiteSettings.public_stats_headline (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_public_site.py:29` |
| `PublicSiteSettings.public_closed_notice (models.CharField)` | `max_length=280; default=''` | field / model | `backend/apps/makerspaces/models_public_site.py:33` |
| `MakerspaceRole.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/makerspaces/models_roles.py:22` |
| `MakerspaceRole.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/makerspaces/models_roles.py:23` |
| `MakerspaceRole.legacy_role (models.CharField)` | `max_length=32` | field / model | `backend/apps/makerspaces/models_roles.py:25` |
| `MakerspaceWaiver.version (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_roles.py:77` |
| `MembershipRequest.invite_email (models.CharField)` | `max_length=254` | field / model | `backend/apps/makerspaces/models_roles.py:115` |
| `MembershipRequest.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/makerspaces/models_roles.py:116` |
| `MembershipRequest.state (models.CharField)` | `max_length=24` | field / model | `backend/apps/makerspaces/models_roles.py:117` |
| `MembershipRequest.joining_fee (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/makerspaces/models_roles.py:137` |
| `MembershipRequest.first_term_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/makerspaces/models_roles.py:138` |
| `MembershipRequest.charge_currency (models.CharField)` | `max_length=3; default='usd'` | field / model | `backend/apps/makerspaces/models_roles.py:139` |
| `SubdomainRequest.requested_label (models.CharField)` | `max_length=63` | field / model | `backend/apps/makerspaces/models_roles.py:167` |
| `SubdomainRequest.status (models.CharField)` | `max_length=20; default=Status.PENDING` | field / model | `backend/apps/makerspaces/models_roles.py:168` |
| `MakerspaceSecurityLock.key (models.CharField)` | `max_length=100` | field / model | `backend/apps/makerspaces/models_security.py:17` |
| `MakerspaceSecurityLock.note (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_security.py:19` |
| `ModuleSettingsGrant.module (models.CharField)` | `max_length=32` | field / model | `backend/apps/makerspaces/models_settings_authority.py:44` |
| `ModuleSettingLock.setting_key (models.CharField)` | `max_length=100` | field / model | `backend/apps/makerspaces/models_settings_authority.py:79` |
| `ModuleSettingLock.note (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_settings_authority.py:83` |
| `SpacePackProfile.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/models_space_packs.py:23` |
| `StationOperatorLease.allowed_actions (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/models_station_leases.py:36` |
| `Station.kind (models.CharField)` | `max_length=24` | field / model | `backend/apps/makerspaces/models_stations.py:22` |
| `Station.name (models.CharField)` | `max_length=160` | field / model | `backend/apps/makerspaces/models_stations.py:23` |
| `StationCredential.pin_digest (models.CharField)` | `max_length=128` | field / model | `backend/apps/makerspaces/models_stations.py:52` |
| `VolunteerHourEntry.description (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_volunteer.py:29` |
| `VolunteerHourEntry.source (models.CharField)` | `max_length=16; default=Source.MANUAL` | field / model | `backend/apps/makerspaces/models_volunteer.py:30` |
| `VolunteerHourEntry.status (models.CharField)` | `max_length=10; default=Status.PENDING` | field / model | `backend/apps/makerspaces/models_volunteer.py:33` |
| `VolunteerHourEntry.review_note (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_volunteer.py:39` |
| `VolunteerCredit.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/makerspaces/models_volunteer.py:62` |
| `VolunteerCredit.amount (MoneyDecimalField)` | `max_digits=11; default=0` | field / model | `backend/apps/makerspaces/models_volunteer.py:63` |
| `VolunteerCredit.currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/makerspaces/models_volunteer.py:65` |
| `VolunteerCredit.status (models.CharField)` | `max_length=10; default=Status.AVAILABLE` | field / model | `backend/apps/makerspaces/models_volunteer.py:66` |
| `VolunteerCredit.applied_amount (MoneyDecimalField)` | `max_digits=11` | field / model | `backend/apps/makerspaces/models_volunteer.py:69` |
| `VolunteerCredit.void_reason (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/models_volunteer.py:72` |
| `MAX_JOINS` | `14` | fixed / see setting | `backend/apps/makerspaces/open_status.py:13` |
| `MAX_INTERVALS` | `400` | fixed / see setting | `backend/apps/makerspaces/opening_hours.py:15` |
| `MAX_CHUNK_BYTES` | `1048576` | fixed / see setting | `backend/apps/makerspaces/private_upload_transport.py:13` |
| `MAX_POLICY_INTERVAL_SECONDS` | `2` | fixed / see setting | `backend/apps/makerspaces/private_upload_transport.py:14` |
| `DERIVED_LIMIT` | `60` | fixed / see setting | `backend/apps/makerspaces/profile_achievements.py:22` |
| `MAX_RESPONSE_BYTES` | `128 * 1024` | fixed / see setting | `backend/apps/makerspaces/profile_github_fetch.py:14` |
| `GitHubDaySerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/makerspaces/profile_github_views.py:17` |
| `ImportInput.submission_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/profile_project_import.py:87` |
| `MAX_INTERESTS` | `20` | fixed / see setting | `backend/apps/makerspaces/profile_serializers.py:19` |
| `MAX_LANGUAGES` | `10` | fixed / see setting | `backend/apps/makerspaces/profile_serializers.py:20` |
| `MAX_EDUCATION` | `10` | fixed / see setting | `backend/apps/makerspaces/profile_serializers.py:21` |
| `MAX_LINKS` | `10` | fixed / see setting | `backend/apps/makerspaces/profile_serializers.py:22` |
| `MAX_PROJECTS` | `20` | fixed / see setting | `backend/apps/makerspaces/profile_serializers.py:23` |
| `MAX_BIO` | `2000` | fixed / see setting | `backend/apps/makerspaces/profile_serializers.py:24` |
| `TagListField.super().__init__` | `max_length=max_items` | field / model | `backend/apps/makerspaces/profile_serializers.py:30` |
| `TagListField.serializers.CharField` | `max_length=60` | field / model | `backend/apps/makerspaces/profile_serializers.py:31` |
| `EducationEntrySerializer.institution (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/profile_serializers.py:40` |
| `EducationEntrySerializer.qualification (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/profile_serializers.py:41` |
| `EducationEntrySerializer.year (serializers.CharField)` | `max_length=20; default=''` | field / model | `backend/apps/makerspaces/profile_serializers.py:42` |
| `ProjectLinkSerializer.label (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/profile_serializers.py:46` |
| `ProjectLinkSerializer.url (serializers.URLField)` | `max_length=500` | field / model | `backend/apps/makerspaces/profile_serializers.py:47` |
| `ProjectWriteSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/profile_serializers.py:60` |
| `ProjectWriteSerializer.subtitle (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/profile_serializers.py:61` |
| `ProjectWriteSerializer.description (serializers.CharField)` | `max_length=4000; default=''` | field / model | `backend/apps/makerspaces/profile_serializers.py:64` |
| `ProjectWriteSerializer.links (serializers.ListField)` | `max_length=MAX_LINKS` | field / model | `backend/apps/makerspaces/profile_serializers.py:65` |
| `ProfileWriteSerializer.headline (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/profile_serializers.py:74` |
| `ProfileWriteSerializer.institution (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/profile_serializers.py:75` |
| `ProfileWriteSerializer.bio (serializers.CharField)` | `max_length=MAX_BIO` | field / model | `backend/apps/makerspaces/profile_serializers.py:76` |
| `ProfileWriteSerializer.education (serializers.ListField)` | `max_length=MAX_EDUCATION` | field / model | `backend/apps/makerspaces/profile_serializers.py:79` |
| `ProfileWriteSerializer.projects (serializers.ListField)` | `max_length=MAX_PROJECTS` | field / model | `backend/apps/makerspaces/profile_serializers.py:87` |
| `RECENT_ATTENDED_EVENTS_LIMIT` | `20` | fixed / see setting | `backend/apps/makerspaces/profile_services.py:18` |
| `MAX_ASSETS` | `50` | fixed / see setting | `backend/apps/makerspaces/public_page_assets.py:16` |
| `MAX_DOCUMENT_BYTES` | `131072` | fixed / see setting | `backend/apps/makerspaces/public_page_contract.py:12` |
| `SectionsField.super().__init__` | `max_length=20` | field / model | `backend/apps/makerspaces/public_page_contract.py:55` |
| `Document.schema_version (s.IntegerField)` | `min_value=1, max_value=1` | field / model | `backend/apps/makerspaces/public_page_contract.py:59` |
| `Document.cover_asset_id (s.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/public_page_contract.py:61` |
| `Palette.fill (s.ListField)` | `min_length=3, max_length=3` | field / model | `backend/apps/makerspaces/public_page_presentation_serializers.py:51` |
| `Palette.foreground (s.ListField)` | `min_length=3, max_length=3` | field / model | `backend/apps/makerspaces/public_page_presentation_serializers.py:52` |
| `Palette.hover (s.ListField)` | `min_length=3, max_length=3` | field / model | `backend/apps/makerspaces/public_page_presentation_serializers.py:53` |
| `Palette.active (s.ListField)` | `min_length=3, max_length=3` | field / model | `backend/apps/makerspaces/public_page_presentation_serializers.py:54` |
| `Palette.soft (s.ListField)` | `min_length=3, max_length=3` | field / model | `backend/apps/makerspaces/public_page_presentation_serializers.py:55` |
| `Palette.ink (s.ListField)` | `min_length=3, max_length=3` | field / model | `backend/apps/makerspaces/public_page_presentation_serializers.py:56` |
| `ProjectedDocument.schema_version (s.IntegerField)` | `min_value=1, max_value=1` | field / model | `backend/apps/makerspaces/public_page_projected_serializers.py:218` |
| `URL.super().__init__` | `max_length=500` | field / model | `backend/apps/makerspaces/public_page_sections.py:23` |
| `Titled.title (s.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/public_page_sections.py:30` |
| `About.markdown (s.CharField)` | `max_length=10000` | field / model | `backend/apps/makerspaces/public_page_sections.py:34` |
| `GalleryItem.asset_id (s.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/public_page_sections.py:41` |
| `GalleryItem.caption (s.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/public_page_sections.py:42` |
| `Gallery.items (GalleryItem)` | `max_length=24` | field / model | `backend/apps/makerspaces/public_page_sections.py:46` |
| `TeamEntry.role (s.CharField)` | `max_length=120` | field / model | `backend/apps/makerspaces/public_page_sections.py:52` |
| `TeamEntry.display_name (s.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/public_page_sections.py:53` |
| `TeamEntry.profile_id (s.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/public_page_sections.py:55` |
| `Team.entries (TeamEntry)` | `max_length=40` | field / model | `backend/apps/makerspaces/public_page_sections.py:68` |
| `Testimonial.quote (s.CharField)` | `max_length=2000` | field / model | `backend/apps/makerspaces/public_page_sections.py:73` |
| `Testimonial.attribution (s.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/public_page_sections.py:74` |
| `Testimonials.entries (Testimonial)` | `max_length=20` | field / model | `backend/apps/makerspaces/public_page_sections.py:78` |
| `Link.label (s.CharField)` | `max_length=80` | field / model | `backend/apps/makerspaces/public_page_sections.py:84` |
| `Links.entries (Link)` | `max_length=20` | field / model | `backend/apps/makerspaces/public_page_sections.py:100` |
| `Location.address (s.CharField)` | `max_length=500` | field / model | `backend/apps/makerspaces/public_page_sections.py:112` |
| `Location.latitude (s.FloatField)` | `min_value=-90, max_value=90` | field / model | `backend/apps/makerspaces/public_page_sections.py:114` |
| `Location.longitude (s.FloatField)` | `min_value=-180, max_value=180` | field / model | `backend/apps/makerspaces/public_page_sections.py:115` |
| `Location.directions (s.CharField)` | `max_length=2000` | field / model | `backend/apps/makerspaces/public_page_sections.py:116` |
| `VersionInput.version (s.IntegerField)` | `min_value=0` | field / model | `backend/apps/makerspaces/public_page_serializers.py:11` |
| `HandleInput.handle (s.CharField)` | `max_length=30` | field / model | `backend/apps/makerspaces/public_page_serializers.py:23` |
| `PageEventQuery.events_page (s.IntegerField)` | `min_value=1; default=1` | field / model | `backend/apps/makerspaces/public_page_serializers.py:32` |
| `AssetUploadInput.alt_text (s.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/public_page_serializers.py:53` |
| `HttpsLinkSerializer.kind (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/public_profile_validation.py:10` |
| `HttpsLinkSerializer.url (serializers.URLField)` | `max_length=500` | field / model | `backend/apps/makerspaces/public_profile_validation.py:11` |
| `SkillSerializer.name (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/public_profile_validation.py:21` |
| `SkillSerializer.level (serializers.IntegerField)` | `min_value=1, max_value=3` | field / model | `backend/apps/makerspaces/public_profile_validation.py:22` |
| `PublicationWriteSerializer.domains (serializers.CharField)` | `max_length=60` | field / model | `backend/apps/makerspaces/public_profile_validation.py:35` |
| `PublicationWriteSerializer.domains (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/makerspaces/public_profile_validation.py:35` |
| `PublicationWriteSerializer.skills (SkillSerializer)` | `max_length=30` | field / model | `backend/apps/makerspaces/public_profile_validation.py:36` |
| `PublicationWriteSerializer.links (HttpsLinkSerializer)` | `max_length=10` | field / model | `backend/apps/makerspaces/public_profile_validation.py:37` |
| `MAX_HEADLINE` | `4` | fixed / see setting | `backend/apps/makerspaces/public_stats_settings.py:28` |
| `_KeyListField.super().__init__` | `max_length=limit` | field / model | `backend/apps/makerspaces/public_stats_settings_serializers.py:27` |
| `PublicStatsSettingsSerializer.tv_refresh_seconds (serializers.IntegerField)` | `min_value=group.TV_REFRESH_MIN, max_value=group.TV_REFRESH_MAX` | field / model | `backend/apps/makerspaces/public_stats_settings_serializers.py:67` |
| `ResourceStaffGrantInvite.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/resource_grants_models.py:56` |
| `ResourceStaffGrantInvite.email_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/makerspaces/resource_grants_models.py:57` |
| `AdmissionSettingsSerializer.vouches_required (serializers.IntegerField)` | `min_value=1, max_value=5` | field / model | `backend/apps/makerspaces/serializers_admission.py:16` |
| `AdmissionSettingsSerializer.voucher_pending_limit (serializers.IntegerField)` | `min_value=1, max_value=100` | field / model | `backend/apps/makerspaces/serializers_admission.py:17` |
| `AdmissionSettingsSerializer.voucher_min_tenure_days (serializers.IntegerField)` | `min_value=0, max_value=3650` | field / model | `backend/apps/makerspaces/serializers_admission.py:18` |
| `AdmissionSettingsSerializer.vouch_expiry_days (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/makerspaces/serializers_admission.py:19` |
| `AdmissionSettingsSerializer.request_expiry_days (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/makerspaces/serializers_admission.py:20` |
| `AdmissionSettingsSerializer.rejoin_after_days (serializers.IntegerField)` | `min_value=1, max_value=3650` | field / model | `backend/apps/makerspaces/serializers_admission.py:23` |
| `PublicAdmissionSerializer.joining_fee (MoneyField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/serializers_admission.py:57` |
| `AdmissionPaymentSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/serializers_admission.py:75` |
| `GuardianTermsInputSerializer.version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_community.py:32` |
| `GuardianTermsInputSerializer.body (serializers.CharField)` | `max_length=20000` | field / model | `backend/apps/makerspaces/serializers_community.py:33` |
| `MinorRecordInputSerializer.date_of_birth (serializers.CharField)` | `max_length=10` | field / model | `backend/apps/makerspaces/serializers_community.py:39` |
| `MinorRecordInputSerializer.guardian_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/serializers_community.py:43` |
| `MinorRecordInputSerializer.guardian_phone (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/makerspaces/serializers_community.py:45` |
| `ConsentInputSerializer.signed_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/serializers_community.py:54` |
| `ConsentInputSerializer.operation_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_community.py:56` |
| `VolunteerLogInputSerializer.minutes (serializers.IntegerField)` | `min_value=1, max_value=1440` | field / model | `backend/apps/makerspaces/serializers_community.py:145` |
| `VolunteerLogInputSerializer.description (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/serializers_community.py:147` |
| `VolunteerDecisionSerializer.note (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/serializers_community.py:152` |
| `VoidInputSerializer.reason (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/serializers_community.py:173` |
| `SponsorInputSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:110` |
| `SponsorInputSerializer.operation_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:111` |
| `RevokeInputSerializer.reason (serializers.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:128` |
| `StaffIssueSerializer.holder_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:161` |
| `StaffIssueSerializer.holder_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:162` |
| `StaffIssueSerializer.sponsor_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:163` |
| `StaffIssueSerializer.operation_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:165` |
| `DeskSaleSerializer.product_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:174` |
| `PurchaseSerializer.operation_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_guest_passes.py:180` |
| `ConsentPurposeInputSerializer.purpose (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_membership_l4.py:31` |
| `ErasureInputSerializer.note (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/makerspaces/serializers_membership_l4.py:43` |
| `RefundSuggestionSerializer.suggested_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/serializers_membership_l4.py:58` |
| `PublicPlanSerializer.renewal_price (MoneyField)` | `max_digits=13` | field / model | `backend/apps/makerspaces/serializers_membership_l4.py:66` |
| `MembershipRequestCreateSerializer.invite_code (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_memberships.py:10` |
| `MembershipRequestCreateSerializer.unit_code (serializers.CharField)` | `max_length=6` | field / model | `backend/apps/makerspaces/serializers_memberships.py:12` |
| `ReferralCreateSerializer.invite_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/makerspaces/serializers_memberships.py:49` |
| `WaiverPublishSerializer.version (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/serializers_memberships.py:91` |
| `GrantsUpdateSerializer.grantee_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/makerspaces/settings_authority_views.py:81` |
| `GrantsUpdateSerializer.grantee_ids (serializers.ListField)` | `max_length=200` | field / model | `backend/apps/makerspaces/settings_authority_views.py:81` |
| `LockUpdateSerializer.setting_key (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/makerspaces/settings_authority_views.py:92` |
| `LockUpdateSerializer.note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/makerspaces/settings_authority_views.py:94` |
| `MAX_BYTES` | `2 * 1024 * 1024` | fixed / see setting | `backend/apps/makerspaces/space_pack_format.py:11` |
| `MAX_ROWS` | `2000` | fixed / see setting | `backend/apps/makerspaces/space_pack_format.py:12` |
| `KioskStationCreateSerializer.name (serializers.CharField)` | `max_length=160` | field / model | `backend/apps/makerspaces/station_serializers.py:15` |
| `KioskStationPinSerializer.makerspace_slug (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/makerspaces/station_serializers.py:48` |
| `ProviderSerializer.site_id (serializers.RegexField)` | `max_length=128` | field / model | `backend/apps/makerspaces/telemetry_schema.py:41` |
| `ProviderSerializer.endpoint (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/makerspaces/telemetry_schema.py:42` |
| `SentrySerializer.dsn (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/makerspaces/telemetry_schema.py:73` |
| `SentrySerializer.sample_rate (serializers.FloatField)` | `min_value=0, max_value=1` | field / model | `backend/apps/makerspaces/telemetry_schema.py:74` |
| `PerformanceSerializer.sample_rate (serializers.FloatField)` | `min_value=0, max_value=1` | field / model | `backend/apps/makerspaces/telemetry_schema.py:98` |
| `FirebaseSerializer.api_key (serializers.RegexField)` | `max_length=128` | field / model | `backend/apps/makerspaces/telemetry_schema.py:112` |
| `FirebaseSerializer.auth_domain (serializers.RegexField)` | `max_length=253` | field / model | `backend/apps/makerspaces/telemetry_schema.py:113` |
| `FirebaseSerializer.project_id (serializers.RegexField)` | `max_length=63` | field / model | `backend/apps/makerspaces/telemetry_schema.py:114` |
| `FirebaseSerializer.app_id (serializers.RegexField)` | `max_length=128` | field / model | `backend/apps/makerspaces/telemetry_schema.py:115` |
| `FirebaseSerializer.messaging_sender_id (serializers.RegexField)` | `max_length=32` | field / model | `backend/apps/makerspaces/telemetry_schema.py:116` |
| `FirebaseSerializer.measurement_id (serializers.RegexField)` | `max_length=32` | field / model | `backend/apps/makerspaces/telemetry_schema.py:117` |
| `FirebaseSerializer.vapid_public_key (serializers.RegexField)` | `max_length=256` | field / model | `backend/apps/makerspaces/telemetry_schema.py:118` |
| `JoinPhotoPresignSerializer.content_type (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/views_admission_changes.py:32` |
| `CapabilityPurgeSerializer.key (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/views_capability_purge.py:38` |
| `CapabilityPurgeSerializer.confirm (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/makerspaces/views_capability_purge.py:39` |
| `InvitationRequestCreateSerializer.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/views_invitation_requests.py:27` |
| `InvitationRequestCreateSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/makerspaces/views_invitation_requests.py:28` |
| `InvitationRequestCreateSerializer.phone (serializers.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/makerspaces/views_invitation_requests.py:29` |
| `InvitationRequestCreateSerializer.message (serializers.CharField)` | `max_length=1000; default=''` | field / model | `backend/apps/makerspaces/views_invitation_requests.py:30` |
| `MembershipReasonSerializer.reason (serializers.CharField)` | `max_length=1000` | field / model | `backend/apps/makerspaces/views_self_service.py:18` |
| `MAX_BYTES` | `5000000` | fixed / see setting | `backend/apps/makerspaces/website_assets.py:24` |
| `MAX_PIXELS` | `16000000` | fixed / see setting | `backend/apps/makerspaces/website_assets.py:25` |
| `MAX_EDGE` | `2048` | fixed / see setting | `backend/apps/makerspaces/website_assets.py:26` |
| `WebsiteOriginsSerializer.origins (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/makerspaces/website_settings_views.py:17` |
| `WebsiteOriginsSerializer.origins (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/makerspaces/website_settings_views.py:17` |
| `DiscoveryFilters.q (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/makerspaces/website_views.py:29` |
| `DiscoveryFilters.tag (serializers.CharField)` | `max_length=50` | field / model | `backend/apps/makerspaces/website_views.py:33` |
| `DiscoveryFilters.organization (serializers.SlugField)` | `max_length=50` | field / model | `backend/apps/makerspaces/website_views.py:34` |

</details>

<details>
<summary>managed_hosting (42 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `HostingPlan.key (models.SlugField)` | `max_length=40` | field / model | `backend/apps/managed_hosting/models.py:25` |
| `HostingPlan.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/managed_hosting/models.py:26` |
| `HostingPlan.description (models.CharField)` | `max_length=500` | field / model | `backend/apps/managed_hosting/models.py:27` |
| `HostingPlan.currency (models.CharField)` | `max_length=3; default='USD'` | field / model | `backend/apps/managed_hosting/models.py:31` |
| `HostingPlan.billing_period (models.CharField)` | `max_length=8; default=Period.MONTHLY` | field / model | `backend/apps/managed_hosting/models.py:33` |
| `HostingInvoice.number (models.CharField)` | `max_length=24` | field / model | `backend/apps/managed_hosting/models.py:72` |
| `HostingInvoice.makerspace_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/managed_hosting/models.py:76` |
| `HostingInvoice.description (models.CharField)` | `max_length=300` | field / model | `backend/apps/managed_hosting/models.py:78` |
| `HostingInvoice.amount_minor (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/managed_hosting/models.py:79` |
| `HostingInvoice.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/managed_hosting/models.py:80` |
| `HostingInvoice.status (models.CharField)` | `max_length=8; default=Status.OPEN` | field / model | `backend/apps/managed_hosting/models.py:84` |
| `HostingInvoice.void_reason (models.CharField)` | `max_length=300` | field / model | `backend/apps/managed_hosting/models.py:87` |
| `HostingInvoice.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/managed_hosting/models.py:88` |
| `HostingInvoice.provider_session_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/managed_hosting/models.py:89` |
| `HostingInvoiceReceipt.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/managed_hosting/models.py:120` |
| `HostingInvoiceReceipt.reference (models.CharField)` | `max_length=200` | field / model | `backend/apps/managed_hosting/models.py:121` |
| `HostingInvoiceReceipt.note (models.CharField)` | `max_length=300` | field / model | `backend/apps/managed_hosting/models.py:124` |
| `PlatformHostingBillingSettings.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/managed_hosting/models.py:149` |
| `PlatformHostingBillingSettings.razorpay_key_id (models.CharField)` | `max_length=100` | field / model | `backend/apps/managed_hosting/models.py:153` |
| `SpaceHostingType.hosting_type (models.CharField)` | `max_length=8; default=Kind.OWN` | field / model | `backend/apps/managed_hosting/models_hosting_type.py:20` |
| `PlatformLimitDefault.key (models.CharField)` | `max_length=64` | field / model | `backend/apps/managed_hosting/models_limit_defaults.py:14` |
| `SpaceLimitThreshold.key (models.CharField)` | `max_length=64` | field / model | `backend/apps/managed_hosting/models_limit_defaults.py:47` |
| `PlatformThrottleRate.scope (models.CharField)` | `max_length=64` | field / model | `backend/apps/managed_hosting/models_throttle.py:12` |
| `PlatformThrottleRate.rate (models.CharField)` | `max_length=16` | field / model | `backend/apps/managed_hosting/models_throttle.py:13` |
| `HostingPlanAssignRequestSerializer.trial_days (serializers.IntegerField)` | `min_value=0, max_value=365; default=None` | field / model | `backend/apps/managed_hosting/serializers.py:44` |
| `HostingInvoiceCreateSerializer.amount_minor (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/managed_hosting/serializers.py:94` |
| `HostingInvoiceCreateSerializer.description (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/managed_hosting/serializers.py:96` |
| `HostingInvoicePaymentSerializer.reference (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/managed_hosting/serializers.py:104` |
| `HostingInvoicePaymentSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/managed_hosting/serializers.py:106` |
| `HostingInvoiceVoidSerializer.reason (serializers.CharField)` | `min_length=3, max_length=300` | field / model | `backend/apps/managed_hosting/serializers.py:110` |
| `HostingBillingSettingsSerializer.provider (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/managed_hosting/serializers.py:115` |
| `SPACE_QUOTA_KEYS` | `frozenset({'events_monthly', 'bookings_monthly', 'payments_monthly_count', 'payments_monthly_amount'})` | fixed / see setting | `backend/apps/managed_hosting/space_quotas.py:20` |
| `MAX_FACTOR` | `10` | fixed / see setting | `backend/apps/managed_hosting/throttle_rates.py:20` |
| `ABSOLUTE_MAX_PER_SECOND` | `1000` | fixed / see setting | `backend/apps/managed_hosting/throttle_rates.py:21` |
| `MAX_DEFAULT` | `2 ** 63 - 1` | fixed / see setting | `backend/apps/managed_hosting/views_limit_defaults.py:55` |
| `RequestRateUpdateSerializer.rate (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/managed_hosting/views_limits.py:104` |
| `BulkLimitsSerializer.makerspace_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/managed_hosting/views_limits_bulk.py:22` |
| `BulkLimitsSerializer.makerspace_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/managed_hosting/views_limits_bulk.py:22` |
| `BulkPlanAssignSerializer.makerspace_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/managed_hosting/views_platform.py:177` |
| `BulkPlanAssignSerializer.makerspace_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/managed_hosting/views_platform.py:177` |
| `BulkPlanAssignSerializer.plan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/managed_hosting/views_platform.py:178` |
| `BulkPlanAssignSerializer.trial_days (serializers.IntegerField)` | `min_value=0, max_value=365; default=None` | field / model | `backend/apps/managed_hosting/views_platform.py:179` |

</details>

<details>
<summary>notifications (32 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_FAILURES` | `5` | fixed / see setting | `backend/apps/notifications/browser_alerts.py:31` |
| `MAX_ATTEMPTS` | `4` | fixed / see setting | `backend/apps/notifications/envelope_push_leases.py:8` |
| `MAX_ATTEMPTS` | `5` | fixed / see setting | `backend/apps/notifications/member_push_leases.py:9` |
| `Notification.level (models.CharField)` | `max_length=16; default=Level.INFO` | field / model | `backend/apps/notifications/models.py:23` |
| `Notification.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/notifications/models.py:24` |
| `Notification.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/notifications/models.py:25` |
| `Notification.url_path (models.CharField)` | `max_length=300` | field / model | `backend/apps/notifications/models.py:27` |
| `BrowserAlertSubscription.endpoint_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/notifications/models_browser_alerts.py:19` |
| `BrowserAlertSubscription.p256dh (models.CharField)` | `max_length=128` | field / model | `backend/apps/notifications/models_browser_alerts.py:20` |
| `NotificationEscalation.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/notifications/models_browser_alerts.py:48` |
| `NotificationEscalation.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/notifications/models_browser_alerts.py:49` |
| `BrowserFirebaseInstallation.fid_hmac (models.CharField)` | `max_length=64` | field / model | `backend/apps/notifications/models_browser_firebase.py:10` |
| `BrowserFirebaseRegistration.project_id (models.CharField)` | `max_length=63` | field / model | `backend/apps/notifications/models_browser_firebase.py:22` |
| `BrowserFirebaseRegistration.fid_hmac (models.CharField)` | `max_length=64` | field / model | `backend/apps/notifications/models_browser_firebase.py:24` |
| `NotificationInboxRow.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/notifications/models_inbox.py:17` |
| `NotificationInboxRow.event (models.CharField)` | `max_length=64` | field / model | `backend/apps/notifications/models_inbox.py:18` |
| `NotificationInboxRow.audience (models.CharField)` | `max_length=8; default=Audience.STAFF` | field / model | `backend/apps/notifications/models_inbox.py:21` |
| `NotificationInboxRow.link (models.CharField)` | `max_length=300` | field / model | `backend/apps/notifications/models_inbox.py:25` |
| `MemberNotificationPreference.feature (models.CharField)` | `max_length=32` | field / model | `backend/apps/notifications/models_inbox.py:46` |
| `MemberNotificationPreference.channel (models.CharField)` | `max_length=16` | field / model | `backend/apps/notifications/models_inbox.py:47` |
| `NotificationPreference.category (models.CharField)` | `max_length=32` | field / model | `backend/apps/notifications/models_preferences.py:9` |
| `MemberPushDelivery.platform (models.CharField)` | `max_length=16` | field / model | `backend/apps/notifications/models_push.py:23` |
| `MemberPushDelivery.provider_source (models.CharField)` | `max_length=8` | field / model | `backend/apps/notifications/models_push.py:24` |
| `MemberPushDelivery.status (models.CharField)` | `max_length=8; default=Status.PENDING` | field / model | `backend/apps/notifications/models_push.py:25` |
| `MemberPushDelivery.last_error (models.CharField)` | `max_length=200` | field / model | `backend/apps/notifications/models_push.py:31` |
| `BroadcastInputSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/notifications/serializers_broadcasts.py:7` |
| `BroadcastInputSerializer.body (serializers.CharField)` | `max_length=12000` | field / model | `backend/apps/notifications/serializers_broadcasts.py:8` |
| `BroadcastInputSerializer.plan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/notifications/serializers_broadcasts.py:9` |
| `BroadcastInputSerializer.machine_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/notifications/serializers_broadcasts.py:11` |
| `SubscriptionWriteSerializer.endpoint (serializers.URLField)` | `max_length=1024` | field / model | `backend/apps/notifications/views_browser_alerts.py:33` |
| `SubscriptionStateSerializer.subscribed_browsers (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/notifications/views_browser_alerts.py:38` |
| `MAX_SNOOZE` | `timedelta(days=30)` | fixed / see setting | `backend/apps/notifications/views_inbox_snooze.py:26` |

</details>

<details>
<summary>operations (240 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `StockTransferAdminForm.quantity (forms.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/admin_forms.py:27` |
| `StocktakeCountAdminForm.counted_quantity (forms.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/admin_forms.py:102` |
| `ITEM_CAP` | `500` | fixed / see setting | `backend/apps/operations/area_tree.py:16` |
| `MAX_ROWS` | `500` | fixed / see setting | `backend/apps/operations/cloud_jobs/admission.py:12` |
| `MAX_LOGICAL_BYTES` | `2 * 1024 * 1024` | fixed / see setting | `backend/apps/operations/cloud_jobs/admission.py:13` |
| `MAX_ARCHIVE_FILES` | `512` | fixed / see setting | `backend/apps/operations/cloud_jobs/admission.py:14` |
| `MAX_OBJECTS` | `4` | fixed / see setting | `backend/apps/operations/cloud_jobs/admission.py:15` |
| `MAX_TICK_BODY_BYTES` | `1024` | fixed / see setting | `backend/apps/operations/cloud_jobs/tick_views.py:18` |
| `TickResponseSerializer.completed (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/cloud_jobs/tick_views.py:62` |
| `TickResponseSerializer.deferred (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/cloud_jobs/tick_views.py:63` |
| `TickResponseSerializer.failed (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/cloud_jobs/tick_views.py:64` |
| `TickResponseSerializer.reasons (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/cloud_jobs/tick_views.py:65` |
| `MAX_SUBJECTS` | `40` | fixed / see setting | `backend/apps/operations/consumable_shortages.py:26` |
| `MAX_LENGTH` | `50000` | fixed / see setting | `backend/apps/operations/legal_pages.py:13` |
| `StockTransfer.status (models.CharField)` | `max_length=20; default=Status.APPLIED` | field / model | `backend/apps/operations/models.py:37` |
| `StockTransferLine.from_status (models.CharField)` | `max_length=32` | field / model | `backend/apps/operations/models.py:55` |
| `StockTransferLine.to_status (models.CharField)` | `max_length=32` | field / model | `backend/apps/operations/models.py:56` |
| `StocktakeSession.status (models.CharField)` | `max_length=20; default=Status.COUNTING` | field / model | `backend/apps/operations/models.py:81` |
| `StocktakeLine.condition (models.CharField)` | `max_length=20; default=Condition.AVAILABLE` | field / model | `backend/apps/operations/models.py:112` |
| `StocktakeLedgerEntry.bucket (models.CharField)` | `max_length=20` | field / model | `backend/apps/operations/models.py:160` |
| `StocktakeLedgerEntry.old_asset_status (models.CharField)` | `max_length=20` | field / model | `backend/apps/operations/models.py:162` |
| `StocktakeLedgerEntry.new_asset_status (models.CharField)` | `max_length=20` | field / model | `backend/apps/operations/models.py:163` |
| `QrPrintBatch.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/operations/models.py:188` |
| `QrPrintBatch.status (models.CharField)` | `max_length=20; default=Status.DRAFT` | field / model | `backend/apps/operations/models.py:189` |
| `QrPrintBatchItem.label_text (models.CharField)` | `max_length=255` | field / model | `backend/apps/operations/models.py:209` |
| `QrPrintBatchItem.target_type (models.CharField)` | `max_length=20` | field / model | `backend/apps/operations/models.py:210` |
| `CloudEmailBudgetAccount.key (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_cloud_email.py:6` |
| `CloudEmailBudgetAccount.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/operations/models_cloud_email.py:7` |
| `CloudEmailBudgetAccount.reset_timezone (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_email.py:8` |
| `CloudEmailReservation.attempt_key (models.CharField)` | `max_length=200` | field / model | `backend/apps/operations/models_cloud_email.py:14` |
| `CloudEmailReservation.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/operations/models_cloud_email.py:15` |
| `CloudEmailReservation.state (models.CharField)` | `max_length=12` | field / model | `backend/apps/operations/models_cloud_email.py:21` |
| `CloudEmailReservation.provider_message_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/operations/models_cloud_email.py:24` |
| `CloudTaskState.key (models.CharField)` | `max_length=100` | field / model | `backend/apps/operations/models_cloud_jobs.py:9` |
| `CloudTaskState.status (models.CharField)` | `max_length=16; default='idle'` | field / model | `backend/apps/operations/models_cloud_jobs.py:12` |
| `CloudTaskState.failure_code (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/operations/models_cloud_jobs.py:18` |
| `CloudTickRun.status (models.CharField)` | `max_length=16; default='running'` | field / model | `backend/apps/operations/models_cloud_jobs.py:38` |
| `CloudTickRateWindow.key (models.CharField)` | `max_length=32` | field / model | `backend/apps/operations/models_cloud_jobs.py:57` |
| `CloudUsageSample.metric (models.CharField)` | `max_length=16` | field / model | `backend/apps/operations/models_cloud_usage.py:8` |
| `CloudUsageSample.scope (models.CharField)` | `max_length=16` | field / model | `backend/apps/operations/models_cloud_usage.py:10` |
| `CloudUsageSample.source (models.CharField)` | `max_length=100` | field / model | `backend/apps/operations/models_cloud_usage.py:14` |
| `CloudUsageSample.reason_code (models.CharField)` | `max_length=100` | field / model | `backend/apps/operations/models_cloud_usage.py:15` |
| `CloudUsageSample.cap_source (models.CharField)` | `max_length=200` | field / model | `backend/apps/operations/models_cloud_usage.py:18` |
| `CloudObjectUsageReceipt.operation_key (models.CharField)` | `max_length=128` | field / model | `backend/apps/operations/models_cloud_usage.py:27` |
| `CloudObjectUsageReceipt.bucket_alias (models.CharField)` | `max_length=100` | field / model | `backend/apps/operations/models_cloud_usage.py:29` |
| `CloudObjectUsageReceipt.object_key_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_usage.py:30` |
| `CloudObjectUsageReceipt.generation (models.CharField)` | `max_length=100` | field / model | `backend/apps/operations/models_cloud_usage.py:31` |
| `CloudObjectUsageReceipt.operation (models.CharField)` | `max_length=16` | field / model | `backend/apps/operations/models_cloud_usage.py:33` |
| `CloudObjectAccount.identity (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_usage.py:38` |
| `CloudObjectAccount.reason (models.CharField)` | `max_length=100; default='storage_usage_unverified'` | field / model | `backend/apps/operations/models_cloud_usage.py:45` |
| `CloudObjectReservation.key (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_usage.py:49` |
| `CloudObjectReservation.state (models.CharField)` | `max_length=16; default='reserved'` | field / model | `backend/apps/operations/models_cloud_usage.py:55` |
| `CloudStorageMigrationReceipt.role (models.CharField)` | `max_length=128` | field / model | `backend/apps/operations/models_cloud_usage.py:61` |
| `CloudStorageMigrationReceipt.source_identity (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_usage.py:62` |
| `CloudStorageMigrationReceipt.destination_identity (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_usage.py:63` |
| `CloudStorageMigrationReceipt.inventory_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_cloud_usage.py:64` |
| `ReminderSchedule.source (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_reminders.py:16` |
| `ReminderSchedule.subject (models.CharField)` | `max_length=160` | field / model | `backend/apps/operations/models_reminders.py:17` |
| `ReminderSchedule.kind (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_reminders.py:18` |
| `ReminderSchedule.state (models.CharField)` | `max_length=16; default=State.PENDING` | field / model | `backend/apps/operations/models_reminders.py:22` |
| `MAX_RECIPIENT_EMAILS` | `10` | fixed / see setting | `backend/apps/operations/models_report_schedules.py:19` |
| `ReportSchedule.report_key (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_report_schedules.py:73` |
| `ReportSchedule.grain (models.CharField)` | `max_length=8; default='day'` | field / model | `backend/apps/operations/models_report_schedules.py:75` |
| `ReportSchedule.format (models.CharField)` | `max_length=8; default=Format.CSV` | field / model | `backend/apps/operations/models_report_schedules.py:76` |
| `ReportSchedule.cadence (models.CharField)` | `max_length=8; default=Cadence.WEEKLY` | field / model | `backend/apps/operations/models_report_schedules.py:77` |
| `ReportDelivery.object_key (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/operations/models_report_schedules.py:118` |
| `ReportDelivery.status (models.CharField)` | `max_length=8` | field / model | `backend/apps/operations/models_report_schedules.py:119` |
| `ReportMetricRollup.source_module (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_rollups.py:33` |
| `ReportMetricRollup.report_key (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_rollups.py:34` |
| `ReportMetricRollup.metric_key (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_rollups.py:35` |
| `ReportMetricRollup.grain (models.CharField)` | `max_length=8` | field / model | `backend/apps/operations/models_rollups.py:37` |
| `ReportMetricRollup.dimension_key (models.CharField)` | `max_length=128` | field / model | `backend/apps/operations/models_rollups.py:38` |
| `ReportMetricRollup.value (models.DecimalField)` | `max_digits=28` | field / model | `backend/apps/operations/models_rollups.py:40` |
| `ReportMetricRollup.checksum (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_rollups.py:45` |
| `ReportRollupCursor.source_module (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_rollups.py:73` |
| `ReportRollupCursor.last_error_code (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/operations/models_rollups.py:76` |
| `SavedView.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/operations/models_saved_views.py:10` |
| `SavedView.entity (models.CharField)` | `max_length=24` | field / model | `backend/apps/operations/models_saved_views.py:11` |
| `PeriodicTaskRun.name (models.CharField)` | `max_length=100` | field / model | `backend/apps/operations/models_scheduling.py:17` |
| `PeriodicTaskRun.last_error (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/operations/models_scheduling.py:19` |
| `StocktakeSchedule.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/operations/models_stocktake_discipline.py:15` |
| `StocktakeSchedule.interval_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/operations/models_stocktake_discipline.py:16` |
| `StorageCapabilityState.identity_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_storage_capabilities.py:6` |
| `StorageCapabilityState.logical_role (models.CharField)` | `max_length=128` | field / model | `backend/apps/operations/models_storage_capabilities.py:8` |
| `StorageCapabilityState.configuration_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/operations/models_storage_capabilities.py:10` |
| `MAX_ORGANIZATION_SCOPE_SPACES` | `25` | fixed / see setting | `backend/apps/operations/org_reports.py:93` |
| `GrowthSerializer.accounts (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:94` |
| `GrowthSerializer.makerspaces (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:95` |
| `MfaSerializer.active (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:99` |
| `MfaSerializer.enabled (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:100` |
| `MfaSerializer.without_mfa (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:101` |
| `OutboxHealthSerializer.pending (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:107` |
| `OutboxHealthSerializer.failed (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:108` |
| `OrganizationInsightSerializer.events (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:115` |
| `OrganizationInsightSerializer.registrations (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:116` |
| `OrganizationInsightSerializer.attended (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/platform_insights.py:117` |
| `MAX_CUSTOM_DAYS` | `3660` | fixed / see setting | `backend/apps/operations/platform_overview_window.py:18` |
| `PositionedElementSerializer.field (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/operations/printable_serializers.py:20` |
| `PositionedElementSerializer.x_mm (serializers.FloatField)` | `min_value=0` | field / model | `backend/apps/operations/printable_serializers.py:21` |
| `PositionedElementSerializer.y_mm (serializers.FloatField)` | `min_value=0` | field / model | `backend/apps/operations/printable_serializers.py:22` |
| `PositionedElementSerializer.width_mm (serializers.FloatField)` | `min_value=0.5` | field / model | `backend/apps/operations/printable_serializers.py:23` |
| `PositionedElementSerializer.height_mm (serializers.FloatField)` | `min_value=0.5` | field / model | `backend/apps/operations/printable_serializers.py:24` |
| `PositionedElementSerializer.font_size_pt (serializers.FloatField)` | `min_value=6, max_value=48` | field / model | `backend/apps/operations/printable_serializers.py:26` |
| `RetentionFilterSerializer.months (serializers.IntegerField)` | `min_value=1, max_value=120` | field / model | `backend/apps/operations/report_request_contract.py:19` |
| `ReportConditionSerializer.metric (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/operations/report_schedule_rules.py:23` |
| `ReportConditionSerializer.value (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/report_schedule_rules.py:25` |
| `SubjectFilterSerializer.subject_kind (serializers.CharField)` | `max_length=48` | field / model | `backend/apps/operations/report_subjects.py:38` |
| `SubjectFilterSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/report_subjects.py:39` |
| `DEFAULT_REPORT_LIMIT` | `100` | fixed / see setting | `backend/apps/operations/reports.py:29` |
| `MAX_REPORT_LIMIT` | `500` | fixed / see setting | `backend/apps/operations/reports.py:30` |
| `MAX_AUDIT_EXPORT_ROWS` | `10000` | fixed / see setting | `backend/apps/operations/reports_audit.py:16` |
| `_machine_rows.rows (DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/reports_health.py:180` |
| `_maintenance_rows.rows (DecimalField)` | `max_digits=21` | field / model | `backend/apps/operations/reports_health.py:194` |
| `build_machine_usage.queryset (DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/reports_machine_usage.py:28` |
| `build_maintenance_activity.qs (DecimalField)` | `max_digits=21` | field / model | `backend/apps/operations/reports_maintenance.py:57` |
| `build_maintenance_activity.qs (DecimalField)` | `max_digits=21` | field / model | `backend/apps/operations/reports_maintenance.py:58` |
| `build_payment_reconciliation.money (DecimalField)` | `max_digits=21` | field / model | `backend/apps/operations/reports_payments.py:67` |
| `B2CL_LIMIT` | `Decimal('100000')` | fixed / see setting | `backend/apps/operations/reports_tax_gst.py:19` |
| `MAX_DAYS` | `62` | fixed / see setting | `backend/apps/operations/schedule.py:19` |
| `MAX_ENTRIES` | `500` | fixed / see setting | `backend/apps/operations/schedule.py:19` |
| `StockTransferLineInputSerializer.quantity (serializers.IntegerField)` | `min_value=1; default=1` | field / model | `backend/apps/operations/serializers.py:116` |
| `AssetGenerateSerializer.count (serializers.IntegerField)` | `min_value=1, max_value=200` | field / model | `backend/apps/operations/serializers.py:182` |
| `QrPrintBatchCreateSerializer.title (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/operations/serializers.py:211` |
| `QrPrintBatchItemCreateSerializer.label_text (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/operations/serializers.py:216` |
| `QrPrintBatchItemCreateSerializer.sort_order (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers.py:217` |
| `InsightsActivitySerializer.events_held (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:13` |
| `InsightsActivitySerializer.registrations (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:14` |
| `InsightsActivitySerializer.check_ins (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:15` |
| `InsightsActivitySerializer.feedback_responses (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:16` |
| `InsightsActivitySerializer.broadcasts_sent (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:17` |
| `InsightsLoginMethodSerializer.accounts (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:23` |
| `InsightsSensitiveActionSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:28` |
| `InsightsApiClientLifecycleSerializer.active (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:32` |
| `InsightsApiClientLifecycleSerializer.revoked (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:33` |
| `InsightsApiClientLifecycleSerializer.rotating (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:34` |
| `InsightsApiClientLifecycleSerializer.unused_in_window (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:35` |
| `InsightsSecuritySerializer.accounts_unverified (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:39` |
| `InsightsSecuritySerializer.accounts_with_passkey (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:40` |
| `InsightsStorageSerializer.total_bytes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:47` |
| `InsightsStorageSerializer.spaces (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:48` |
| `InsightsStorageSerializer.largest_bytes (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_insights_wide.py:49` |
| `OverviewPlatformMetricSerializer.value (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:26` |
| `OverviewBlockSerializer.on_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:39` |
| `OverviewBlockSerializer.off_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:40` |
| `OverviewHiddenBlockSerializer.on_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:52` |
| `OverviewHiddenBlockSerializer.off_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:53` |
| `OverviewMoneyFiguresSerializer.charges (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:57` |
| `OverviewMoneyFiguresSerializer.amounts (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/serializers_platform_overview.py:58` |
| `OverviewCurrencySerializer.currency (serializers.CharField)` | `max_length=3` | field / model | `backend/apps/operations/serializers_platform_overview.py:66` |
| `OverviewModuleSerializer.on_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:88` |
| `OverviewModuleSerializer.off_in (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:89` |
| `PlatformOverviewSerializer.excluded_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_platform_overview.py:98` |
| `PlatformOverviewComputingSerializer.retry_after_seconds (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/serializers_platform_overview.py:111` |
| `ProblemReportTriageResolutionSerializer.quantity (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/serializers_problem_reports.py:7` |
| `ReportChartTruncationSerializer.top_n (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/serializers_report_chart.py:19` |
| `ReportScheduleFiltersSerializer.window_days (serializers.IntegerField)` | `min_value=1, max_value=366` | field / model | `backend/apps/operations/serializers_report_schedules.py:33` |
| `ReportScheduleFiltersSerializer.months (serializers.IntegerField)` | `min_value=1, max_value=120` | field / model | `backend/apps/operations/serializers_report_schedules.py:36` |
| `ReportScheduleFiltersSerializer.subject_kind (serializers.CharField)` | `max_length=48` | field / model | `backend/apps/operations/serializers_report_schedules.py:37` |
| `ReportScheduleFiltersSerializer.subject_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/serializers_report_schedules.py:38` |
| `ReportScheduleSerializer.recipient_roles (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/operations/serializers_report_schedules.py:88` |
| `ReportScheduleSerializer.recipient_roles (serializers.SlugField)` | `max_length=80` | field / model | `backend/apps/operations/serializers_report_schedules.py:88` |
| `ReportScheduleSerializer.recipient_actions (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/operations/serializers_report_schedules.py:89` |
| `ReportScheduleSerializer.recipient_emails (serializers.ListField)` | `max_length=MAX_RECIPIENT_EMAILS` | field / model | `backend/apps/operations/serializers_report_schedules.py:91` |
| `ReportViewStateSerializer.grain (serializers.CharField)` | `max_length=8` | field / model | `backend/apps/operations/serializers_report_views.py:15` |
| `ReportViewStateSerializer.columns (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/operations/serializers_report_views.py:16` |
| `ReportViewStateSerializer.columns (serializers.ListField)` | `max_length=100; default=list` | field / model | `backend/apps/operations/serializers_report_views.py:16` |
| `ActiveLoansReportRowSerializer.count (serializers.IntegerField)` | `min_value=1, max_value=1` | field / model | `backend/apps/operations/serializers_reports.py:15` |
| `ReturnsReportRowSerializer.count (serializers.IntegerField)` | `min_value=1, max_value=1` | field / model | `backend/apps/operations/serializers_reports.py:23` |
| `QrScansReportRowSerializer.hour_of_week (serializers.IntegerField)` | `min_value=0, max_value=167` | field / model | `backend/apps/operations/serializers_reports.py:47` |
| `AuditReportFilterSerializer.action (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/operations/serializers_reports_audit.py:7` |
| `AuditReportFilterSerializer.target_type (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/operations/serializers_reports_audit.py:8` |
| `AuditReportFilterSerializer.target_id (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/operations/serializers_reports_audit.py:9` |
| `AuditReportFilterSerializer.actor (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/serializers_reports_audit.py:10` |
| `BookingOccupancyRowSerializer.weekday (serializers.IntegerField)` | `min_value=0, max_value=6` | field / model | `backend/apps/operations/serializers_reports_de.py:22` |
| `BookingOccupancyRowSerializer.hour (serializers.IntegerField)` | `min_value=0, max_value=23` | field / model | `backend/apps/operations/serializers_reports_de.py:23` |
| `BookingOccupancyRowSerializer.occupied_hours (serializers.DecimalField)` | `max_digits=24` | field / model | `backend/apps/operations/serializers_reports_de.py:24` |
| `BookingOccupancyRowSerializer.window_hours (serializers.DecimalField)` | `max_digits=24` | field / model | `backend/apps/operations/serializers_reports_de.py:25` |
| `BookingTopMemberRowSerializer.reserved_hours (serializers.DecimalField)` | `max_digits=24` | field / model | `backend/apps/operations/serializers_reports_de.py:38` |
| `EventRevenueRowSerializer.charged_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_de.py:54` |
| `EventRevenueRowSerializer.promo_discount_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_de.py:55` |
| `EventRevenueRowSerializer.collected_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_de.py:56` |
| `EventRevenueRowSerializer.refunded_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_de.py:57` |
| `EventRevenueRowSerializer.outstanding_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_de.py:58` |
| `EventRevenueRowSerializer.net_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_de.py:59` |
| `EventFeedbackScoresRowSerializer.score_total (serializers.DecimalField)` | `max_digits=24` | field / model | `backend/apps/operations/serializers_reports_de.py:78` |
| `EventFeedbackScoresRowSerializer.average_score (serializers.DecimalField)` | `max_digits=24` | field / model | `backend/apps/operations/serializers_reports_de.py:79` |
| `MachineUsageRowSerializer.usage_hours (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_fablab.py:13` |
| `BookingUtilizationRowSerializer.reserved_hours (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_fablab.py:47` |
| `BookingUtilizationRowSerializer.completed_hours (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_fablab.py:48` |
| `BookingUtilizationRowSerializer.window_hours (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_fablab.py:49` |
| `MaintenanceActivityRowSerializer.total_cost (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_fablab.py:61` |
| `MaintenanceActivityRowSerializer.average_cost (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_fablab.py:62` |
| `FabLabHealthRowSerializer.bookings_reserved_hours (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_fablab.py:81` |
| `FabLabHealthRowSerializer.machines_usage_hours (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_fablab.py:88` |
| `FabLabHealthRowSerializer.maintenance_total_cost (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_fablab.py:92` |
| `FinanceAmountsSerializer.collected_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:10` |
| `FinanceAmountsSerializer.refunded_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:11` |
| `LedgerLineSerializer.amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:24` |
| `LedgerLineSerializer.owed_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:25` |
| `RevenuePeriodSerializer.owed_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:36` |
| `RevenuePeriodSerializer.waived_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:37` |
| `RevenuePeriodSerializer.net_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:38` |
| `CashPeriodSerializer.net_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:44` |
| `JournalLineSerializer.debit (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:55` |
| `JournalLineSerializer.credit (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_finance.py:56` |
| `PaymentAgeingRowSerializer.outstanding_amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_finance.py:80` |
| `serializers.DecimalField` | `max_digits=24` | field / model | `backend/apps/operations/serializers_reports_machine_analytics.py:9` |
| `MachineHeatmapRow.weekday (serializers.IntegerField)` | `min_value=0, max_value=6` | field / model | `backend/apps/operations/serializers_reports_machine_analytics.py:43` |
| `MachineHeatmapRow.hour (serializers.IntegerField)` | `min_value=0, max_value=23` | field / model | `backend/apps/operations/serializers_reports_machine_analytics.py:44` |
| `MemberRetentionRowSerializer.retention_percent (serializers.DecimalField)` | `max_digits=20` | field / model | `backend/apps/operations/serializers_reports_membership.py:13` |
| `MembershipRevenueRowSerializer.mrr (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_membership.py:30` |
| `MembershipRevenueRowSerializer.arr (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_membership.py:31` |
| `MembershipRevenueRowSerializer.arpu (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_membership.py:32` |
| `CommunicationCountsSerializer (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_reports_messaging.py:13` |
| `PlatformServicesRowSerializer.count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_reports_messaging.py:49` |
| `PlatformServicesRowSerializer.amount (MoneyField)` | `max_digits=25` | field / model | `backend/apps/operations/serializers_reports_messaging.py:51` |
| `PaymentReconciliationReportRowSerializer.amount_total (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_payments.py:23` |
| `PaymentReconciliationReportRowSerializer.outstanding_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_payments.py:24` |
| `PaymentReconciliationReportRowSerializer.refunded_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_payments.py:26` |
| `PaymentCashBookRowSerializer.collected_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_payments.py:36` |
| `PaymentCashBookRowSerializer.refunded_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_payments.py:37` |
| `PaymentCashBookRowSerializer.net_amount (MoneyField)` | `max_digits=21` | field / model | `backend/apps/operations/serializers_reports_payments.py:38` |
| `SavedViewSerializer.state (serializers.CharField)` | `max_length=250` | field / model | `backend/apps/operations/serializers_saved_views.py:12` |
| `StocktakeLineInputSerializer.counted_quantity (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/operations/serializers_stocktake.py:16` |
| `StocktakeScanInputSerializer.payload (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/operations/serializers_stocktake.py:27` |
| `AreaMoneySerializer.amount (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:39` |
| `AreaFinanceTotalsSerializer.income (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:44` |
| `AreaFinanceTotalsSerializer.other_income (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:45` |
| `AreaFinanceTotalsSerializer.refunds (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:46` |
| `AreaFinanceTotalsSerializer.expenses (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:47` |
| `AreaFinanceTotalsSerializer.owed (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:48` |
| `AreaFinanceTotalsSerializer.money_in (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:49` |
| `AreaFinanceTotalsSerializer.payouts (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:50` |
| `AreaFinanceTotalsSerializer.money_out (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:52` |
| `AreaFinanceTotalsSerializer.net (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:53` |
| `AreaItemSerializer.amount (MoneyField)` | `max_digits=17` | field / model | `backend/apps/operations/views_area_overview.py:65` |
| `LegalPageWriteSerializer.markdown (serializers.CharField)` | `max_length=legal_pages.MAX_LENGTH` | field / model | `backend/apps/operations/views_legal.py:35` |
| `LegalPageWriteSerializer.language (serializers.RegexField)` | `max_length=16; default=''` | field / model | `backend/apps/operations/views_legal.py:36` |
| `MAX_STREAM_SECONDS` | `60 * 60` | fixed / see setting | `backend/apps/operations/views_live.py:30` |
| `ScheduleSerializer.interval_days (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/operations/views_stocktake_discipline.py:49` |

</details>

<details>
<summary>organizations (25 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `LeaveInput.expected_version (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/organizations/member_leave.py:91` |
| `Organization.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/organizations/models.py:17` |
| `Organization.legal_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/organizations/models.py:19` |
| `Organization.registration_number (models.CharField)` | `max_length=100` | field / model | `backend/apps/organizations/models.py:20` |
| `Organization.logo_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/organizations/models.py:23` |
| `Organization.review_status (models.CharField)` | `max_length=24; default=ReviewStatus.APPROVED` | field / model | `backend/apps/organizations/models.py:36` |
| `OrganizationMakerspace.relationship (models.CharField)` | `max_length=16` | field / model | `backend/apps/organizations/models.py:89` |
| `OrganizationMembership.status (models.CharField)` | `max_length=16; default=Status.ACTIVE` | field / model | `backend/apps/organizations/models.py:134` |
| `OrganizationInvitation.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/organizations/models.py:173` |
| `OrganizationInvitation.invitee_email_digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/organizations/models.py:175` |
| `OrganizationPublicPageAsset.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/organizations/models_public_pages.py:30` |
| `OrganizationPublicPageAsset.alt_text (models.CharField)` | `max_length=200` | field / model | `backend/apps/organizations/models_public_pages.py:32` |
| `OrganizationPublicPageRevisionAsset.slot (models.CharField)` | `max_length=80` | field / model | `backend/apps/organizations/models_public_pages.py:40` |
| `OrganizationReview.action (models.CharField)` | `max_length=24` | field / model | `backend/apps/organizations/models_review.py:24` |
| `OrganizationInvitationCreateSerializer.expires_in_days (serializers.IntegerField)` | `min_value=1, max_value=30; default=7` | field / model | `backend/apps/organizations/serializers_admin.py:149` |
| `OrganizationInvitationCreateSerializer.invitee_email (serializers.EmailField)` | `max_length=254; default=''` | field / model | `backend/apps/organizations/serializers_admin.py:150` |
| `OrganizationInvitationRedeemSerializer.token (serializers.CharField)` | `min_length=20, max_length=200` | field / model | `backend/apps/organizations/serializers_admin.py:164` |
| `MAX_EXPIRY_DAYS` | `30` | fixed / see setting | `backend/apps/organizations/services_invitations.py:32` |
| `serializers.CharField` | `max_length=200` | field / model | `backend/apps/organizations/services_owner.py:58` |
| `serializers.IntegerField` | `min_value=1` | field / model | `backend/apps/organizations/services_owner.py:59` |
| `OrganizationLinkWriteSerializer.makerspace_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/organizations/views_console.py:22` |
| `ReviewDecisionSerializer.reason (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/organizations/views_review.py:51` |
| `ReviewResubmitSerializer.note (serializers.CharField)` | `max_length=2000` | field / model | `backend/apps/organizations/views_review.py:55` |
| `OrganizationSelfCreateSerializer.description (serializers.CharField)` | `max_length=10000` | field / model | `backend/apps/organizations/views_self_service.py:15` |
| `EVENT_LIMIT` | `12` | fixed / see setting | `backend/apps/organizations/workspace_payload.py:13` |

</details>

<details>
<summary>payments (493 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `MAX_ROWS` | `200` | fixed / see setting | `backend/apps/payments/collection_sheet.py:26` |
| `MAX_PDF_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/payments/document_delivery.py:14` |
| `MAX_PDF_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/payments/document_pdf.py:7` |
| `MAX_SOURCE_BYTES` | `5 * 1024 * 1024` | fixed / see setting | `backend/apps/payments/document_pdf_assets.py:14` |
| `MAX_LOGO_BYTES` | `256 * 1024` | fixed / see setting | `backend/apps/payments/document_pdf_assets.py:15` |
| `DonationCampaign.kind (models.CharField)` | `max_length=10; default=Kind.CAMPAIGN` | field / model | `backend/apps/payments/donations/models_donations.py:31` |
| `DonationCampaign.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/payments/donations/models_donations.py:32` |
| `DonationCampaign.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/payments/donations/models_donations.py:33` |
| `DonationCampaign.goal_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/models_donations.py:35` |
| `DonationCampaign.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/donations/models_donations.py:36` |
| `DonationPledge.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/models_donations.py:91` |
| `DonationPledge.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/donations/models_donations.py:92` |
| `DonationPledge.interval (models.CharField)` | `max_length=10; default=Interval.MONTHLY` | field / model | `backend/apps/payments/donations/models_donations.py:93` |
| `DonationPledge.status (models.CharField)` | `max_length=10; default=Status.ACTIVE` | field / model | `backend/apps/payments/donations/models_donations.py:97` |
| `DonationPledge.manage_secret (models.CharField)` | `max_length=64; default=secrets.token_hex` | field / model | `backend/apps/payments/donations/models_donations.py:102` |
| `Donation.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/models_donations.py:142` |
| `Donation.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/donations/models_donations.py:143` |
| `Donation.source (models.CharField)` | `max_length=10; default=Source.ONLINE` | field / model | `backend/apps/payments/donations/models_donations.py:144` |
| `Donation.status (models.CharField)` | `max_length=10; default=Status.PENDING` | field / model | `backend/apps/payments/donations/models_donations.py:145` |
| `Donation.access_secret (models.CharField)` | `max_length=64; default=secrets.token_hex` | field / model | `backend/apps/payments/donations/models_donations.py:156` |
| `DonationSettings.page_intro (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:192` |
| `DonationSettings.minimum_amount (MoneyDecimalField)` | `max_digits=13; default=1` | field / model | `backend/apps/payments/donations/models_donations.py:194` |
| `DonationSettings.tax_exempt_registration_number (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:195` |
| `DonationSettings.tax_exempt_registrant_pan (models.CharField)` | `max_length=10; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:198` |
| `DonationSettings.tax_exempt_note (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:199` |
| `DonationSettings.legal_name (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:204` |
| `DonationSettings.organization_registration_number (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:205` |
| `DonationSettings.signatory_name (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:207` |
| `DonationSettings.signatory_title (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:208` |
| `DonationSettings.receipt_footer (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/models_donations.py:209` |
| `SponsorTier.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/payments/donations/models_sponsors.py:22` |
| `SponsorTier.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/models_sponsors.py:24` |
| `SponsorTier.currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:25` |
| `SponsorTier.description (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:26` |
| `Sponsor.name (models.CharField)` | `max_length=150` | field / model | `backend/apps/payments/donations/models_sponsors.py:36` |
| `Sponsor.logo_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:40` |
| `Sponsor.website_url (models.URLField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:41` |
| `Sponsor.blurb (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:42` |
| `SponsorPerk.description (models.CharField)` | `max_length=300` | field / model | `backend/apps/payments/donations/models_sponsors.py:70` |
| `SponsorPerk.note (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:75` |
| `SponsorshipCharge.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/models_sponsors.py:100` |
| `SponsorshipCharge.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/donations/models_sponsors.py:101` |
| `SponsorshipCharge.description (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/payments/donations/models_sponsors.py:102` |
| `SponsorshipCharge.earmark (models.CharField)` | `max_length=12; default='general'` | field / model | `backend/apps/payments/donations/models_sponsors.py:105` |
| `MAX_EXEMPTIONS` | `10` | fixed / see setting | `backend/apps/payments/donations/nonprofit.py:29` |
| `GiverFields.donor_name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/payments/donations/serializers_public.py:12` |
| `GiverFields.email_code (serializers.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/payments/donations/serializers_public.py:14` |
| `GiverFields.donor_pan (serializers.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/payments/donations/serializers_public.py:16` |
| `GiverFields.donor_address (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/serializers_public.py:18` |
| `DonationCreateSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_public.py:22` |
| `DonationCreateSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/serializers_public.py:24` |
| `PledgeCreateSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_public.py:30` |
| `CampaignCardSerializer.goal_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_public.py:46` |
| `CampaignCardSerializer.raised_amount (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/donations/serializers_public.py:47` |
| `DonationPageSerializer.minimum_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_public.py:72` |
| `GiftStatusSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_public.py:96` |
| `PledgeStatusSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_public.py:116` |
| `PledgeActionSerializer.amount (MoneyField)` | `max_digits=13; default=None` | field / model | `backend/apps/payments/donations/serializers_public.py:128` |
| `ChargeCreateSerializer.amount (MoneyField)` | `max_digits=13, min_value=1` | field / model | `backend/apps/payments/donations/serializers_sponsors.py:67` |
| `ChargeCreateSerializer.description (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/payments/donations/serializers_sponsors.py:68` |
| `ChargeCreateSerializer.event_id (serializers.IntegerField)` | `min_value=1; default=None` | field / model | `backend/apps/payments/donations/serializers_sponsors.py:70` |
| `FulfilSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/serializers_sponsors.py:129` |
| `TaxExemptionSerializer.number (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/payments/donations/serializers_staff.py:39` |
| `DonationSettingsSerializer.suggested_amounts (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_staff.py:48` |
| `DonationSettingsSerializer.suggested_amounts (serializers.ListField)` | `max_length=8` | field / model | `backend/apps/payments/donations/serializers_staff.py:48` |
| `DonationSettingsSerializer.tax_exemptions (serializers.ListField)` | `max_length=10` | field / model | `backend/apps/payments/donations/serializers_staff.py:51` |
| `DeskGiftSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/donations/serializers_staff.py:148` |
| `DeskGiftSerializer.donor_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/payments/donations/serializers_staff.py:149` |
| `DeskGiftSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/serializers_staff.py:152` |
| `DeskGiftSerializer.donor_pan (serializers.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/payments/donations/serializers_staff.py:154` |
| `DeskGiftSerializer.donor_address (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/serializers_staff.py:155` |
| `NoteSerializer.reason (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/serializers_staff.py:162` |
| `ChargeReturnSerializer.reason (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/donations/views_sponsors.py:198` |
| `ClaimDecisionSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/donations/views_staff_area.py:50` |
| `SUPPORTER_LIMIT` | `30` | fixed / see setting | `backend/apps/payments/donations/wall.py:49` |
| `FinanceAttachment.event_title_snapshot (models.CharField)` | `max_length=200` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:12` |
| `FinanceAttachment.purpose (models.CharField)` | `max_length=32` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:14` |
| `FinanceAttachment.binding_kind (models.CharField)` | `max_length=8` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:16` |
| `FinanceAttachment.question_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:18` |
| `FinanceAttachment.state (models.CharField)` | `max_length=12; default='initiated'` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:19` |
| `FinanceAttachment.declared_mime (models.CharField)` | `max_length=100` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:25` |
| `FinanceAttachment.canonical_mime (models.CharField)` | `max_length=100` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:26` |
| `FinanceAttachment.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:27` |
| `FinanceAttachment.staging_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:29` |
| `FinanceAttachment.staging_version_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:30` |
| `FinanceAttachment.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:31` |
| `FinanceAttachment.final_version_id (models.CharField)` | `max_length=200` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:32` |
| `FinanceAttachment.scan_status (models.CharField)` | `max_length=8; default='pending'` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:33` |
| `FinanceAttachment.scanner_policy (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:35` |
| `FinanceAttachment.scanner_version (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:36` |
| `FinanceAttachment.error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:37` |
| `FinanceAttachment.closure_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:45` |
| `FinanceAttachment.legal_hold_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/attachment_models.py:49` |
| `MAX_BYTES` | `10 * 1024 ** 2` | fixed / see setting | `backend/apps/payments/event_payouts/attachment_policy.py:19` |
| `FinanceObjectCleanup.bucket (models.CharField)` | `max_length=200` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:28` |
| `FinanceObjectCleanup.staging_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:29` |
| `FinanceObjectCleanup.object_key (models.CharField)` | `max_length=500` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:30` |
| `FinanceObjectCleanup.last_error_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:36` |
| `FinanceSweepCursor.key (models.CharField)` | `max_length=32` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:69` |
| `FinanceSweepCursor.last_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:70` |
| `FinanceRetentionPolicyRevision.command_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:82` |
| `FinanceRetentionPolicyRevision.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/cleanup_models.py:83` |
| `EventPayoutCommandReceipt.command_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/command_models.py:11` |
| `PayoutEligibility.status (models.CharField)` | `max_length=24` | field / model | `backend/apps/payments/event_payouts/eligibility_models.py:14` |
| `PayoutEligibility.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/eligibility_models.py:15` |
| `PayoutHold.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/payments/event_payouts/eligibility_models.py:29` |
| `PayoutHold.action (models.CharField)` | `max_length=8` | field / model | `backend/apps/payments/event_payouts/eligibility_models.py:30` |
| `PayoutHold.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/eligibility_models.py:34` |
| `PayoutExportBatch.command_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/export_models.py:15` |
| `PayoutExportBatch.selection_hash (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/export_models.py:17` |
| `PayoutExportBatch.state (models.CharField)` | `max_length=8; default='ready'` | field / model | `backend/apps/payments/event_payouts/export_models.py:18` |
| `EventPayoutObligation.event_title_snapshot (models.CharField)` | `max_length=200` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:15` |
| `EventPayoutObligation.source_kind (models.CharField)` | `max_length=24; default='event_reimbursement'` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:16` |
| `EventPayoutObligation.domain_coordination_state (models.CharField)` | `max_length=8; default='attached'` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:19` |
| `EventPayoutObligation.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:20` |
| `EventPayoutObligation.eligibility_status (models.CharField)` | `max_length=24; default='needs_acknowledgement'` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:25` |
| `EventPayoutObligation.hold_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:29` |
| `EventPayoutObligation.state (models.CharField)` | `max_length=12; default='open'` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:30` |
| `EventPayoutObligationRevision.kind (models.CharField)` | `max_length=12` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:47` |
| `EventPayoutObligationRevision.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:49` |
| `EventPayoutObligationRevision.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:53` |
| `EventPayoutObligationRevision.command_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/obligation_models.py:57` |
| `EventPayeeRevision.country (models.CharField)` | `max_length=2` | field / model | `backend/apps/payments/event_payouts/payee_models.py:15` |
| `EventPayeeRevision.template_key (models.CharField)` | `max_length=24` | field / model | `backend/apps/payments/event_payouts/payee_models.py:16` |
| `EventPayeeRevision.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/event_payouts/payee_models.py:18` |
| `EventPayeeRevision.state (models.CharField)` | `max_length=12; default='current'` | field / model | `backend/apps/payments/event_payouts/payee_models.py:20` |
| `EventPayeeRevision.closure_reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/payee_models.py:28` |
| `EventPayeeReview.kind (models.CharField)` | `max_length=20` | field / model | `backend/apps/payments/event_payouts/payee_models.py:47` |
| `EventPayeeReview.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/payee_models.py:50` |
| `EventPayoutEntry.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/event_payouts/payout_models.py:18` |
| `EventPayoutEntry.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/event_payouts/payout_models.py:19` |
| `EventPayoutEntry.reference (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/payout_models.py:20` |
| `EventPayoutEntry.command_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/payout_models.py:25` |
| `EventPayoutEntry.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/payout_models.py:28` |
| `ReceiptUse.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/receipt_models.py:12` |
| `ReceiptUse.original_currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/event_payouts/receipt_models.py:13` |
| `ReceiptAllocationOverride.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/event_payouts/receipt_models.py:29` |
| `ReceiptAllocationOverride.reason_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/receipt_models.py:32` |
| `Command.expected_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers.py:51` |
| `PayeeCommand.expected_payee_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers.py:94` |
| `PayeeCommand.template_key (serializers.CharField)` | `max_length=24` | field / model | `backend/apps/payments/event_payouts/serializers.py:96` |
| `PayeeCommand.template_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers.py:97` |
| `PayeeCommand.disclosure_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers.py:100` |
| `RevealCommand.expected_payee_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers.py:104` |
| `PayeeFileCreateCommand.expected_payee_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_files.py:9` |
| `PayeeFileCreateCommand.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/payments/event_payouts/serializers_files.py:11` |
| `PayeeFileCreateCommand.bytes (Integer)` | `min_value=1, max_value=10485760` | field / model | `backend/apps/payments/event_payouts/serializers_files.py:12` |
| `FinanceFileCommand.expected_asset_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_files.py:17` |
| `FinanceFileCommand.generation (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_files.py:18` |
| `CancelUnpaidObligationCommand.expected_revision_sequence (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:8` |
| `CancelUnpaidObligationCommand.expected_pool_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:9` |
| `CancelUnpaidObligationCommand.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:11` |
| `RecordPayoutCommand.amount_minor (Integer)` | `min_value=1, max_value=MAX_MINOR` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:15` |
| `RecordPayoutCommand.reference (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:18` |
| `RecordPayoutCommand.expected_payee_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:21` |
| `RecordPayoutCommand.eligibility_revision (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:22` |
| `AmendPayoutCommand.amount_minor (Integer)` | `min_value=0, max_value=MAX_MINOR` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:27` |
| `AmendPayoutCommand.expected_payee_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:31` |
| `PayeeVerifyCommand.expected_payee_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:36` |
| `PayeeCorrectionCommand.note (serializers.CharField)` | `max_length=5000` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:42` |
| `PayoutHoldCommand.eligibility_revision (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:46` |
| `PayoutHoldCommand.note (serializers.CharField)` | `max_length=5000; default=''` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:49` |
| `PayoutHoldCommand.evidence_refs (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:50` |
| `PayoutHoldCommand.evidence_refs (serializers.ListField)` | `max_length=100; default=list` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:50` |
| `EligibilityAcknowledgementCommand.eligibility_revision (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:60` |
| `PayoutExportCommand.expected_version (Integer)` | `min_value=0, max_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:65` |
| `PayoutExportCommand.obligation_ids (serializers.ListField)` | `max_length=500` | field / model | `backend/apps/payments/event_payouts/serializers_finance.py:66` |
| `Source.claim_revision (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:8` |
| `Source.decision_sequence (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:10` |
| `Decision.actor_id (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:16` |
| `CategoryCaps.rail (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:22` |
| `CategoryCaps.air (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:23` |
| `CategoryCaps.bus (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:24` |
| `CategoryCaps.ground_transport (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:25` |
| `CategoryCaps.lodging (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:26` |
| `Award.cap_minor (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:35` |
| `Award.policy_revision (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:37` |
| `Award.rule_revision (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:38` |
| `Totals.claimed_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:43` |
| `Totals.eligible_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:44` |
| `Totals.approved_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:45` |
| `OverrideAllocation.original_amount_minor (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:51` |
| `Receipt.attachment_id (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:55` |
| `Receipt.generation (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:56` |
| `Receipt.total_minor (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:58` |
| `Receipt.receipt_use_id (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:60` |
| `Receipt.receipt_use_version (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:61` |
| `Receipt.allocation_minor (Integer)` | `min_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:62` |
| `Limits.cap_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:70` |
| `DecisionLine.original_amount_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:80` |
| `DecisionLine.original_exponent (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:82` |
| `DecisionLine.target_exponent (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:88` |
| `DecisionLine.converted_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:89` |
| `DecisionLine.approved_minor (Integer)` | `min_value=0` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:90` |
| `DecisionSummarySerializer.schema_version (Integer)` | `min_value=1, max_value=1` | field / model | `backend/apps/payments/event_payouts/serializers_snapshot.py:109` |
| `MAX_MINOR` | `9000000000000000` | fixed / see setting | `backend/apps/payments/event_payouts/validation.py:7` |
| `MakerspaceBillingSettings.payment_terms_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/payments/models_billing.py:35` |
| `MakerspaceBillingSettings.max_reminders (MaxValueValidator)` | `max_value=20` | field / model | `backend/apps/payments/models_billing.py:38` |
| `MakerspaceBillingSettings.number_prefix (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/payments/models_billing.py:39` |
| `MakerspaceBillingSettings.bill_prefix (models.CharField)` | `max_length=32; default='BILL-'` | field / model | `backend/apps/payments/models_billing.py:40` |
| `MakerspaceBillingSettings.payment_instructions (models.TextField)` | `max_length=2000; default=''` | field / model | `backend/apps/payments/models_billing.py:41` |
| `MakerspaceBillingSettings.legal_name (models.CharField)` | `max_length=150; default=''` | field / model | `backend/apps/payments/models_billing.py:42` |
| `MakerspaceBillingSettings.address (models.TextField)` | `max_length=1000; default=''` | field / model | `backend/apps/payments/models_billing.py:43` |
| `MakerspaceBillingSettings.tax_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_billing.py:44` |
| `MakerspaceBillingSettings.footer (models.TextField)` | `max_length=1000; default=''` | field / model | `backend/apps/payments/models_billing.py:45` |
| `MakerspaceBillingSettings.upi_vpa (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_billing.py:49` |
| `MakerspaceBillingSettings.upi_payee_name (models.CharField)` | `max_length=50; default=''` | field / model | `backend/apps/payments/models_billing.py:50` |
| `PaymentCaptureFlag.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_capture_flags.py:39` |
| `PaymentCaptureFlag.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_capture_flags.py:40` |
| `PaymentCaptureFlag.provider_payment_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_capture_flags.py:41` |
| `PaymentCaptureFlag.provider_event_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_capture_flags.py:42` |
| `PaymentCaptureFlag.captured_currency (models.CharField)` | `max_length=3; default=''` | field / model | `backend/apps/payments/models_capture_flags.py:46` |
| `PaymentCaptureFlag.captured_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_capture_flags.py:47` |
| `PaymentCaptureFlag.prior_status (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/payments/models_capture_flags.py:48` |
| `PaymentCaptureFlag.resolution (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/payments/models_capture_flags.py:50` |
| `PaymentCaptureFlag.resolution_note (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/models_capture_flags.py:51` |
| `PaymentClaim.method (models.CharField)` | `max_length=16; default=Method.UPI` | field / model | `backend/apps/payments/models_claims.py:35` |
| `PaymentClaim.reference (models.CharField)` | `max_length=35` | field / model | `backend/apps/payments/models_claims.py:37` |
| `PaymentClaim.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_claims.py:39` |
| `PaymentClaim.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_claims.py:40` |
| `PaymentClaim.status (models.CharField)` | `max_length=24; default=Status.SUBMITTED` | field / model | `backend/apps/payments/models_claims.py:41` |
| `PaymentClaim.decision_note (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/models_claims.py:45` |
| `PaymentDispute.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_disputes.py:26` |
| `PaymentDispute.provider_dispute_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_disputes.py:27` |
| `PaymentDispute.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_disputes.py:28` |
| `PaymentDispute.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_disputes.py:29` |
| `PaymentDispute.reason (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_disputes.py:30` |
| `PaymentDispute.status (models.CharField)` | `max_length=16; default=Status.OPEN` | field / model | `backend/apps/payments/models_disputes.py:31` |
| `PaymentDispute.provider_status (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/payments/models_disputes.py:32` |
| `PaymentDisputeEvent.status (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_disputes.py:50` |
| `PaymentDisputeEvent.provider_status (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/payments/models_disputes.py:51` |
| `PaymentDisputeEvent.provider_event_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_disputes.py:52` |
| `PaymentDisputeEvent.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_disputes.py:53` |
| `PaymentDocument.number (models.CharField)` | `max_length=80` | field / model | `backend/apps/payments/models_documents.py:22` |
| `PaymentDocument.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_documents.py:23` |
| `PaymentDocument.branding_logo_key (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/models_documents.py:25` |
| `PaymentDocument.branding_logo_sha256 (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_documents.py:26` |
| `PaymentDocument.payer_label (models.CharField)` | `max_length=150` | field / model | `backend/apps/payments/models_documents.py:28` |
| `PaymentDocument.payer_type (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_documents.py:29` |
| `PaymentDocument.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_documents.py:31` |
| `PaymentDocument.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_documents.py:32` |
| `PaymentDocument.settlement_method (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_documents.py:33` |
| `PaymentDocument.settlement_reference (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/models_documents.py:34` |
| `PaymentDocument.number_series (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/payments/models_documents.py:42` |
| `EventFinanceBudget.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_event_budget.py:20` |
| `EventFinanceBudget.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_event_budget.py:21` |
| `EventMoneySettings.prize_tds_rate (models.DecimalField)` | `max_digits=5; default=Decimal('30.00')` | field / model | `backend/apps/payments/models_event_money.py:21` |
| `EventMoneySettings.prize_tds_threshold (MoneyDecimalField)` | `max_digits=13; default=Decimal('10000.00')` | field / model | `backend/apps/payments/models_event_money.py:22` |
| `LedgerEntry.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_ledger_entries.py:62` |
| `LedgerEntry.domain (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_ledger_entries.py:63` |
| `LedgerEntry.machine_type_label (models.CharField)` | `max_length=120; default=''` | field / model | `backend/apps/payments/models_ledger_entries.py:67` |
| `LedgerEntry.category (models.CharField)` | `max_length=48` | field / model | `backend/apps/payments/models_ledger_entries.py:69` |
| `LedgerEntry.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_ledger_entries.py:70` |
| `LedgerEntry.account (models.CharField)` | `max_length=8` | field / model | `backend/apps/payments/models_ledger_entries.py:71` |
| `LedgerEntry.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_ledger_entries.py:72` |
| `LedgerEntry.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_ledger_entries.py:73` |
| `LedgerEntry.description (models.CharField)` | `max_length=300` | field / model | `backend/apps/payments/models_ledger_entries.py:75` |
| `LedgerEntry.counterparty (models.CharField)` | `max_length=150; default=''` | field / model | `backend/apps/payments/models_ledger_entries.py:77` |
| `LedgerEntry.reference (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_ledger_entries.py:78` |
| `LedgerEntry.source_kind (models.CharField)` | `max_length=48; default='manual'` | field / model | `backend/apps/payments/models_ledger_entries.py:80` |
| `LedgerEntry.source_id (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_ledger_entries.py:81` |
| `LedgerEntry.void_reason (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/models_ledger_entries.py:88` |
| `OpeningBalance.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_ledger_entries.py:128` |
| `OpeningBalance.cash_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_ledger_entries.py:129` |
| `OpeningBalance.bank_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_ledger_entries.py:130` |
| `PaymentPayLink.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/models_pay_links.py:15` |
| `Payment.subject_type (models.CharField)` | `max_length=48` | field / model | `backend/apps/payments/models_payment.py:98` |
| `Payment.subject_label (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_payment.py:116` |
| `Payment.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_payment.py:117` |
| `Payment.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_payment.py:118` |
| `Payment.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/payments/models_payment.py:119` |
| `Payment.provider (models.CharField)` | `max_length=16; default=Provider.STRIPE` | field / model | `backend/apps/payments/models_payment.py:125` |
| `Payment.external_order_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_payment.py:128` |
| `Payment.external_payment_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_payment.py:129` |
| `Payment.stripe_provider (models.CharField)` | `max_length=16; default=StripeProvider.RAW` | field / model | `backend/apps/payments/models_payment.py:131` |
| `Payment.stripe_connected_account_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_payment.py:132` |
| `Payment.online_rail (models.CharField)` | `max_length=32` | field / model | `backend/apps/payments/models_payment.py:134` |
| `Payment.stripe_checkout_session_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_payment.py:140` |
| `Payment.stripe_payment_intent_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_payment.py:143` |
| `Payment.method_label (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_payment.py:148` |
| `ProcessedStripeEvent.provider (models.CharField)` | `max_length=16; default=Payment.Provider.STRIPE` | field / model | `backend/apps/payments/models_payment.py:270` |
| `ProcessedStripeEvent.stripe_event_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_payment.py:271` |
| `PricingDefault.domain (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_pricing.py:50` |
| `PricingDefault.mode (models.CharField)` | `max_length=8; default=Mode.FREE` | field / model | `backend/apps/payments/models_pricing.py:51` |
| `PricingDefault.rental_timing (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/payments/models_pricing.py:53` |
| `PricingDefault.failed_job_charge (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/payments/models_pricing.py:55` |
| `PricingDefaultLine.component (models.CharField)` | `max_length=32` | field / model | `backend/apps/payments/models_pricing.py:75` |
| `PricingDefaultLine.amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_pricing.py:76` |
| `PricingDefaultLine.cap (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_pricing.py:79` |
| `PriceOverride.domain (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_pricing.py:117` |
| `PriceOverride.component (models.CharField)` | `max_length=32` | field / model | `backend/apps/payments/models_pricing.py:118` |
| `PriceOverride.target_type (models.CharField)` | `max_length=24` | field / model | `backend/apps/payments/models_pricing.py:119` |
| `PriceOverride.mode (models.CharField)` | `max_length=8` | field / model | `backend/apps/payments/models_pricing.py:128` |
| `PriceOverride.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_pricing.py:129` |
| `PriceOverride.cap (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_pricing.py:130` |
| `PriceDiscount.name (models.CharField)` | `max_length=120` | field / model | `backend/apps/payments/models_pricing_rules.py:29` |
| `PriceDiscount.audience (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_pricing_rules.py:30` |
| `PriceDiscount.percent_bps (MaxValueValidator)` | `max_value=10000` | field / model | `backend/apps/payments/models_pricing_rules.py:43` |
| `PriceDiscount.percent_bps (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/payments/models_pricing_rules.py:43` |
| `PriceDiscount.amount_off (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_pricing_rules.py:44` |
| `LoanFeeWaiver.reason (models.CharField)` | `max_length=500` | field / model | `backend/apps/payments/models_pricing_rules.py:100` |
| `Refund.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_refund.py:41` |
| `Refund.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_refund.py:42` |
| `Refund.status (models.CharField)` | `max_length=16; default=Status.PENDING` | field / model | `backend/apps/payments/models_refund.py:43` |
| `Refund.provider (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_refund.py:44` |
| `Refund.method (models.CharField)` | `max_length=16; default=''` | field / model | `backend/apps/payments/models_refund.py:45` |
| `Refund.reference (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_refund.py:47` |
| `Refund.external_refund_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_refund.py:52` |
| `Refund.reason (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_refund.py:55` |
| `RefundCase.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_refund_cases.py:99` |
| `RefundCase.area (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_refund_cases.py:100` |
| `RefundCase.reason_code (models.CharField)` | `max_length=32` | field / model | `backend/apps/payments/models_refund_cases.py:101` |
| `RefundCase.member_reason (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/models_refund_cases.py:104` |
| `RefundCase.due_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_refund_cases.py:107` |
| `RefundCase.status (models.CharField)` | `max_length=16; default=Status.OPEN` | field / model | `backend/apps/payments/models_refund_cases.py:110` |
| `RefundCase.approved_amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_refund_cases.py:116` |
| `RefundCase.decision_note (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/models_refund_cases.py:118` |
| `RefundPolicy.area (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_refund_cases.py:166` |
| `RefundPolicy.partial_percent (MaxValueValidator)` | `max_value=100` | field / model | `backend/apps/payments/models_refund_cases.py:176` |
| `RefundPolicy.partial_mode (models.CharField)` | `max_length=16; default=PartialMode.PERCENT` | field / model | `backend/apps/payments/models_refund_cases.py:180` |
| `RefundPolicy.cancellation_fee (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_refund_cases.py:182` |
| `MakerspacePaymentSettings.provider (models.CharField)` | `max_length=16; default='stripe'` | field / model | `backend/apps/payments/models_settings.py:41` |
| `MakerspacePaymentSettings.stripe_publishable_key (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_settings.py:46` |
| `MakerspacePaymentSettings.default_currency (models.CharField)` | `max_length=3; default='usd'` | field / model | `backend/apps/payments/models_settings.py:49` |
| `MakerspacePaymentSettings.connect_account_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/payments/models_settings.py:52` |
| `MakerspacePaymentSettings.connect_status (models.CharField)` | `max_length=16; default=ConnectStatus.UNCONNECTED` | field / model | `backend/apps/payments/models_settings.py:59` |
| `MakerspacePaymentSettings.razorpay_key_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_settings.py:69` |
| `MakerspacePaymentSettings.loan_deposit_mode (models.CharField)` | `max_length=16; default=LoanDepositMode.NONE` | field / model | `backend/apps/payments/models_settings.py:74` |
| `MakerspacePaymentSettings.loan_deposit_amount (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_settings.py:77` |
| `MakerspacePaymentSettings.loan_late_fee_per_day (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_settings.py:78` |
| `MakerspacePaymentSettings.loan_late_fee_cap (MoneyDecimalField)` | `max_digits=13; default=0` | field / model | `backend/apps/payments/models_settings.py:79` |
| `PlatformStripeConnectSettings.stripe_publishable_key (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_settings.py:227` |
| `PlatformStripeConnectSettings.stripe_connect_client_id (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/models_settings.py:230` |
| `PlatformStripeConnectSettings.application_fee_bps (MaxValueValidator)` | `max_value=10000` | field / model | `backend/apps/payments/models_settings.py:232` |
| `StripeConnectOAuthState.state_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/payments/models_settings.py:275` |
| `ManualSettlement.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_settlement.py:45` |
| `ManualSettlement.reference (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_settlement.py:50` |
| `ManualSettlement.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_settlement.py:53` |
| `ManualSettlement.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_settlement.py:54` |
| `SettlementConfirmation.method (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/models_settlement.py:168` |
| `SettlementConfirmation.reference (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/models_settlement.py:169` |
| `SettlementConfirmation.amount (MoneyDecimalField)` | `max_digits=13` | field / model | `backend/apps/payments/models_settlement.py:171` |
| `SettlementConfirmation.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/payments/models_settlement.py:172` |
| `SettlementConfirmation.status (models.CharField)` | `max_length=24; default=Status.AWAITING` | field / model | `backend/apps/payments/models_settlement.py:176` |
| `SettlementConfirmation.decision_note (models.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/models_settlement.py:179` |
| `MONEY_MAX_DIGITS` | `13` | fixed / see setting | `backend/apps/payments/money.py:17` |
| `MAX_LENGTH` | `16` | fixed / see setting | `backend/apps/payments/numbering_fy.py:20` |
| `MAX_DAYS` | `60` | fixed / see setting | `backend/apps/payments/pay_links.py:25` |
| `PricingQuoteLineSerializer.quantity (serializers.DecimalField)` | `max_digits=16` | field / model | `backend/apps/payments/pricing/serializers.py:13` |
| `PricingQuoteLineSerializer.unit_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:14` |
| `PricingQuoteLineSerializer.gross (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:15` |
| `PricingQuoteLineSerializer.discount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:16` |
| `PricingQuoteLineSerializer.net (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:17` |
| `PricingQuoteDiscountSerializer.saving (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:28` |
| `PricingQuoteSerializer.subtotal (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:36` |
| `PricingQuoteSerializer.discount_total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:37` |
| `PricingQuoteSerializer.total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:38` |
| `PricingRateLineSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers.py:66` |
| `PricingRateLineSerializer.cap (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers.py:67` |
| `PricingRateLineSerializer.grace_units (serializers.IntegerField)` | `min_value=0, max_value=365` | field / model | `backend/apps/payments/pricing/serializers.py:68` |
| `PricingRateLineSerializer.billing_increment (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/payments/pricing/serializers.py:69` |
| `PricingRateLineSerializer.minimum (serializers.IntegerField)` | `min_value=0, max_value=1440` | field / model | `backend/apps/payments/pricing/serializers.py:70` |
| `PricingLendingSerializer.deposit_amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers.py:76` |
| `PricingLendingSerializer.late_per_day (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers.py:78` |
| `PricingLendingSerializer.late_cap (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers.py:79` |
| `PricingLendingSerializer.grace_days (serializers.IntegerField)` | `min_value=0, max_value=365` | field / model | `backend/apps/payments/pricing/serializers.py:80` |
| `PricingImpactChangeSerializer.before (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:120` |
| `PricingImpactChangeSerializer.after (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers.py:121` |
| `PricingCurrencySerializer.default_currency (serializers.RegexField)` | `max_length=3` | field / model | `backend/apps/payments/pricing/serializers.py:135` |
| `PriceOverrideComponentSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers_rules.py:18` |
| `PriceOverrideComponentSerializer.cap (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers_rules.py:19` |
| `PriceOverrideComponentSerializer.effective_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers_rules.py:20` |
| `PriceOverrideComponentSerializer.default_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers_rules.py:22` |
| `PriceOverrideWriteSerializer.component (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/payments/pricing/serializers_rules.py:37` |
| `PriceOverrideWriteSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers_rules.py:39` |
| `PriceOverrideWriteSerializer.cap (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers_rules.py:40` |
| `PriceDiscountSerializer.components (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/payments/pricing/serializers_rules.py:54` |
| `LoanFeeWaiverCreateSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/payments/pricing/serializers_rules.py:113` |
| `LoanFeeWaiverRevokeSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/payments/pricing/serializers_rules.py:117` |
| `LoanChargeSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers_rules.py:131` |
| `LoanAccountabilityRowSerializer.suggested_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/pricing/serializers_rules.py:143` |
| `LoanAccountabilityChargeSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/pricing/serializers_rules.py:164` |
| `LoanAccountabilityChargeSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/pricing/serializers_rules.py:165` |
| `DecimalField` | `max_digits=13` | field / model | `backend/apps/payments/reconciliation.py:78` |
| `MemberRefundSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers.py:25` |
| `ArchivedPaymentSummarySerializer.pending_count (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/payments/serializers.py:183` |
| `ArchivedPaymentSummarySerializer.total_count (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/serializers.py:184` |
| `CollectionRowSerializer.payment_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/serializers_collection_sheet.py:15` |
| `CollectionRowSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/serializers_collection_sheet.py:17` |
| `CollectionSheetSerializer.rows (CollectionRowSerializer)` | `max_length=MAX_ROWS` | field / model | `backend/apps/payments/serializers_collection_sheet.py:27` |
| `CashHandoverSerializer.collector_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/serializers_collection_sheet.py:51` |
| `CashHandoverSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/payments/serializers_collection_sheet.py:52` |
| `CashHandoverSerializer.note (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/payments/serializers_collection_sheet.py:55` |
| `CashHandoverResultSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_collection_sheet.py:61` |
| `ClaimSubmitSerializer.reference (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/payments/serializers_l5.py:46` |
| `DecisionNoteSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/payments/serializers_l5.py:67` |
| `CaptureFlagSerializer.charge_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_l5.py:93` |
| `FlagResolveSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/serializers_l5.py:108` |
| `FlagResolveSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/payments/serializers_l5.py:109` |
| `LedgerEntryCreateSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/payments/serializers_ledger.py:43` |
| `LedgerEntryCreateSerializer.description (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/payments/serializers_ledger.py:46` |
| `LedgerEntryCreateSerializer.counterparty (serializers.CharField)` | `max_length=150; default=''` | field / model | `backend/apps/payments/serializers_ledger.py:47` |
| `LedgerEntryCreateSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/serializers_ledger.py:48` |
| `VoidSerializer.reason (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/payments/serializers_ledger.py:65` |
| `ReceiptUploadRequestSerializer.size_bytes (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/serializers_ledger.py:71` |
| `OpeningBalanceSerializer.cash_amount (MoneyField)` | `max_digits=13; default=Decimal('0')` | field / model | `backend/apps/payments/serializers_ledger.py:89` |
| `OpeningBalanceSerializer.bank_amount (MoneyField)` | `max_digits=13; default=Decimal('0')` | field / model | `backend/apps/payments/serializers_ledger.py:90` |
| `PaymentBulkActionSerializer.ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/serializers_reconciliation.py:134` |
| `ManualSettlementSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/serializers_reconciliation.py:153` |
| `PaymentRefundRequestSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/payments/serializers_reconciliation.py:175` |
| `PaymentRefundRequestSerializer.reason (serializers.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/serializers_reconciliation.py:178` |
| `RefundCasePaymentSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_refund_cases.py:20` |
| `RefundCaseSerializer.MoneyField` | `max_digits=13` | field / model | `backend/apps/payments/serializers_refund_cases.py:55` |
| `RefundCaseApproveSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/payments/serializers_refund_cases.py:81` |
| `RefundCaseApproveSerializer.reason (serializers.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/payments/serializers_refund_cases.py:82` |
| `RefundCaseApproveSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/payments/serializers_refund_cases.py:83` |
| `RefundCaseDeclineSerializer.note (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/payments/serializers_refund_cases.py:93` |
| `MemberRefundRequestSerializer.reason (serializers.CharField)` | `max_length=500` | field / model | `backend/apps/payments/serializers_refund_cases.py:111` |
| `ManualRefundReceiptSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/payments/serializers_refunds_offline.py:15` |
| `TaxSettingsSerializer.rate_bps (serializers.IntegerField)` | `min_value=0, max_value=10000` | field / model | `backend/apps/payments/serializers_tax.py:14` |
| `GstinCheckSerializer.gstin (serializers.CharField)` | `max_length=32` | field / model | `backend/apps/payments/serializers_tax.py:41` |
| `TaxPreviewRequestSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/payments/serializers_tax.py:52` |
| `TaxComponentSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_tax.py:62` |
| `TaxPreviewSerializer.entered_amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_tax.py:68` |
| `TaxPreviewSerializer.taxable (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_tax.py:69` |
| `TaxPreviewSerializer.tax (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_tax.py:70` |
| `TaxPreviewSerializer.gross (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/serializers_tax.py:71` |
| `MakerspaceTaxSettings.mode (models.CharField)` | `max_length=16; default=Mode.NONE` | field / model | `backend/apps/payments/tax/models_tax.py:34` |
| `MakerspaceTaxSettings.tax_name (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/payments/tax/models_tax.py:35` |
| `MakerspaceTaxSettings.rate_bps (MaxValueValidator)` | `max_value=10000` | field / model | `backend/apps/payments/tax/models_tax.py:36` |
| `MakerspaceTaxSettings.gstin (models.CharField)` | `max_length=15; default=''` | field / model | `backend/apps/payments/tax/models_tax.py:38` |
| `MakerspaceTaxSettings.state_code (models.CharField)` | `max_length=2; default=''` | field / model | `backend/apps/payments/tax/models_tax.py:39` |
| `MakerspaceTaxSettings.scheme (models.CharField)` | `max_length=16; default=Scheme.REGULAR` | field / model | `backend/apps/payments/tax/models_tax.py:40` |
| `MakerspaceTaxSettings.sac_code (models.CharField)` | `max_length=8; default='999599'` | field / model | `backend/apps/payments/tax/models_tax.py:42` |
| `MakerspaceTaxSettings.foreign_currency (models.CharField)` | `max_length=16; default=ForeignCurrency.NO_GST` | field / model | `backend/apps/payments/tax/models_tax.py:43` |
| `MakerspaceTaxSettings.lut_number (models.CharField)` | `max_length=32; default=''` | field / model | `backend/apps/payments/tax/models_tax.py:44` |
| `MakerspaceTaxSettings.invoice_prefix (models.CharField)` | `max_length=4; default='INV'` | field / model | `backend/apps/payments/tax/models_tax.py:45` |
| `MakerspaceTaxSettings.credit_note_prefix (models.CharField)` | `max_length=4; default='CN'` | field / model | `backend/apps/payments/tax/models_tax.py:46` |
| `DocumentNumberCounter.series (models.CharField)` | `max_length=16` | field / model | `backend/apps/payments/tax/models_tax.py:98` |
| `BillingSettingsSerializer.reminder_days_before (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/payments/views_billing.py:22` |
| `BillingSettingsSerializer.reminder_days_before (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/payments/views_billing.py:22` |
| `BillingSettingsSerializer.reminder_days_after (serializers.IntegerField)` | `min_value=1, max_value=365` | field / model | `backend/apps/payments/views_billing.py:23` |
| `BillingSettingsSerializer.reminder_days_after (serializers.ListField)` | `max_length=20` | field / model | `backend/apps/payments/views_billing.py:23` |
| `BillingSettingsSerializer.max_reminders (serializers.IntegerField)` | `min_value=0, max_value=20` | field / model | `backend/apps/payments/views_billing.py:24` |
| `EventMoneySettingsRead.prize_tds_rate (serializers.DecimalField)` | `max_digits=5` | field / model | `backend/apps/payments/views_event_money.py:33` |
| `EventMoneySettingsRead.prize_tds_threshold (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_event_money.py:34` |
| `EventMoneySettingsInput.expected_version (serializers.IntegerField)` | `min_value=0` | field / model | `backend/apps/payments/views_event_money.py:42` |
| `EventMoneySettingsInput.prize_tds_rate (serializers.DecimalField)` | `max_digits=5, min_value=Decimal('0'), max_value=Decimal('100')` | field / model | `backend/apps/payments/views_event_money.py:44` |
| `EventMoneySettingsInput.prize_tds_threshold (MoneyField)` | `max_digits=13, min_value=Decimal('0')` | field / model | `backend/apps/payments/views_event_money.py:46` |
| `EventMoneySettingsInput.payee_templates (serializers.CharField)` | `max_length=16` | field / model | `backend/apps/payments/views_event_money.py:48` |
| `EventMoneySettingsInput.payee_templates (serializers.ListField)` | `max_length=200` | field / model | `backend/apps/payments/views_event_money.py:48` |
| `EventMoneySettingsInput.payee_templates (serializers.ListField)` | `min_length=2, max_length=2` | field / model | `backend/apps/payments/views_event_money.py:48` |
| `SummaryRowSerializer.income (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:43` |
| `SummaryRowSerializer.other_income (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:44` |
| `SummaryRowSerializer.refunds (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:45` |
| `SummaryRowSerializer.expenses (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:46` |
| `SummaryRowSerializer.payouts (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:47` |
| `SummaryRowSerializer.money_in (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:48` |
| `SummaryRowSerializer.money_out (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:49` |
| `SummaryRowSerializer.net (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:50` |
| `EventFinanceRowSerializer.income (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:63` |
| `EventFinanceRowSerializer.refunds (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:64` |
| `EventFinanceRowSerializer.other_income (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:65` |
| `EventFinanceRowSerializer.expenses (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:66` |
| `EventFinanceRowSerializer.payouts (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:67` |
| `EventFinanceRowSerializer.budget (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:68` |
| `EventFinanceRowSerializer.budget_left (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:69` |
| `EventFinanceRowSerializer.net (MoneyField)` | `max_digits=15` | field / model | `backend/apps/payments/views_finance.py:70` |
| `EventBudgetSerializer.amount (MoneyField)` | `max_digits=13, min_value=0` | field / model | `backend/apps/payments/views_finance.py:75` |
| `PayLinkCreateSerializer.days (serializers.IntegerField)` | `min_value=1, max_value=pay_links.MAX_DAYS; default=pay_links.DEFAULT_DAYS` | field / model | `backend/apps/payments/views_pay_links.py:30` |
| `PricingQuoteItemSerializer.product_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:32` |
| `PricingQuoteItemSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=1000` | field / model | `backend/apps/payments/views_pricing_quote.py:33` |
| `PricingQuoteRequestSerializer.items (PricingQuoteItemSerializer)` | `max_length=50` | field / model | `backend/apps/payments/views_pricing_quote.py:38` |
| `PricingQuoteRequestSerializer.days (serializers.IntegerField)` | `min_value=0, max_value=365` | field / model | `backend/apps/payments/views_pricing_quote.py:39` |
| `PricingQuoteRequestSerializer.request_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:40` |
| `PricingQuoteRequestSerializer.space_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:41` |
| `PricingQuoteRequestSerializer.machine_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:45` |
| `PricingQuoteRequestSerializer.machine_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:46` |
| `PricingQuoteRequestSerializer.pool_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:47` |
| `PricingQuoteRequestSerializer.minutes (serializers.IntegerField)` | `min_value=0, max_value=100000` | field / model | `backend/apps/payments/views_pricing_quote.py:48` |
| `PricingQuoteRequestSerializer.quantity (serializers.DecimalField)` | `max_digits=12, min_value=0` | field / model | `backend/apps/payments/views_pricing_quote.py:49` |
| `PricingQuoteRequestSerializer.event_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:50` |
| `PricingQuoteRequestSerializer.ticket_type_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:52` |
| `PricingQuoteRequestSerializer.plan_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/payments/views_pricing_quote.py:53` |
| `PricingQuoteTaxSerializer.net (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:63` |
| `PricingQuoteTaxSerializer.tax (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:64` |
| `PricingQuoteTaxSerializer.gross (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:65` |
| `PricingQuoteDepositSerializer.amount (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:71` |
| `PricingQuotePolicySerializer.late_per_day (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:76` |
| `PricingQuotePolicySerializer.late_cap (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:77` |
| `PricingQuotePolicySerializer.damage_default (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:79` |
| `PricingQuotePolicySerializer.lost_default (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:80` |
| `PricingPublicQuoteSerializer.members_total (MoneyField)` | `max_digits=13` | field / model | `backend/apps/payments/views_pricing_quote.py:88` |

</details>

<details>
<summary>presence (55 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `BODY_LIMIT` | `1024 * 1024` | fixed / see setting | `backend/apps/presence/anthias_client.py:37` |
| `MAX_UNCLAIMED` | `2000` | fixed / see setting | `backend/apps/presence/display_pairing.py:31` |
| `MAX_UNCLAIMED_PER_NETWORK` | `20` | fixed / see setting | `backend/apps/presence/display_pairing.py:34` |
| `MAX_HIGHLIGHTS` | `8` | fixed / see setting | `backend/apps/presence/display_panels_extra.py:13` |
| `MAX_SPONSORS` | `24` | fixed / see setting | `backend/apps/presence/display_panels_extra.py:14` |
| `MAX_CARDS` | `24` | fixed / see setting | `backend/apps/presence/here_now.py:24` |
| `MAX_SKILLS` | `4` | fixed / see setting | `backend/apps/presence/here_now.py:25` |
| `PresenceSession.status (models.CharField)` | `max_length=24; default=Status.VISITING` | field / model | `backend/apps/presence/models.py:39` |
| `PresenceSession.end_reason (models.CharField)` | `max_length=24` | field / model | `backend/apps/presence/models.py:67` |
| `AnthiasPlayer.name (models.CharField)` | `max_length=80` | field / model | `backend/apps/presence/models_anthias.py:21` |
| `AnthiasPlayer.host_url (models.CharField)` | `max_length=200` | field / model | `backend/apps/presence/models_anthias.py:22` |
| `AnthiasPlayer.username (models.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/presence/models_anthias.py:23` |
| `AnthiasPlayer.api_version (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/presence/models_anthias.py:25` |
| `AnthiasPlayer.anthias_version (models.CharField)` | `max_length=40; default=''` | field / model | `backend/apps/presence/models_anthias.py:26` |
| `AnthiasPlayer.status (models.CharField)` | `max_length=8; default=Status.NEVER` | field / model | `backend/apps/presence/models_anthias.py:27` |
| `AnthiasPlayer.last_error (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/presence/models_anthias.py:28` |
| `AnthiasAssetLink.asset_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/presence/models_anthias.py:45` |
| `AnthiasAssetLink.synced_hash (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/presence/models_anthias.py:46` |
| `AnthiasAssetLink.uri_hash (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/presence/models_anthias.py:47` |
| `SpaceNowConfig.privacy (models.CharField)` | `max_length=12; default='profiles'` | field / model | `backend/apps/presence/models_anthias.py:57` |
| `MAX_REFRESH` | `600` | fixed / see setting | `backend/apps/presence/models_display.py:38` |
| `MAX_ROTATION` | `120` | fixed / see setting | `backend/apps/presence/models_display.py:39` |
| `DisplayScreen.token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/presence/models_display.py:45` |
| `DisplayScreen.pairing_code (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/presence/models_display.py:46` |
| `DisplayScreen.name (models.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/presence/models_display.py:48` |
| `DisplayScreen.announcement (models.CharField)` | `max_length=280; default=''` | field / model | `backend/apps/presence/models_display.py:51` |
| `DisplayScreen.layout (models.CharField)` | `max_length=12; default='playlist'` | field / model | `backend/apps/presence/models_display.py:53` |
| `DisplayScreen.theme (models.CharField)` | `max_length=8; default='dark'` | field / model | `backend/apps/presence/models_display.py:54` |
| `DisplayScreen.privacy (models.CharField)` | `max_length=12; default='profiles'` | field / model | `backend/apps/presence/models_display.py:55` |
| `MAX_MACHINES` | `60` | fixed / see setting | `backend/apps/presence/public_feed.py:17` |
| `MAX_EVENTS` | `200` | fixed / see setting | `backend/apps/presence/public_feed.py:18` |
| `MAX_YEAR` | `2100` | fixed / see setting | `backend/apps/presence/public_feed.py:19` |
| `PresenceRenewSerializer.duration_minutes (serializers.IntegerField)` | `min_value=15, max_value=480` | field / model | `backend/apps/presence/serializers.py:22` |
| `PresenceStartSerializer.project_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/presence/serializers.py:27` |
| `PresenceStartSerializer.latitude (serializers.FloatField)` | `min_value=-90, max_value=90` | field / model | `backend/apps/presence/serializers.py:29` |
| `PresenceStartSerializer.longitude (serializers.FloatField)` | `min_value=-180, max_value=180` | field / model | `backend/apps/presence/serializers.py:30` |
| `PresenceStartSerializer.accuracy (serializers.FloatField)` | `min_value=0` | field / model | `backend/apps/presence/serializers.py:31` |
| `StaffPresenceStartSerializer.account_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/presence/serializers.py:41` |
| `StaffPresenceEndSerializer.account_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/presence/serializers.py:47` |
| `AnthiasPlayerWriteSerializer.name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/presence/serializers_anthias.py:27` |
| `AnthiasPlayerWriteSerializer.host_url (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/presence/serializers_anthias.py:28` |
| `AnthiasPlayerWriteSerializer.username (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/presence/serializers_anthias.py:29` |
| `AnthiasPlayerWriteSerializer.password (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/presence/serializers_anthias.py:30` |
| `DisplayPlayersSerializer.player_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/presence/serializers_anthias.py:47` |
| `DisplayPlayersSerializer.player_ids (serializers.ListField)` | `max_length=10` | field / model | `backend/apps/presence/serializers_anthias.py:47` |
| `NowConfigSerializer.sections (serializers.CharField)` | `max_length=24` | field / model | `backend/apps/presence/serializers_anthias.py:51` |
| `NowConfigSerializer.sections (serializers.ListField)` | `max_length=8` | field / model | `backend/apps/presence/serializers_anthias.py:51` |
| `DisplayConfigSerializer.name (serializers.CharField)` | `max_length=80` | field / model | `backend/apps/presence/serializers_display.py:71` |
| `DisplayConfigSerializer.rotation_seconds (serializers.IntegerField)` | `min_value=MIN_ROTATION, max_value=MAX_ROTATION` | field / model | `backend/apps/presence/serializers_display.py:73` |
| `DisplayConfigSerializer.announcement (serializers.CharField)` | `max_length=280` | field / model | `backend/apps/presence/serializers_display.py:74` |
| `DisplayConfigSerializer.refresh_seconds (serializers.IntegerField)` | `min_value=MIN_REFRESH, max_value=MAX_REFRESH` | field / model | `backend/apps/presence/serializers_display.py:79` |
| `DisplayConfigSerializer.slide_seconds (serializers.IntegerField)` | `min_value=MIN_ROTATION, max_value=MAX_ROTATION` | field / model | `backend/apps/presence/serializers_display.py:80` |
| `DisplayClaimSerializer.code (serializers.CharField)` | `max_length=8` | field / model | `backend/apps/presence/serializers_display.py:85` |
| `MAX_PLAYERS` | `10` | fixed / see setting | `backend/apps/presence/views_anthias.py:32` |
| `MAX_RESULTS` | `20` | fixed / see setting | `backend/apps/presence/views_staff_guests.py:22` |

</details>

<details>
<summary>procurement (35 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `ToBuyItem.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/procurement/models.py:39` |
| `ToBuyItem.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/models.py:40` |
| `ToBuyItem.status (models.CharField)` | `max_length=16; default=Status.REQUESTED` | field / model | `backend/apps/procurement/models.py:43` |
| `ToBuyItem.estimated_unit_cost (MoneyDecimalField)` | `max_digits=11` | field / model | `backend/apps/procurement/models.py:48` |
| `ToBuyItem.vendor_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/models.py:54` |
| `ToBuyItem.actual_unit_cost (MoneyDecimalField)` | `max_digits=11` | field / model | `backend/apps/procurement/models.py:55` |
| `ToBuyReceipt.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/procurement/models.py:147` |
| `Vendor.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/models_vendors.py:17` |
| `Vendor.contact_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/models_vendors.py:18` |
| `Vendor.email (models.EmailField)` | `max_length=254` | field / model | `backend/apps/procurement/models_vendors.py:19` |
| `Vendor.phone (models.CharField)` | `max_length=40` | field / model | `backend/apps/procurement/models_vendors.py:20` |
| `ToBuyItemSerializer.quantity (serializers.IntegerField)` | `min_value=1; default=1` | field / model | `backend/apps/procurement/serializers.py:74` |
| `MoveToInventoryRequestSerializer.quantity (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/procurement/serializers.py:156` |
| `MoveToInventoryRequestSerializer.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/serializers.py:171` |
| `MoveToPrintingRequestSerializer.material (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/procurement/serializers.py:188` |
| `MoveToPrintingRequestSerializer.color (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/procurement/serializers.py:189` |
| `MoveToPrintingRequestSerializer.brand (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/procurement/serializers.py:190` |
| `MoveToPrintingRequestSerializer.lot_code (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/procurement/serializers.py:191` |
| `MoveToPrintingRequestSerializer.initial_weight_grams (serializers.DecimalField)` | `max_digits=8` | field / model | `backend/apps/procurement/serializers.py:192` |
| `MoveToPrintingRequestSerializer.remaining_weight_grams (serializers.DecimalField)` | `max_digits=8` | field / model | `backend/apps/procurement/serializers.py:197` |
| `MoveToPrintingRequestSerializer.name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/serializers.py:204` |
| `MoveToPrintingRequestSerializer.model (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/procurement/serializers.py:205` |
| `ToBuyReceiptPresignSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/procurement/serializers.py:214` |
| `ToBuyReceiptPresignSerializer.content_type (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/procurement/serializers.py:215` |
| `ToBuyReceiptFinalizeSerializer.object_key (serializers.CharField)` | `max_length=512` | field / model | `backend/apps/procurement/serializers.py:219` |
| `DEFAULT_LIST_LIMIT` | `200` | fixed / see setting | `backend/apps/procurement/views_common.py:26` |
| `MAX_LIST_LIMIT` | `500` | fixed / see setting | `backend/apps/procurement/views_common.py:27` |
| `RefillConsumableRequestSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/procurement/views_move.py:84` |
| `MarkBoughtSerializer.amount (MoneyField)` | `max_digits=13, min_value=Decimal('0.001')` | field / model | `backend/apps/procurement/views_vendors.py:34` |
| `MarkBoughtSerializer.currency (serializers.CharField)` | `max_length=3` | field / model | `backend/apps/procurement/views_vendors.py:35` |
| `MarkBoughtSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/procurement/views_vendors.py:37` |
| `MarkBoughtSerializer.receipt_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/procurement/views_vendors.py:38` |
| `MarkBoughtSerializer.vendor_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/procurement/views_vendors.py:41` |
| `MarkBoughtSerializer.vendor_name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/procurement/views_vendors.py:42` |
| `MarkBoughtSerializer.refill_amount (serializers.DecimalField)` | `max_digits=12, min_value=Decimal('0.01')` | field / model | `backend/apps/procurement/views_vendors.py:43` |

</details>

<details>
<summary>roadmap (3 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `RoadmapItem.title (models.CharField)` | `max_length=200` | field / model | `backend/apps/roadmap/models.py:11` |
| `RoadmapItem.status (models.CharField)` | `max_length=20; default=Status.PLANNED` | field / model | `backend/apps/roadmap/models.py:13` |
| `RoadmapItem.category (models.CharField)` | `max_length=100` | field / model | `backend/apps/roadmap/models.py:18` |

</details>

<details>
<summary>separability (1 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `_MAX_ID` | `9007199254740991` | fixed / see setting | `backend/apps/separability/booking_decision_intent.py:9` |

</details>

<details>
<summary>shop (82 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `STAFF_EVENT_LIMIT` | `50` | fixed / see setting | `backend/apps/shop/event_offers.py:21` |
| `ShopSettings.online_hold_minutes (MinValueValidator)` | `min_value=5` | field / model | `backend/apps/shop/models_catalogue.py:27` |
| `ShopSettings.online_hold_minutes (MaxValueValidator)` | `max_value=120` | field / model | `backend/apps/shop/models_catalogue.py:28` |
| `ShopSettings.desk_hold_hours (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_catalogue.py:29` |
| `ShopSettings.desk_hold_hours (MaxValueValidator)` | `max_value=720` | field / model | `backend/apps/shop/models_catalogue.py:30` |
| `ShopSettings.returns_window_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/shop/models_catalogue.py:32` |
| `ShopSettings.first_reminder_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_catalogue.py:34` |
| `ShopSettings.first_reminder_days (MaxValueValidator)` | `max_value=90` | field / model | `backend/apps/shop/models_catalogue.py:35` |
| `ShopSettings.second_reminder_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_catalogue.py:36` |
| `ShopSettings.second_reminder_days (MaxValueValidator)` | `max_value=180` | field / model | `backend/apps/shop/models_catalogue.py:37` |
| `ShopSettings.uncollected_cancel_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_catalogue.py:38` |
| `ShopSettings.uncollected_cancel_days (MaxValueValidator)` | `max_value=365` | field / model | `backend/apps/shop/models_catalogue.py:39` |
| `ShopSettings.policy_text (models.TextField)` | `max_length=2000; default=''` | field / model | `backend/apps/shop/models_catalogue.py:41` |
| `ShopSettings.pickup_note (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/shop/models_catalogue.py:42` |
| `ShopProduct.kind (models.CharField)` | `max_length=16; default=Kind.OTHER` | field / model | `backend/apps/shop/models_catalogue.py:68` |
| `ShopProduct.name (models.CharField)` | `max_length=200` | field / model | `backend/apps/shop/models_catalogue.py:69` |
| `ShopProduct.slug (models.SlugField)` | `max_length=80` | field / model | `backend/apps/shop/models_catalogue.py:70` |
| `ShopProduct.description (models.TextField)` | `max_length=4000; default=''` | field / model | `backend/apps/shop/models_catalogue.py:71` |
| `ShopProduct.image_key (models.CharField)` | `max_length=512; default=''` | field / model | `backend/apps/shop/models_catalogue.py:73` |
| `ShopProduct.category (models.CharField)` | `max_length=80; default=''` | field / model | `backend/apps/shop/models_catalogue.py:74` |
| `ShopProduct.unit (models.CharField)` | `max_length=32; default='each'` | field / model | `backend/apps/shop/models_catalogue.py:78` |
| `ShopProduct.max_per_order (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_catalogue.py:80` |
| `ShopProduct.tax_rate_bps (MaxValueValidator)` | `max_value=10000` | field / model | `backend/apps/shop/models_catalogue.py:87` |
| `ShopProduct.hsn_code (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/shop/models_catalogue.py:88` |
| `ShopVariant.name (models.CharField)` | `max_length=120; default='Standard'` | field / model | `backend/apps/shop/models_catalogue.py:113` |
| `ShopVariant.sku (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/shop/models_catalogue.py:116` |
| `ShopVariant.price (MinValueValidator)` | `min_value=0` | field / model | `backend/apps/shop/models_catalogue.py:117` |
| `ShopKitComponent.quantity (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_catalogue.py:151` |
| `ShopOrder.channel (models.CharField)` | `max_length=8; default=Channel.ONLINE` | field / model | `backend/apps/shop/models_orders.py:54` |
| `ShopOrder.status (models.CharField)` | `max_length=20; default=Status.HELD` | field / model | `backend/apps/shop/models_orders.py:55` |
| `ShopOrder.pickup_at (models.CharField)` | `max_length=8; default=Pickup.SPACE` | field / model | `backend/apps/shop/models_orders.py:62` |
| `ShopOrder.pickup_code (models.CharField)` | `max_length=12` | field / model | `backend/apps/shop/models_orders.py:66` |
| `ShopOrder.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/shop/models_orders.py:67` |
| `ShopOrder.digest (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/shop/models_orders.py:77` |
| `ShopOrder.status_secret (models.CharField)` | `max_length=32; default=new_status_secret` | field / model | `backend/apps/shop/models_orders.py:79` |
| `ShopOrder.close_reason (models.CharField)` | `max_length=24; default=''` | field / model | `backend/apps/shop/models_orders.py:93` |
| `ShopOrder.idempotency_key (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/shop/models_orders.py:98` |
| `ShopOrderLine.label (models.CharField)` | `max_length=240` | field / model | `backend/apps/shop/models_orders.py:130` |
| `ShopOrderLine.sku (models.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/shop/models_orders.py:131` |
| `ShopOrderLine.quantity (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_orders.py:132` |
| `ShopOrderLine.hsn_code (models.CharField)` | `max_length=8; default=''` | field / model | `backend/apps/shop/models_orders.py:139` |
| `ShopOrderReturn.quantity (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/shop/models_orders.py:165` |
| `ShopOrderReturn.disposition (models.CharField)` | `max_length=12` | field / model | `backend/apps/shop/models_orders.py:166` |
| `ShopOrderReturn.reason (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/shop/models_orders.py:170` |
| `ShopCashSession.status (models.CharField)` | `max_length=8; default=Status.OPEN` | field / model | `backend/apps/shop/models_pos.py:27` |
| `ShopCashSession.currency (models.CharField)` | `max_length=3` | field / model | `backend/apps/shop/models_pos.py:28` |
| `ShopCashSession.note (models.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/shop/models_pos.py:35` |
| `ShopStockMovement.kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/shop/models_stock.py:35` |
| `ShopStockMovement.reason (models.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/shop/models_stock.py:40` |
| `ShopCheckoutHold.release_reason (models.CharField)` | `max_length=12; default=''` | field / model | `backend/apps/shop/models_stock.py:68` |
| `MAX_LINES` | `50` | fixed / see setting | `backend/apps/shop/pricing.py:19` |
| `MAX_QUANTITY` | `999` | fixed / see setting | `backend/apps/shop/pricing.py:20` |
| `ShopLineInputSerializer.variant_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/shop/serializers_public.py:64` |
| `ShopLineInputSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=999` | field / model | `backend/apps/shop/serializers_public.py:65` |
| `ShopQuoteRequestSerializer.lines (ShopLineInputSerializer)` | `min_length=1, max_length=50` | field / model | `backend/apps/shop/serializers_public.py:69` |
| `ShopQuoteLineSerializer.quantity (serializers.DecimalField)` | `max_digits=12` | field / model | `backend/apps/shop/serializers_public.py:75` |
| `ShopOrderCreateSerializer.quote_digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/shop/serializers_public.py:97` |
| `ShopOrderCreateSerializer.guest_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/shop/serializers_public.py:100` |
| `ShopOrderCreateSerializer.guest_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/shop/serializers_public.py:101` |
| `ShopOrderCreateSerializer.email_code (serializers.CharField)` | `max_length=12` | field / model | `backend/apps/shop/serializers_public.py:102` |
| `ShopEmailCodeSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/shop/serializers_public.py:106` |
| `ShopComponentSerializer.variant_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/shop/serializers_staff.py:38` |
| `ShopComponentSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=999; default=1` | field / model | `backend/apps/shop/serializers_staff.py:39` |
| `ShopProductSerializer.price (MoneyField)` | `min_value=0` | field / model | `backend/apps/shop/serializers_staff.py:47` |
| `ShopStockMoveSerializer.quantity (serializers.IntegerField)` | `min_value=-100000, max_value=100000` | field / model | `backend/apps/shop/serializers_staff.py:68` |
| `ShopStockMoveSerializer.reason (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/shop/serializers_staff.py:69` |
| `ShopReturnRowSerializer.line_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/shop/serializers_staff.py:93` |
| `ShopReturnRowSerializer.quantity (serializers.IntegerField)` | `min_value=1, max_value=999` | field / model | `backend/apps/shop/serializers_staff.py:94` |
| `ShopReturnSerializer.rows (ShopReturnRowSerializer)` | `min_length=1, max_length=50` | field / model | `backend/apps/shop/serializers_staff.py:99` |
| `ShopReturnSerializer.reason (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/shop/serializers_staff.py:100` |
| `ShopDeskPaymentSerializer.reference (serializers.CharField)` | `max_length=64; default=''` | field / model | `backend/apps/shop/serializers_staff.py:154` |
| `ShopPosQuoteSerializer.lines (ShopLineInputSerializer)` | `min_length=1, max_length=50` | field / model | `backend/apps/shop/serializers_staff.py:160` |
| `ShopPosSaleSerializer.quote_digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/shop/serializers_staff.py:165` |
| `ShopPosSaleSerializer.receipt_email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/shop/serializers_staff.py:166` |
| `ShopCollectSerializer.pickup_code (serializers.CharField)` | `max_length=12` | field / model | `backend/apps/shop/serializers_staff.py:170` |
| `ShopCancelSerializer.reason (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/shop/serializers_staff.py:174` |
| `ShopCashOpenSerializer.opening_float (MoneyField)` | `min_value=0` | field / model | `backend/apps/shop/serializers_staff.py:183` |
| `ShopCashCloseSerializer.counted_cash (MoneyField)` | `min_value=0` | field / model | `backend/apps/shop/serializers_staff.py:187` |
| `ShopCashCloseSerializer.note (serializers.CharField)` | `max_length=300; default=''` | field / model | `backend/apps/shop/serializers_staff.py:188` |
| `ShopReceiptEmailSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/shop/serializers_staff.py:248` |
| `ShopEventOfferSetSerializer.variant_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/shop/views_event_offers.py:30` |
| `ShopEventOfferSetSerializer.variant_ids (serializers.ListField)` | `max_length=50` | field / model | `backend/apps/shop/views_event_offers.py:30` |

</details>

<details>
<summary>space_controls (26 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `HELD_LIMIT` | `5000` | fixed / see setting | `backend/apps/space_controls/held_mail.py:13` |
| `SpaceControlState.suspension_reason (models.CharField)` | `max_length=500` | field / model | `backend/apps/space_controls/models.py:32` |
| `SpaceControlState.read_only_reason (models.CharField)` | `max_length=500` | field / model | `backend/apps/space_controls/models.py:37` |
| `SpaceControlState.read_only_source (models.CharField)` | `max_length=24` | field / model | `backend/apps/space_controls/models.py:38` |
| `SpaceControlState.purge_grace_days (MaxValueValidator)` | `max_value=3650` | field / model | `backend/apps/space_controls/models.py:46` |
| `SpaceControlState.purge_grace_days (MinValueValidator)` | `min_value=1` | field / model | `backend/apps/space_controls/models.py:46` |
| `SpaceControlState.schedule_note (models.CharField)` | `max_length=500` | field / model | `backend/apps/space_controls/models.py:48` |
| `PlatformAnnouncement.title (models.CharField)` | `max_length=120` | field / model | `backend/apps/space_controls/models.py:92` |
| `PlatformAnnouncement.body (models.TextField)` | `max_length=4000` | field / model | `backend/apps/space_controls/models.py:93` |
| `PlatformAnnouncement.severity (models.CharField)` | `max_length=16; default=Severity.INFO` | field / model | `backend/apps/space_controls/models.py:94` |
| `PlatformAnnouncement.audience (models.CharField)` | `max_length=16; default=Audience.ALL_SPACES` | field / model | `backend/apps/space_controls/models.py:95` |
| `SpaceControlReasonSerializer.reason (serializers.CharField)` | `min_length=10, max_length=500` | field / model | `backend/apps/space_controls/serializers.py:115` |
| `SpaceScheduleRequestSerializer.purge_grace_days (serializers.IntegerField)` | `min_value=1, max_value=3650; default=90` | field / model | `backend/apps/space_controls/serializers.py:124` |
| `SpaceScheduleRequestSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/space_controls/serializers.py:125` |
| `SpaceScheduleRequestSerializer.confirm_slug (serializers.CharField)` | `max_length=50` | field / model | `backend/apps/space_controls/serializers.py:126` |
| `SpacePurgeRequestSerializer.confirm_slug (serializers.CharField)` | `max_length=50` | field / model | `backend/apps/space_controls/serializers.py:130` |
| `SpaceTransferRequestSerializer.email (serializers.EmailField)` | `max_length=254` | field / model | `backend/apps/space_controls/serializers.py:134` |
| `SpaceTransferRequestSerializer.previous_roles (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/space_controls/serializers.py:137` |
| `PlatformAnnouncementCreateSerializer.title (serializers.CharField)` | `max_length=120` | field / model | `backend/apps/space_controls/views_announcements.py:48` |
| `PlatformAnnouncementCreateSerializer.body (serializers.CharField)` | `max_length=4000` | field / model | `backend/apps/space_controls/views_announcements.py:49` |
| `PlatformAnnouncementCreateSerializer.makerspace_ids (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/space_controls/views_announcements.py:52` |
| `OnboardingApproveSerializer.name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/space_controls/views_onboarding.py:67` |
| `OnboardingApproveSerializer.slug (serializers.SlugField)` | `max_length=50; default=''` | field / model | `backend/apps/space_controls/views_onboarding.py:68` |
| `OnboardingApproveSerializer.new_organization_name (serializers.CharField)` | `max_length=200; default=''` | field / model | `backend/apps/space_controls/views_onboarding.py:70` |
| `OnboardingChangesNoteSerializer.note (serializers.CharField)` | `min_length=10, max_length=2000` | field / model | `backend/apps/space_controls/views_onboarding.py:91` |
| `OnboardingRejectSerializer.reason (serializers.CharField)` | `min_length=10, max_length=2000` | field / model | `backend/apps/space_controls/views_onboarding.py:95` |

</details>

<details>
<summary>tenant_migration (92 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `CHUNK_MAX_BYTES` | `8 * 1024 * 1024` | fixed / see setting | `backend/apps/tenant_migration/import_chunk_parser.py:9` |
| `MAX_MEMBER_BYTES` | `2 * 1024 * 1024 * 1024` | fixed / see setting | `backend/apps/tenant_migration/import_staging.py:17` |
| `MAX_ARCHIVE_BYTES` | `20 * 1024 * 1024 * 1024` | fixed / see setting | `backend/apps/tenant_migration/import_staging.py:18` |
| `ExternalTenantReference.source_archive_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models.py:31` |
| `ExternalTenantReference.source_model_label (models.CharField)` | `max_length=100` | field / model | `backend/apps/tenant_migration/models.py:34` |
| `ExternalTenantReference.source_object_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models.py:35` |
| `ExternalTenantReference.field_name (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models.py:36` |
| `ExternalTenantReference.target_model_label (models.CharField)` | `max_length=100` | field / model | `backend/apps/tenant_migration/models.py:37` |
| `ExternalTenantReference.target_object_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models.py:38` |
| `TenantImportJob.source_archive_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_import_job.py:25` |
| `TenantImportJob.source_makerspace_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_import_job.py:26` |
| `TenantImportJob.source_makerspace_slug (models.CharField)` | `max_length=100` | field / model | `backend/apps/tenant_migration/models_import_job.py:27` |
| `TenantImportJob.source_makerspace_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/tenant_migration/models_import_job.py:28` |
| `TenantImportJob.source_deployment_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/tenant_migration/models_import_job.py:29` |
| `TenantImportJob.storage_mode (models.CharField)` | `max_length=32` | field / model | `backend/apps/tenant_migration/models_import_job.py:31` |
| `TenantImportJob.status (models.CharField)` | `max_length=32; default=Status.PENDING` | field / model | `backend/apps/tenant_migration/models_import_job.py:39` |
| `TenantImportJob.archive_path (models.CharField)` | `max_length=1024` | field / model | `backend/apps/tenant_migration/models_import_job.py:53` |
| `TenantImportJob.failure_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_import_job.py:58` |
| `TenantImportJob.failure_detail (models.CharField)` | `max_length=500` | field / model | `backend/apps/tenant_migration/models_import_job.py:59` |
| `ImportIdentityDecision.source_user_id (models.CharField)` | `max_length=255` | field / model | `backend/apps/tenant_migration/models_import_job.py:87` |
| `ImportIdentityDecision.identity_resolution (models.CharField)` | `max_length=24` | field / model | `backend/apps/tenant_migration/models_import_job.py:89` |
| `ImportIdentityDecision.membership_disposition (models.CharField)` | `max_length=24` | field / model | `backend/apps/tenant_migration/models_import_job.py:92` |
| `TenantImportObject.bucket_kind (models.CharField)` | `max_length=16` | field / model | `backend/apps/tenant_migration/models_import_objects.py:26` |
| `TenantImportObject.source_key (models.CharField)` | `max_length=1024` | field / model | `backend/apps/tenant_migration/models_import_objects.py:27` |
| `TenantImportObject.staging_key (models.CharField)` | `max_length=1024` | field / model | `backend/apps/tenant_migration/models_import_objects.py:28` |
| `TenantImportObject.target_key (models.CharField)` | `max_length=1024` | field / model | `backend/apps/tenant_migration/models_import_objects.py:29` |
| `TenantImportObject.sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_import_objects.py:31` |
| `TenantImportObject.content_type (models.CharField)` | `max_length=255; default=''` | field / model | `backend/apps/tenant_migration/models_import_objects.py:32` |
| `TenantImportObject.state (models.CharField)` | `max_length=16; default=State.STAGED` | field / model | `backend/apps/tenant_migration/models_import_objects.py:33` |
| `DeploymentSigningKey.public_key (models.CharField)` | `max_length=44` | field / model | `backend/apps/tenant_migration/models_protocol.py:14` |
| `DeploymentSigningKey.fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:15` |
| `DisclosureClosureApproval.closure_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:28` |
| `TenantMigrationExportJob.closure_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:69` |
| `TenantMigrationExportJob.target_age_recipient (models.CharField)` | `max_length=256` | field / model | `backend/apps/tenant_migration/models_protocol.py:70` |
| `TenantMigrationExportJob.archive_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:72` |
| `MigrationPairing.source_tenant_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:81` |
| `MigrationPairing.archive_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:82` |
| `MigrationPairing.source_deployment_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/tenant_migration/models_protocol.py:83` |
| `MigrationPairing.source_public_key (models.CharField)` | `max_length=44` | field / model | `backend/apps/tenant_migration/models_protocol.py:84` |
| `MigrationPairing.source_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:85` |
| `MigrationPairing.target_deployment_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/tenant_migration/models_protocol.py:86` |
| `MigrationPairing.target_public_key (models.CharField)` | `max_length=44` | field / model | `backend/apps/tenant_migration/models_protocol.py:87` |
| `MigrationPairing.target_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:88` |
| `MigrationReceipt.operation (models.CharField)` | `max_length=24` | field / model | `backend/apps/tenant_migration/models_protocol.py:121` |
| `MigrationReceipt.source_tenant_id (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:123` |
| `MigrationReceipt.archive_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:124` |
| `MigrationReceipt.source_deployment_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/tenant_migration/models_protocol.py:125` |
| `MigrationReceipt.target_deployment_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/tenant_migration/models_protocol.py:126` |
| `MigrationReceipt.signer_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:127` |
| `MigrationReceipt.signature (models.CharField)` | `max_length=88` | field / model | `backend/apps/tenant_migration/models_protocol.py:128` |
| `ReceiptConsumption.purpose (models.CharField)` | `max_length=24` | field / model | `backend/apps/tenant_migration/models_protocol.py:152` |
| `MigratedOutHandoff.archive_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_protocol.py:175` |
| `MigratedOutHandoff.target_deployment_id (models.CharField)` | `max_length=128` | field / model | `backend/apps/tenant_migration/models_protocol.py:176` |
| `MigratedOutHandoff.state (models.CharField)` | `max_length=24; default=State.MIGRATED_OUT` | field / model | `backend/apps/tenant_migration/models_protocol.py:177` |
| `SelfHostMoveRequest.status (models.CharField)` | `max_length=16; default=Status.REQUESTED` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:34` |
| `SelfHostMoveRequest.note (models.TextField)` | `max_length=2000` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:35` |
| `SelfHostMoveRequest.decision_note (models.CharField)` | `max_length=500` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:42` |
| `SelfHostMoveRequest.recipient_fingerprint (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:43` |
| `SelfHostMoveRequest.artifact_path (models.CharField)` | `max_length=500` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:44` |
| `SelfHostMoveRequest.artifact_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:45` |
| `SelfHostMoveRequest.failure_code (models.CharField)` | `max_length=48` | field / model | `backend/apps/tenant_migration/models_selfhost_move.py:47` |
| `SourceMigrationGate.state (models.CharField)` | `max_length=16; default=State.OPEN` | field / model | `backend/apps/tenant_migration/models_source_gate.py:27` |
| `SourceMigrationGate.purpose (models.CharField)` | `max_length=24; default=Purpose.MIGRATION` | field / model | `backend/apps/tenant_migration/models_source_gate.py:30` |
| `TenantDumpCapture.status (models.CharField)` | `max_length=32; default=Status.REQUESTED` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:34` |
| `TenantDumpCapture.source_makerspace_slug (models.SlugField)` | `max_length=100` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:42` |
| `TenantDumpCapture.database_image_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:51` |
| `TenantDumpCapture.object_ledger_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:53` |
| `TenantDumpCapture.money_fingerprint_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:57` |
| `TenantDumpCapture.catalog_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:59` |
| `TenantDumpCapture.parent_database_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:61` |
| `TenantDumpCapture.parent_object_ledger_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:62` |
| `TenantDumpCapture.derivation_policy_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:63` |
| `TenantDumpCapture.artifact_sha256 (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:66` |
| `TenantDumpCapture.unpublished_object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:68` |
| `TenantDumpCapture.object_key (models.CharField)` | `max_length=512` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:69` |
| `TenantDumpCapture.download_token_digest (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:70` |
| `TenantDumpCapture.refusal_code (models.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:73` |
| `TenantDumpCapture.refusal_detail (models.CharField)` | `max_length=500` | field / model | `backend/apps/tenant_migration/models_tenant_dump.py:74` |
| `MAX_QUERY_PARAMETERS` | `60000` | fixed / see setting | `backend/apps/tenant_migration/raw_repository.py:14` |
| `PendingClosureSerializer.digest (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/serializers.py:65` |
| `ClosureApprovalCreateSerializer.digest (serializers.CharField)` | `min_length=64, max_length=64` | field / model | `backend/apps/tenant_migration/serializers.py:75` |
| `MigrationExportCreateSerializer.target_age_recipient (serializers.CharField)` | `max_length=256` | field / model | `backend/apps/tenant_migration/serializers.py:105` |
| `ImportIdentityDecisionSerializer.source_user_id (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/tenant_migration/serializers.py:176` |
| `PairingCreateSerializer.source_tenant_id (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/serializers.py:244` |
| `ReceiptEnvelopeSerializer.signer_fingerprint (serializers.CharField)` | `max_length=64` | field / model | `backend/apps/tenant_migration/serializers.py:252` |
| `ReceiptEnvelopeSerializer.signature (serializers.CharField)` | `max_length=88` | field / model | `backend/apps/tenant_migration/serializers.py:253` |
| `ImportUploadStartSerializer.archive_bytes (serializers.IntegerField)` | `min_value=1, max_value=MAX_ARCHIVE_BYTES` | field / model | `backend/apps/tenant_migration/serializers_import_upload.py:11` |
| `MAX_OUTER_MANIFEST_BYTES` | `64 * 1024` | fixed / see setting | `backend/apps/tenant_migration/tenant_dump_outer_artifact.py:19` |
| `MAX_CALLBACK_TIMEOUT_SECONDS` | `300` | fixed / see setting | `backend/apps/tenant_migration/tenant_restore_scheduler.py:12` |
| `SelfHostMoveCreateSerializer.note (serializers.CharField)` | `max_length=2000; default=''` | field / model | `backend/apps/tenant_migration/views_selfhost_move.py:35` |
| `MoveDecisionSerializer.note (serializers.CharField)` | `max_length=500; default=''` | field / model | `backend/apps/tenant_migration/views_selfhost_moves_platform.py:59` |
| `ExportSerializer.recipient (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/tenant_migration/views_selfhost_moves_platform.py:63` |

</details>

<details>
<summary>tenant_rls (1 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `FixedRoleScope.role_name (models.CharField)` | `max_length=63` | field / model | `backend/apps/tenant_rls/models.py:13` |

</details>

<details>
<summary>warranty (12 declarations)</summary>

| Setting or bound | Value / default expression | Owner / kind | Source |
| --- | --- | --- | --- |
| `Warranty.vendor_name (models.CharField)` | `max_length=200` | field / model | `backend/apps/warranty/models.py:29` |
| `Warranty.vendor_contact (models.CharField)` | `max_length=200` | field / model | `backend/apps/warranty/models.py:30` |
| `WarrantyDocument.object_key (models.CharField)` | `max_length=300` | field / model | `backend/apps/warranty/models.py:76` |
| `WarrantyDocument.original_filename (models.CharField)` | `max_length=255` | field / model | `backend/apps/warranty/models.py:77` |
| `WarrantyDocument.content_type (models.CharField)` | `max_length=100` | field / model | `backend/apps/warranty/models.py:78` |
| `WarrantyUpsertSerializer.vendor_name (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/warranty/serializers.py:99` |
| `WarrantyUpsertSerializer.vendor_contact (serializers.CharField)` | `max_length=200` | field / model | `backend/apps/warranty/serializers.py:100` |
| `WarrantyUpsertSerializer.vendor_id (serializers.IntegerField)` | `min_value=1` | field / model | `backend/apps/warranty/serializers.py:101` |
| `WarrantyDocumentPresignSerializer.filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/warranty/serializers.py:106` |
| `WarrantyDocumentPresignSerializer.content_type (serializers.CharField)` | `max_length=100` | field / model | `backend/apps/warranty/serializers.py:107` |
| `WarrantyDocumentFinalizeSerializer.object_key (serializers.CharField)` | `max_length=300` | field / model | `backend/apps/warranty/serializers.py:111` |
| `WarrantyDocumentFinalizeSerializer.original_filename (serializers.CharField)` | `max_length=255` | field / model | `backend/apps/warranty/serializers.py:112` |

</details>
