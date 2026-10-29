"""Integrator attaches at root after crawler and origin registrations land."""

from django.urls import path, re_path
from apps.separability.registry import runtime_active
from .public_page_share import PublicPageCoverShareView, PublicPageShareView

urlpatterns = [
    path("share/pages/<str:handle>/", PublicPageShareView.as_view(), name="public-page-share"),
    path("share/pages/<str:handle>/cover/", PublicPageCoverShareView.as_view(), name="public-page-cover-share"),
]
if runtime_active("events"):
    from apps.events.views_public_codes import PublicEventCodeShareView, PublicEventCoverShareView
    urlpatterns += [
        path("share/e/<uuid:public_token>/", PublicEventCodeShareView.as_view(), name="public-event-code-share"),
        path("share/e/<uuid:public_token>/cover/", PublicEventCoverShareView.as_view(), name="public-event-cover-share"),
        # Short codes are aliases of the same live gate; the crawler card never counts a visit.
        re_path(r"^share/e/(?P<code>[0-9A-Za-z]{7})/$", PublicEventCodeShareView.as_view(),
                name="public-event-short-code-share"),
        re_path(r"^share/e/(?P<code>[0-9A-Za-z]{7})/cover/$", PublicEventCoverShareView.as_view(),
                name="public-event-short-code-cover-share"),
    ]
