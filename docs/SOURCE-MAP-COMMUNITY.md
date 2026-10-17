# Community and public-page source map

Continued from [SOURCE-MAP.md](SOURCE-MAP.md). Paths are repository-relative. Notification
transport and domain-adapter ownership continues in [SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md).

## Public maker profiles

`makerspaces/models_profiles.py` owns MemberProfile/MemberProject plus PublicHandle,
PublicHandleRedirect and ProfileTimelineEntry; migration 0094 adds the public contract.
`public_profile_handles.py` owns locked claim/rename/release, `public_profile_reserved.py` and
`public_profile_route_inventory.py` the reserved namespace and drift inputs. `public_profile_access.py`
owns the single public/tenant predicate; projection/serializers/views own the allow-list response.
public_profile_views.py optionally authenticates the main read for viewer_is_owner;
profile_services.py/profile_serializers.py expose verified from the selected membership.
`public_profile_validation.py` owns fresh publication consent and bounded timeline/link fields;
`profile_services.py`/`profile_projects.py` apply member-owned audited writes. Contract routes/views
own handles and timeline. `public_profile_cache.py` owns generation/cache invalidation.

`profile_activity_sources.py` owns source registration/consent mapping;
`profile_activity_public.py` owns local-day windowing and counts/dedup. `profile_activity_p2.py`
adds loans/bookings/speaking to the existing projects/events/machine sources. `profile_history_public.py`
selects ATTENDED/HOSTED/SPOKE and `profile_history_speaking.py` adapts the speaker seam;
`profile_history_views.py` owns the paginated events response. `profile_github*` divides cache,
bounded fetch, background refresh and URL/view responsibilities. `tasks.py` composes calendar
refresh into the existing daily GitHub task.

`public_profile_share.py` owns live-gated cards/sitemap URLs. `website_urls.py` mounts the share
route; frontend nginx and deploy/Caddyfile variants own crawler rewrites/reserved exclusions.
`frontend/src/features/profile/` owns the anonymous /<handle> page, counts/calendar rendering,
section tabs and event badges; `edit/` owns handle, consent, family switches, timeline and preview.
`features/members/memberProfile/PublicContentFields.tsx` extends the ordinary profile form.
`features/NotFoundPage.tsx` is the shared 404; AppRoutes.tsx keeps the handle route last before `*`.

## Presence

`presence/models.py` owns sessions/settings/preferences, with account/member compatibility in
migration 0003. `policy.py` owns module/account/staff/duration/project checks; `geofence.py` owns
hard self-check-in validation. `services.py` owns transactional start/renew/end/staff paths;
`renewal.py` shares renewal eligibility/deadlines between the current-session hint and the writer, and
`services_claim.py` retains claim-session revocation/deadlines. `event_attendance.py` is the live
post-commit event-ticket adapter, called by events/services_checkin.py.
`privacy.py` writes tenant/personal display policy; `display.py` projects the allow-list TV rows,
`cache.py` bounds server caching and `signals.py` advances display generations.
`tasks.py` closes expired rows and queues `notifications.py` revision-bound outbox reminders;
`schedule.py` supplies the common beat/beat-less cadence. `purge.py` owns presence purge.
`serializers.py`/`schema.py`, views.py/views_public.py/views_staff.py and urls.py/urls_admin.py
split member, TV and staff APIs. `makerspaces/module_registry_p2_presence.py` declares the module.
makerspaces/0096_enable_existing_presence installs it for existing rows; new spaces opt in.
makerspaces/validators.py shares the 60/120/180/240-minute service defaults. Current-session and
staff roster serializers expose personal_opt_out_allowed/names_displayed even on empty responses.

`features/presence/api.ts` owns typed requests, query keys, polling and invalidation.
PresenceCheckInSheet/location/presenceCopy own the self-check-in interaction;
PresencePanel/PresenceRenewPrompt/renewReminder/webNotify own session/renewal prompts.
PresenceRoster/StaffCheckInDialog own the staff roster; PresenceNowPage/PresenceNowBoard own
/m/:slug/now and the single-space /now alias. PresencePrivacySettings is mounted by
MakerspaceSettingsPanel for Space Managers with presence enabled. The notification feature-enum
editor limit remains in INVARIANTS.md.

## Events and bookings

`events/speaker_identity_models.py` owns EventSpeaker; speaker_identity.py writes links/claims,
speaker_history.py exports contributions_for. serializers_speakers/views_speakers/urls_speakers
own speaker APIs; views_event_history.py owns self/staff history. ticketing_edit.py and
views_ticketing_edit.py own bounded ticket/category edits/deletes. notification_envelopes.py,
notification_sources.py, grant_recipients.py and broadcast_channels.py own event personal fan-out,
live source eligibility, delegates and campaign channels behind notifications.py.

