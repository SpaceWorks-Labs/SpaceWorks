"""Programme surfaces, mounted through config.urls.separable('events', ...).

Views/services retain their tenant module, capability and authority checks.
One pattern serves every method for a resource; no duplicate method aliases.
"""
from django.urls import include, path

urlpatterns = [
    path("member/", include("apps.events.hackathons.urls_member")),
    path("admin/", include("apps.events.hackathons.urls_admin")),
    path("public/", include("apps.events.hackathons.urls_public")),
    path("member/", include("apps.events.submissions.urls_member")),
    path("admin/", include("apps.events.submissions.urls_admin")),
    path("public/", include("apps.events.submissions.urls_public")),
    path("member/", include("apps.events.contributions.urls_member")),
    path("admin/", include("apps.events.contributions.urls_admin")),
    path("public/", include("apps.events.contributions.urls_public")),
    path("member/", include("apps.events.mentoring.urls_member")),
    path("admin/", include("apps.events.mentoring.urls_admin")),
    path("", include("apps.events.judging.urls")),
    path("admin/", include("apps.events.credentials.urls_admin")),
    path("admin/", include("apps.events.certificates.urls_admin")),
    path("admin/", include("apps.events.certificates.urls_library")),
    path("public/", include("apps.events.certificates.urls_public")),
    path("member/", include("apps.events.certificates.urls_member")),
    path("member/", include("apps.events.profile_photos.urls_member")),
    path("public/", include("apps.events.profile_photos.urls_public")),
    path("admin/", include("apps.events.programme.broadcast_urls")),
]

from .contributions.urls_completion import ADMIN, MEMBER
from .mentoring.urls_completion import urlpatterns as mentoring_completion
from .programme.urls import admin_patterns, series_patterns

from .urls_l21a import ADMIN as L21A_ADMIN, MEMBER as L21A_MEMBER, PUBLIC as L21A_PUBLIC
from .urls_l21b import ADMIN as L21B_ADMIN

urlpatterns += [
    # Lane L21a: review stages, participation switches, attendance, re-accept, crew, check-in lists.
    path("admin/", include(L21A_ADMIN)),
    path("member/", include(L21A_MEMBER)),
    path("public/", include(L21A_PUBLIC)),
    # Lane L21b: filtered staff lists and their CSV exports.
    path("admin/", include(L21B_ADMIN)),
    path("admin/", include(ADMIN)),
    path("member/", include(MEMBER)),
    path("admin/", include(mentoring_completion)),
    path("admin/", include(admin_patterns)),
    path("admin/", include(series_patterns)),
]
