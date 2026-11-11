"""Presence's staff API, relocated out of `admin_api` (plan B5/B6, phase 12).

Separate from `urls.py`, which carries the member-facing check-in routes mounted under
`/api/v1/public/`. Two urlconfs rather than one because the prefixes differ; both are
withdrawn together by the same tombstone.

Mounted at `admin_api`'s own `/api/v1/admin/` prefix with the path and route name
unchanged, so `origin_scope_routes` (keyed by bare `url_name`) and the OpenAPI snapshot
are unaffected. No `app_name`, matching `admin_api`.
"""

from django.urls import path

from apps.presence.views import PresenceRosterView
from .views_staff import StaffPresenceStartView, StaffPresenceEndView, PresencePrivacyView
from .views_staff_guests import StaffCheckInGuestSearchView

urlpatterns = [
    path("makerspace/<int:makerspace_id>/presence-sessions/check-in", StaffPresenceStartView.as_view(), name="admin-presence-start"),
    path("makerspace/<int:makerspace_id>/presence-sessions/check-in-guests", StaffCheckInGuestSearchView.as_view(), name="admin-presence-check-in-guests"),
    path("makerspace/<int:makerspace_id>/presence-sessions/check-out", StaffPresenceEndView.as_view(), name="admin-presence-end"),
    path("makerspace/<int:makerspace_id>/presence-sessions/privacy", PresencePrivacyView.as_view(), name="admin-presence-privacy"),
    path(
        "makerspace/<int:makerspace_id>/presence-sessions/current",
        PresenceRosterView.as_view(),
        name="admin-presence-sessions-current",
    ),
]