`bookings/models_departure.py` owns append-only departure and issue models; services_departure.py
owns recording/resolution, services_decisions.py bounded reasons, views_queue.py the scoped queue/
issues/departure routes, serializers_departure.py their wire shape, member_notices.py owner notices.
models_gallery.py/services_gallery.py/views_gallery.py own public resource photos; views_venue.py
derives Hosted at from public space/location matches. urls_p2.py composes these routes.
notification_sources.py/reminder_envelopes.py/broadcasts_personal.py own booking personal delivery;
notification_owner_mailbox.py registers the email-only same-owner contact compatibility source,
rechecks live gates and reserves/hands off its envelope email leg without parallel delivery.
purge_p2.py removes departures/issues/photo objects. Migrations bookings/0020 and makerspaces/0095
own schema/immutability fences and the audit-aware requester-notification default.

Frontend staff Event* controls below own essentials/More/check-in, speakers, tickets/categories
and the member-drawer events block. features/events owns personal history and speaker-claim pages.
BookingQueuePanel/BookingDecisionDialog/BookingIssuesList/BookingCheckout plus bookingQueueApi
own requests/decisions/issues; features/bookings/DepartureForm is shared owner/staff input.
SpacePhotosSection/spacePhotosApi and Gallery/GalleryEditor/galleryUpload own photo editing;
EventVenueBlock and spacePhotosSection own public rendering. BookingDrawerTabs/BookingsPanel
compose the new sections. Gallery is imported directly, outside the ui/index.ts barrel.

## Makerspace home and staff settings

`features/public/MakerspacePage.tsx` composes header, Featured activities, embedded inventory and
more sections; MakerspaceHeader/MakerspaceSection/MakerspaceMoreSections split presentation,
FeaturedActivities reuses the public events query, openingHours.ts owns tenant-zone hours.
`lib/publicHome.ts` selects the combined home and exports publicFamilies; AppRoutes.tsx routes it.

`staff/sidebarSections.ts` owns SPACE_MANAGER_SECTIONS and the alternate scoped sidebar;
StaffShell selects the menu. SettingsHub/settingsHubCatalog/SetupChecklist own settings search,
links and checklist. MakerspaceSettingsPanel composes the sections; useDomainSettingsDialog and
domain consoles mount local settings. admin_api/views_loan_policy.py and
makerspaces/loan_policy_settings.py share EDIT_INVENTORY-or-MANAGE_MAKERSPACE authorization.
Fixed roles remain in makerspaces/role_catalog.py; menu grouping adds no authority.
operations/dashboard_programmes.py counts unresolved BookingIssue rows as open_booking_issues with
MANAGE_BOOKINGS scoping; serializers_dashboard.py exposes it. DashboardStats.ts and dashboardLinks.ts
render the Booking issues action and route it to the issues view.

## File inventory by owner

The concrete sibling files below complete the ownership groups above, including migration,
audit, retention, encryption and route-registry adapters. Names are relative to each directory.

### `backend/apps/accounts/`

`claim_routes_p2_presence.py`, `claim_routes_profiles.py`.

### `backend/apps/apiclients/`

`scope_registry_p2_presence.py`.

### `backend/apps/audit/`

`presentation_catalog_p2_bookings.py`, `presentation_catalog_p2_events.py`,
`presentation_catalog_p2_presence.py`, `presentation_catalog_profiles.py`.

### `backend/apps/bookings/`

`broadcasts_personal.py`, `member_notices.py`, `models_departure.py`, `models_gallery.py`,
`notification_sources.py`, `purge_p2.py`, `reminder_envelopes.py`, `serializers_departure.py`,
`services_decisions.py`, `services_departure.py`, `services_gallery.py`, `urls_p2.py`,
`views_gallery.py`, `views_queue.py`, `views_venue.py`.

### `backend/apps/bookings/migrations/`

`0020_p2_bookings.py`.

### `backend/apps/encryption/`

`registry_p2_bookings.py`.

### `backend/apps/events/`

`broadcast_channels.py`, `grant_recipients.py`, `notification_envelopes.py`, `notification_sources.py`,
`serializers_speakers.py`, `speaker_history.py`, `speaker_identity.py`, `speaker_identity_models.py`,
`ticketing_edit.py`, `urls_speakers.py`, `views_event_history.py`, `views_speakers.py`,
`views_ticketing_edit.py`.

### `backend/apps/events/migrations/`

`0036_event_speakers.py`.

### `backend/apps/makerspaces/migrations/`

`0094_public_profile_contract.py`, `0095_booking_requester_notifications_default_on.py`.

### `backend/apps/makerspaces/`

`module_registry_p2_presence.py`, `origin_scope_routes_p2_bookings.py`,
`origin_scope_routes_p2_events.py`, `profile_activity_p2.py`, `profile_activity_public.py`,
`profile_activity_sources.py`, `profile_contract_urls.py`, `profile_contract_views.py`,
`profile_github.py`, `profile_github_fetch.py`, `profile_github_tasks.py`, `profile_github_urls.py`,
`profile_github_views.py`, `profile_history_public.py`, `profile_history_speaking.py`,
`profile_history_views.py`, `profile_projects.py`, `public_profile_access.py`, `public_profile_cache.py`,
`public_profile_handles.py`, `public_profile_projection.py`, `public_profile_reserved.py`,
`public_profile_route_inventory.py`, `public_profile_serializers.py`, `public_profile_share.py`,
`public_profile_validation.py`, `public_profile_views.py`.

### `backend/apps/presence/`

`cache.py`, `display.py`, `event_attendance.py`, `notifications.py`, `policy.py`, `privacy.py`,
`purge.py`, `renewal.py`, `schedule.py`, `schema.py`, `services_claim.py`, `signals.py`, `tasks.py`, `views_public.py`,
`views_staff.py`.

### `backend/apps/presence/migrations/`

`0003_presence_programme.py`.

### `backend/apps/tenant_migration/`

`audit_references_meta_p2_bookings.py`, `catalog_p2_bookings.py`, `catalog_p2_events.py`,
`catalog_p2_presence.py`, `catalog_profiles.py`, `tenant_dump_field_snapshot_core.py`.

### `frontend/src/components/ui/`

`Gallery.tsx`, `GalleryEditor.tsx`, `galleryUpload.ts`.

### `frontend/src/features/`

`NotFoundPage.tsx`.

### `frontend/src/features/bookings/`

`DepartureForm.tsx`, `EventVenueBlock.tsx`, `spacePhotosSection.tsx`.

### `frontend/src/features/events/`

`EventHistoryLists.tsx`, `MemberEventHistoryPage.tsx`, `SpeakerClaimPage.tsx`, `eventHistoryApi.ts`.

### `frontend/src/features/members/`

`MemberEventHistoryLink.tsx`.

### `frontend/src/features/members/memberProfile/`

`PublicContentFields.tsx`.

### `frontend/src/features/presence/`

`PresenceCheckInSheet.tsx`, `PresenceNowBoard.tsx`, `PresenceNowPage.tsx`, `PresencePanel.tsx`,
`PresencePrivacySettings.tsx`, `PresenceRenewPrompt.tsx`, `PresenceRoster.tsx`, `StaffCheckInDialog.tsx`,
`api.ts`, `location.ts`, `presenceCopy.ts`, `renewReminder.ts`, `webNotify.ts`.

### `frontend/src/features/profile/`

`ContributionGrid.tsx`, `ProfileEventsTab.tsx`, `ProfileHeader.tsx`, `ProfileOverviewTab.tsx`,
`ProfileSectionTabs.tsx`, `PublicProfilePage.tsx`, `PublicProfileView.tsx`, `profileFormat.ts`,
`publicProfileApi.ts`.

### `frontend/src/features/profile/edit/`

`HandleField.tsx`, `ProfilePreviewDialog.tsx`, `PublicPageSettings.tsx`, `PublishConsentDialog.tsx`,
`TimelineEditor.tsx`, `TimelineEntryForm.tsx`, `VisibilitySwitches.tsx`, `profileEditApi.ts`.

### `frontend/src/features/public/`

`FeaturedActivities.tsx`, `MakerspaceHeader.tsx`, `MakerspaceMoreSections.tsx`, `MakerspacePage.tsx`,
`MakerspaceSection.tsx`, `openingHours.ts`.

### `frontend/src/features/staff/`

`BookingCheckout.tsx`, `BookingDecisionDialog.tsx`, `BookingIssuesList.tsx`, `BookingQueuePanel.tsx`,
`CertificateArtworkPreview.tsx`, `EventCategoryManager.tsx`, `EventCheckInTab.tsx`,
`EventDisclosure.tsx`, `EventDrawerMore.tsx`, `EventEssentialsEditor.tsx`, `EventFieldGroups.tsx`,
`EventSpeakerForms.tsx`, `EventSpeakersPanel.tsx`, `EventTicketRow.tsx`, `MemberEventsSection.tsx`,
`SettingsHub.tsx`, `SpacePhotosSection.tsx`, `bookingQueueApi.ts`, `eventCategoriesApi.ts`,
`eventDrawerTabs.ts`, `eventSpeakersApi.ts`, `settingsHubCatalog.ts`, `spacePhotosApi.ts`.
